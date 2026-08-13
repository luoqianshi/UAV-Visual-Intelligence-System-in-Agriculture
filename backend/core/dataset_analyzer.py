"""数据集分析器：格式识别 + 轻量统计 + 报告重统计 + 缓存。

scan() 做轻量统计（不解析全部框几何），compute_report() 做重统计并缓存到
dataset_meta.json.report_cache。
"""
import json
import logging
from collections import Counter
from pathlib import Path

from config import PROJECT_ROOT
from core.dataset_formats import detect_format, parse_coco, parse_voc, parse_yolo

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

    # ── 报告重统计 + 缓存 ──────────────────────────────────
    def compute_report(self, dataset_cfg, force: bool = False) -> dict:
        """dataset_cfg 可以是 dataset_id 字符串（需 registry）或配置 dict。"""
        cfg = self._resolve_cfg(dataset_cfg)
        dataset_dir = self._resolve_path(cfg["path"])
        meta_path = dataset_dir / "dataset_meta.json"
        meta = self._read_meta(meta_path)
        cache = (meta or {}).get("report_cache")
        if cache and not force:
            report = dict(cache)
            report["cached"] = True
            report["dataset_id"] = cfg["dataset_id"]
            return report
        ir = _PARSERS[cfg["format"]](dataset_dir)
        heavy = self._compute_heavy_stats(ir)
        splits = self._splits_from_ir(ir)
        report = {
            "dataset_id": cfg["dataset_id"],
            "summary": {
                "total_images": len(ir["images"]),
                "total_objects": sum(len(im["boxes"]) for im in ir["images"]),
                "origin_image_count": len({im["origin_stem"] for im in ir["images"]}),
                "non_empty_images": sum(1 for im in ir["images"] if im["boxes"]),
                "splits": splits,
            },
            "class_dist": heavy["class_dist"],
            "bbox_stats": heavy["bbox_stats"],
            "image_stats": heavy["image_stats"],
            "warnings": heavy["warnings"],
            "cached": False,
            "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        # 回写缓存
        meta = meta or {"dataset_id": cfg["dataset_id"]}
        meta["report_cache"] = {k: v for k, v in report.items() if k != "cached"}
        meta["report_cached_at"] = report["generated_at"]
        self._write_meta(meta_path, meta)
        return report

    def _resolve_cfg(self, dataset_cfg):
        if isinstance(dataset_cfg, dict):
            return dataset_cfg
        if self._registry is None:
            raise RuntimeError("analyzer 无 registry，无法按 id 查询")
        return self._registry.get_dataset(dataset_cfg)

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _splits_from_ir(self, ir: dict) -> dict:
        splits = {}
        for im in ir["images"]:
            s = splits.setdefault(im["split"], {"image_count": 0, "object_count": 0})
            s["image_count"] += 1
            s["object_count"] += len(im["boxes"])
        return splits

    def _compute_heavy_stats(self, ir: dict) -> dict:
        class_counter = Counter()
        resolutions = Counter()
        aspect_ratios = Counter()
        widths, heights, areas = [], [], []
        non_empty = 0
        for im in ir["images"]:
            resolutions[f"{im['width']}x{im['height']}"] += 1
            ar = round(im["width"] / im["height"], 2) if im["height"] else 0
            aspect_ratios[f"{ar:.2f}"] += 1
            if im["boxes"]:
                non_empty += 1
            for b in im["boxes"]:
                _, _, w, h = b["bbox"]
                widths.append(w)
                heights.append(h)
                areas.append(w * h)
                class_counter[b["class_name"]] += 1
        total_objs = sum(class_counter.values())
        class_dist = [{"name": n, "class_id": i, "count": c,
                       "pct": round(c / total_objs * 100, 2) if total_objs else 0}
                      for i, (n, c) in enumerate(sorted(class_counter.items()))]
        warnings = []
        if class_dist and total_objs:
            if class_dist[0]["pct"] > 90:
                warnings.append(
                    f"类别分布失衡：{class_dist[0]['name']} 占比 {class_dist[0]['pct']}% > 90%")
        # 面积直方图（20 桶）
        area_hist = self._histogram(areas, 20)
        # COCO small/medium/large
        size_dist = self._coco_size_dist(areas)
        bbox_stats = {
            "avg_width": round(sum(widths) / len(widths), 2) if widths else 0,
            "avg_height": round(sum(heights) / len(heights), 2) if heights else 0,
            "area_hist": area_hist,
            "size_dist": size_dist,
        }
        return {
            "class_dist": class_dist,
            "bbox_stats": bbox_stats,
            "image_stats": {"resolutions": dict(resolutions),
                            "aspect_ratios": dict(aspect_ratios)},
            "warnings": warnings,
            "non_empty_images": non_empty,
        }

    @staticmethod
    def _histogram(values, bins):
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi == lo:
            return [[[lo, hi], len(values)]]
        step = (hi - lo) / bins
        edges = [lo + i * step for i in range(bins + 1)]
        counts = [0] * bins
        for v in values:
            idx = min(int((v - lo) / step), bins - 1)
            counts[idx] += 1
        return [[[round(edges[i], 2), round(edges[i + 1], 2)], counts[i]]
                for i in range(bins)]

    @staticmethod
    def _coco_size_dist(areas):
        if not areas:
            return {"small": 0, "medium": 0, "large": 0}
        small = sum(1 for a in areas if a < 32 * 32)
        medium = sum(1 for a in areas if 32 * 32 <= a <= 96 * 96)
        large = sum(1 for a in areas if a > 96 * 96)
        total = len(areas)
        return {"small": round(small / total, 4),
                "medium": round(medium / total, 4),
                "large": round(large / total, 4)}

    @staticmethod
    def _read_meta(meta_path: Path):
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_meta(meta_path: Path, meta: dict):
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def invalidate_cache(self, dataset_dir: Path):
        """重新导入时失效报告缓存。"""
        meta_path = Path(dataset_dir) / "dataset_meta.json"
        meta = self._read_meta(meta_path)
        if meta:
            meta["report_cache"] = None
            meta["report_cached_at"] = None
            self._write_meta(meta_path, meta)
