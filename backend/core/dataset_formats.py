"""三格式数据集纯函数解析器。

产出统一中间表示 IR（对齐 PRD §4.3），为阶段二格式互转写出器预留同源结构。
仅依赖 stdlib（json/xml/yaml）+ pathlib，无副作用。
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

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
def detect_format(dataset_dir: Path) -> str | None:
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
