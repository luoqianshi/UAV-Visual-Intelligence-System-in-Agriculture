"""mini 数据集夹具构建器：在 tmp_path 下构建 COCO/YOLO/VOC 小数据集。"""
import json
from pathlib import Path

import yaml
from PIL import Image


def _make_jpg(path: Path, w=640, h=640):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (128, 128, 128)).save(path, "JPEG")


def build_mini_coco(root: Path):
    """构建 COCO mini 数据集（{split}/ 直放布局，对齐 SSDC-UAV）。
    train: 2 图 3 框；val: 1 图 1 框；test: 1 图 1 框。
    返回期望统计 dict 供断言。"""
    splits = {
        "train": [
            ("img_t1.jpg", 640, 640, [[10, 20, 30, 40], [100, 100, 50, 50], [200, 200, 60, 60]]),
            ("img_t2.jpg", 640, 640, [[5, 5, 20, 20]]),
        ],
        "val": [("img_v1.jpg", 640, 640, [[300, 300, 40, 40]])],
        "test": [("img_e1.jpg", 640, 640, [[400, 400, 62.5, 62.5]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "annotations").mkdir(exist_ok=True)
    for split, imgs in splits.items():
        images, anns = [], []
        aid = 1
        for fn, w, h, boxes in imgs:
            _make_jpg(root / split / fn, w, h)
            images.append({"id": len(images) + 1, "file_name": fn, "width": w, "height": h})
            for x, y, bw, bh in boxes:
                anns.append({"id": aid, "image_id": images[-1]["id"], "category_id": 1,
                             "bbox": [x, y, bw, bh], "area": bw * bh, "iscrowd": 0})
                aid += 1
        coco = {
            "info": {"description": "Mini COCO for test", "version": "1.0",
                     "contributor": "tester", "date_created": "2026-01-01"},
            "images": images, "annotations": anns,
            "categories": [{"id": 1, "name": "Sugarcane Seedling"}],
        }
        (root / "annotations" / f"{split}.json").write_text(
            json.dumps(coco), encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}


def build_mini_yolo(root: Path):
    """构建 YOLO mini 数据集。归一化坐标。train: 2 图 4 框；val: 1 图 1 框；test: 1 图 1 框。"""
    splits = {
        "train": [("img_t1.jpg", [[0.078125, 0.34375, 0.046875, 0.0625],
                                  [0.1953125, 0.1953125, 0.078125, 0.078125]]),
                  ("img_t2.jpg", [[0.5, 0.5, 0.1, 0.1], [0.3, 0.3, 0.1, 0.1]])],
        "val": [("img_v1.jpg", [[0.6, 0.6, 0.0625, 0.0625]])],
        "test": [("img_e1.jpg", [[0.7, 0.7, 0.15625, 0.15625]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    for split, imgs in splits.items():
        for fn, boxes in imgs:
            _make_jpg(root / "images" / split / fn)
            lbl = root / "labels" / split / (Path(fn).stem + ".txt")
            lbl.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"0 {xc} {yc} {w} {h}" for xc, yc, w, h in boxes]
            lbl.write_text("\n".join(lines), encoding="utf-8")
    cfg = {"path": "D:/stale/path", "train": "images/train", "val": "images/val",
           "test": "images/test", "nc": 1, "names": {0: "Sugarcane Seedling"}}
    (root / "mini.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}


def build_mini_voc(root: Path):
    """构建 VOC mini 数据集（{split}/images + {split}/annotations 布局）。
    train: 2 图 4 框；val: 1 图 1 框；test: 1 图 1 框。"""
    splits = {
        "train": [("img_t1.jpg", [[10, 20, 40, 60], [100, 100, 150, 150], [200, 200, 260, 260]]),
                  ("img_t2.jpg", [[5, 5, 25, 25]])],
        "val": [("img_v1.jpg", [[300, 300, 340, 340]])],
        "test": [("img_e1.jpg", [[400, 400, 500, 500]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    for split, imgs in splits.items():
        for fn, boxes in imgs:
            _make_jpg(root / split / "images" / fn)
            xml = root / split / "annotations" / (Path(fn).stem + ".xml")
            xml.parent.mkdir(parents=True, exist_ok=True)
            objs = "".join(
                f"<object><name>Sugarcane Seedling</name>"
                f"<bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin>"
                f"<xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object>"
                for x1, y1, x2, y2 in boxes)
            xml.write_text(
                f"<annotation><folder>images</folder><filename>{fn}</filename>"
                f"<path>G:/stale/{fn}</path>"
                f"<size><width>640</width><height>640</height><depth>3</depth></size>"
                f"{objs}</annotation>", encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}
