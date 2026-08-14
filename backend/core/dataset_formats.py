"""三格式数据集纯函数解析器。

产出统一中间表示 IR（对齐 PRD §4.3），为阶段二格式互转写出器预留同源结构。
仅依赖 stdlib（json/xml/yaml）+ pathlib，无副作用。
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import yaml

SUPPORTED_FORMATS = ("COCO", "YOLO", "VOC")
SPLITS = ("train", "val", "test")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
_TILE_RE = re.compile(r"_tile_\d+_x\d+_y\d+$")


def _tile_origin_stem(stem: str) -> str:
    """解析 tile 文件名 stem 得原图 stem；无 tile 后缀时原样返回。"""
    return _TILE_RE.sub("", stem)


def _empty_ir(format_name: str) -> dict:
    return {"images": [], "classes": [], "meta": {
        "format": format_name, "version": "", "description": "",
        "contributor": "", "date_created": ""}}


def _list_images(folder: Path):
    return sorted([f for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in _IMAGE_EXTS])


# ── 格式识别 ──────────────────────────────────────────────
def detect_format(dataset_dir: Path) -> Optional[str]:
    """识别数据集格式。无法识别返回 None。"""
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        return None
    # COCO: annotations/*.json 含 images/annotations/categories
    ann_dir = dataset_dir / "annotations"
    if ann_dir.is_dir():
        for jf in ann_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if {"images", "annotations", "categories"} <= set(data.keys()):
                    return "COCO"
            except Exception:
                continue
    # YOLO: images/{split} + labels/{split} + 根目录含 names 的 .yaml
    has_yolo_dirs = all((dataset_dir / "images" / s).is_dir() for s in SPLITS) and \
                    all((dataset_dir / "labels" / s).is_dir() for s in SPLITS)
    if has_yolo_dirs:
        for yf in dataset_dir.glob("*.yaml"):
            try:
                cfg = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
                if "names" in cfg:
                    return "YOLO"
            except Exception:
                continue
    # VOC: {split}/images + {split}/annotations/*.xml，或 JPEGImages/+Annotations/
    voc_split = all((dataset_dir / s / "images").is_dir() and
                    (dataset_dir / s / "annotations").is_dir() for s in SPLITS)
    if voc_split:
        return "VOC"
    if (dataset_dir / "JPEGImages").is_dir() and (dataset_dir / "Annotations").is_dir():
        return "VOC"
    return None


# ── COCO 解析 ──────────────────────────────────────────────
def _coco_image_dir(dataset_dir: Path, split: str) -> Path:
    """COCO 图片布局：优先 {split}/ 直放（SSDC-UAV），回退 images/{split}/。"""
    direct = dataset_dir / split
    if direct.is_dir() and any(f.suffix.lower() in _IMAGE_EXTS for f in direct.iterdir()):
        return direct
    return dataset_dir / "images" / split


def parse_coco(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("COCO")
    ann_dir = dataset_dir / "annotations"
    cat_map = {}  # category_id → 内部 class_id
    for split in SPLITS:
        jf = ann_dir / f"{split}.json"
        if not jf.exists():
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        # 元信息（首个非空 info 块采信）
        info = data.get("info") or {}
        if info:
            ir["meta"].update({
                "format": "COCO",
                "version": str(info.get("version", "")),
                "description": info.get("description", ""),
                "contributor": info.get("contributor", ""),
                "date_created": info.get("date_created", ""),
            })
        # 类别映射（category_id 从 1 起 → 内部从 0 起）
        for cat in data.get("categories", []):
            cid = cat["id"]
            if cid not in cat_map:
                cat_map[cid] = len(ir["classes"])
                ir["classes"].append(cat["name"])
        # 图片索引
        img_by_id = {}
        for im in data.get("images", []):
            entry = {
                "filename": im["file_name"],
                "split": split,
                "width": im["width"], "height": im["height"],
                "origin_stem": _tile_origin_stem(Path(im["file_name"]).stem),
                "boxes": [],
            }
            img_by_id[im["id"]] = entry
            ir["images"].append(entry)
        # 标注
        for ann in data.get("annotations", []):
            entry = img_by_id.get(ann["image_id"])
            if entry is None:
                continue
            x, y, w, h = ann["bbox"]
            entry["boxes"].append({
                "bbox": [float(x), float(y), float(w), float(h)],
                "class_id": cat_map.get(ann["category_id"], 0),
                "class_name": ir["classes"][cat_map.get(ann["category_id"], 0)],
            })
    return ir


# ── YOLO 解析 ──────────────────────────────────────────────
def _load_yolo_config(dataset_dir: Path) -> dict:
    for yf in dataset_dir.glob("*.yaml"):
        try:
            cfg = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
            if "names" in cfg:
                return cfg
        except Exception:
            continue
    return {}


def parse_yolo(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("YOLO")
    cfg = _load_yolo_config(dataset_dir)
    names = cfg.get("names", {})
    # names 可能是 dict {0: name} 或 list [name]
    if isinstance(names, dict):
        for k in sorted(names.keys()):
            ir["classes"].append(names[k])
    elif isinstance(names, list):
        ir["classes"] = list(names)
    ir["meta"]["format"] = "YOLO"
    # 忽略 cfg['path']（过期绝对路径）

    for split in SPLITS:
        img_dir = dataset_dir / "images" / split
        lbl_dir = dataset_dir / "labels" / split
        if not img_dir.is_dir():
            continue
        for img in _list_images(img_dir):
            lbl = lbl_dir / (img.stem + ".txt")
            # 归一化→绝对像素（需要宽高，YOLO 无尺寸字段，读图片元信息开销大；
            # 此处用同目录图片的 PIL 读取尺寸）
            width, height = _image_size(img)
            boxes = []
            if lbl.exists():
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    cid = int(parts[0])
                    xc, yc, w, h = map(float, parts[1:5])
                    abs_w, abs_h = w * width, h * height
                    abs_x = xc * width - abs_w / 2
                    abs_y = yc * height - abs_h / 2
                    cname = ir["classes"][cid] if cid < len(ir["classes"]) else str(cid)
                    boxes.append({"bbox": [abs_x, abs_y, abs_w, abs_h],
                                  "class_id": cid, "class_name": cname})
            ir["images"].append({
                "filename": img.name, "split": split,
                "width": width, "height": height,
                "origin_stem": _tile_origin_stem(img.stem),
                "boxes": boxes,
            })
    return ir


def _image_size(img_path: Path):
    """读取图片宽高（YOLO 标注无尺寸字段，需读图片元信息）。"""
    from PIL import Image
    with Image.open(img_path) as im:
        return im.size


# ── VOC 解析 ──────────────────────────────────────────────
def _voc_split_dirs(dataset_dir: Path):
    """返回 [(split, images_dir, annotations_dir)]。"""
    result = []
    for split in SPLITS:
        img_dir = dataset_dir / split / "images"
        ann_dir = dataset_dir / split / "annotations"
        if img_dir.is_dir() and ann_dir.is_dir():
            result.append((split, img_dir, ann_dir))
    if not result:  # 标准 JPEGImages/+Annotations/ 布局（阶段二构建产物）
        jpg = dataset_dir / "JPEGImages"
        ann = dataset_dir / "Annotations"
        if jpg.is_dir() and ann.is_dir():
            # 标准 VOC 无 split 目录，全部归 train（导入兼容用；SSDC-UAV 走 split 布局）
            result.append(("train", jpg, ann))
    return result


def parse_voc(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("VOC")
    name_to_id = {}
    for split, img_dir, ann_dir in _voc_split_dirs(dataset_dir):
        for img in _list_images(img_dir):
            xml = ann_dir / (img.stem + ".xml")
            boxes = []
            width = height = 0
            if xml.exists():
                try:
                    tree = ET.fromstring(xml.read_text(encoding="utf-8"))
                except ET.ParseError:
                    tree = None
                if tree is not None:
                    size = tree.find("size")
                    if size is not None:
                        w = size.find("width")
                        h = size.find("height")
                        if w is not None:
                            width = int(w.text)
                        if h is not None:
                            height = int(h.text)
                    for obj in tree.findall("object"):
                        name_el = obj.find("name")
                        bnd = obj.find("bndbox")
                        if name_el is None or bnd is None:
                            continue
                        cname = name_el.text or ""
                        if cname not in name_to_id:
                            name_to_id[cname] = len(ir["classes"])
                            ir["classes"].append(cname)
                        xmin = float(bnd.find("xmin").text)
                        ymin = float(bnd.find("ymin").text)
                        xmax = float(bnd.find("xmax").text)
                        ymax = float(bnd.find("ymax").text)
                        boxes.append({"bbox": [xmin, ymin, xmax - xmin, ymax - ymin],
                                      "class_id": name_to_id[cname],
                                      "class_name": cname})
            if width == 0 or height == 0:
                width, height = _image_size(img)
            ir["images"].append({
                "filename": img.name, "split": split,
                "width": width, "height": height,
                "origin_stem": _tile_origin_stem(img.stem),
                "boxes": boxes,
            })
    ir["meta"]["format"] = "VOC"
    return ir
