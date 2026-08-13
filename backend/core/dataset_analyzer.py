"""数据集分析器：格式识别 + 轻量统计 + 报告重统计 + 缓存。

scan() 做轻量统计（不解析全部框几何），compute_report() 做重统计并缓存到
dataset_meta.json.report_cache。
"""
import json
import logging
from collections import Counter
from pathlib import Path

from config import PROJECT_ROOT
from dataset_formats import detect_format, parse_coco, parse_voc, parse_yolo

logger = logging.getLogger(__name__)

_PARSERS = {"COCO": parse_coco, "YOLO": parse_yolo, "VOC": parse_voc}


class DatasetAnalyzer:
    def __init__(self, registry=None):
        self._registry = registry

    # ── 路径预检（轻量统计）──────────────────────────────
    def scan(self, path: str) -> dict:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if not p.exists():
            return self._invalid(f"路径不存在: {path}")
        if not p.is_dir():
            return self._invalid("指定路径不是文件夹")
        fmt = detect_format(p)
        if fmt is None:
            return self._invalid("无法识别数据集格式（非 COCO/YOLO/VOC 标准布局）")
        ir = _PARSERS[fmt](p)
        return self._summarize(fmt, ir, p)

    def _invalid(self, msg: str) -> dict:
        return {"valid": False, "format": None, "classes": [], "image_count": 0,
                "object_count": 0, "splits": {}, "origin_image_count": 0,
                "image_size": "", "version": "", "description": "", "message": msg}

    def _summarize(self, fmt: str, ir: dict, dataset_dir: Path) -> dict:
        classes = ir["classes"]
        splits = {}
        origin_stems = set()
        res_set = Counter()
        total_objs = 0
        for im in ir["images"]:
            sp = im["split"]
            s = splits.setdefault(sp, {"image_count": 0, "object_count": 0})
            s["image_count"] += 1
            s["object_count"] += len(im["boxes"])
            total_objs += len(im["boxes"])
            origin_stems.add(im["origin_stem"])
            res_set[f"{im['width']}x{im['height']}"] += 1
        image_size = res_set.most_common(1)[0][0] if res_set else ""
        meta = ir["meta"]
        return {
            "valid": True, "format": fmt, "classes": classes,
            "image_count": len(ir["images"]), "object_count": total_objs,
            "splits": splits, "origin_image_count": len(origin_stems),
            "image_size": image_size,
            "version": meta.get("version") or "1.0",
            "description": meta.get("description", ""),
            "message": f"识别为 {fmt} 格式，{len(ir['images'])} 张图片",
        }

    # compute_report 将在 Task 5 实现
    def compute_report(self, dataset_id: str, force: bool = False) -> dict:
        raise NotImplementedError
