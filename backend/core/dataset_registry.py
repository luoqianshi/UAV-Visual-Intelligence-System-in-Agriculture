"""数据集注册中心：YAML 持久化 + 自动扫描 + CRUD + 图片索引 + 预览。

镜像 BatchRegistry 模式：datasets/datasets.yaml 就地持久化，启动扫描 datasets/ 自动注册。
"""
import io
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from PIL import Image

from config import DATASETS_DIR, DATASETS_YAML, IMAGE_EXTENSIONS, PROJECT_ROOT, \
    PREVIEW_MEDIUM_SIZE, THUMBNAIL_MAX_SIZE
from dataset_formats import detect_format

_DATASET_FIELD_ORDER = [
    "dataset_id", "name", "format", "source", "path", "classes",
    "splits", "image_count", "object_count", "origin_image_count",
    "image_size", "version", "description", "created_at", "status",
]


class _InlineList(list):
    """flow style 列表输出。"""
    pass


def _inline_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


yaml.add_representer(_InlineList, _inline_list_representer)


def _sanitize(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def _infer_name(folder_name: str, fmt: str) -> str:
    """推断数据集名：文件夹名以 _{fmt} 结尾则 → '{stem} ({FMT})'，否则用文件夹名。"""
    lower = folder_name.lower()
    suffixes = {f"_{fmt.lower()}", "_pascal-voc", "_voc"}
    for suf in suffixes:
        if lower.endswith(suf):
            stem = folder_name[: -len(suf)]
            return f"{stem} ({fmt})"
    return folder_name


class DatasetRegistry:
    def __init__(self, datasets_dir=DATASETS_DIR, yaml_path=DATASETS_YAML):
        self._datasets_dir = Path(datasets_dir)
        self._yaml_path = Path(yaml_path)
        self._datasets: Dict[str, dict] = {}
        self._ignored_folders: set = set()
        self._analyzer = None

    def set_analyzer(self, analyzer):
        self._analyzer = analyzer

    # ── 加载与持久化 ───────────────────────────────────────
    def load_from_yaml(self):
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for d in data.get("datasets", []) or []:
                self._datasets[d["dataset_id"]] = d
            self._ignored_folders = set(data.get("ignored_folders", []) or [])
        if self._auto_discover():
            self.save_to_yaml()

    def save_to_yaml(self):
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        datasets_list = [self._ordered(d) for d in self._datasets.values()]
        data = {"datasets": datasets_list,
                "ignored_folders": sorted(self._ignored_folders)}
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False,
                      default_flow_style=False, indent=2, width=1000)

    def _ordered(self, cfg: dict) -> dict:
        ordered = {}
        for k in _DATASET_FIELD_ORDER:
            if k in cfg:
                v = cfg[k]
                if k == "classes" and isinstance(v, list):
                    v = _InlineList(v)
                ordered[k] = v
        for k, v in cfg.items():
            if k not in ordered:
                ordered[k] = v
        return ordered

    def _auto_discover(self) -> bool:
        if not self._datasets_dir.is_dir():
            return False
        registered_paths = set()
        for cfg in self._datasets.values():
            try:
                registered_paths.add(str(self._resolve_path(cfg["path"]).resolve()))
            except Exception:
                pass
        added = False
        for entry in sorted(self._datasets_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name in self._ignored_folders:
                continue
            try:
                resolved = str(entry.resolve())
            except Exception:
                continue
            if resolved in registered_paths:
                continue
            fmt = detect_format(entry)
            if fmt is None:
                continue
            self._register_from_scan(entry, fmt)
            added = True
        return added

    def _register_from_scan(self, folder: Path, fmt: str):
        """自动发现注册（轻量统计）。"""
        summary = self._analyzer.scan(str(folder)) if self._analyzer else None
        name = _infer_name(folder.name, fmt)
        dataset_id = "dataset_" + _sanitize(folder.name).lower()
        dataset_id = self._ensure_unique_id(dataset_id)
        cfg = self._build_cfg(dataset_id, name, fmt, "imported",
                              str(self._to_relative(folder)), summary)
        self._datasets[dataset_id] = cfg
        # 自动发现也写 dataset_meta.json
        if self._analyzer:
            self._analyzer._write_meta(folder / "dataset_meta.json",
                                       self._meta_from_cfg(cfg, folder))

    def _build_cfg(self, dataset_id, name, fmt, source, rel_path, summary) -> dict:
        summary = summary or {}
        return {
            "dataset_id": dataset_id, "name": name, "format": fmt, "source": source,
            "path": rel_path, "classes": _InlineList(summary.get("classes", [])),
            "splits": summary.get("splits", {}),
            "image_count": summary.get("image_count", 0),
            "object_count": summary.get("object_count", 0),
            "origin_image_count": summary.get("origin_image_count", 0),
            "image_size": summary.get("image_size", ""),
            "version": summary.get("version", "1.0"),
            "description": summary.get("description", ""),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "ready",
        }

    def _meta_from_cfg(self, cfg, folder):
        return {"dataset_id": cfg["dataset_id"], "name": cfg["name"],
                "format": cfg["format"], "classes": list(cfg["classes"]),
                "splits": cfg["splits"], "image_count": cfg["image_count"],
                "object_count": cfg["object_count"],
                "origin_image_count": cfg["origin_image_count"],
                "image_size": cfg["image_size"], "version": cfg["version"],
                "source_path": cfg["path"], "layout": {},
                "report_cache": None, "report_cached_at": None,
                "generated_at": cfg["created_at"]}

    def _ensure_unique_id(self, dataset_id: str) -> str:
        if dataset_id not in self._datasets:
            return dataset_id
        i = 2
        while f"{dataset_id}_{i}" in self._datasets:
            i += 1
        return f"{dataset_id}_{i}"

    # ── 查询 ───────────────────────────────────────────────
    def list_datasets(self, fmt: Optional[str] = None) -> List[dict]:
        result = list(self._datasets.values())
        if fmt:
            result = [d for d in result if d["format"] == fmt]
        return sorted(result, key=lambda d: d["created_at"], reverse=True)

    def get_dataset(self, dataset_id: str) -> dict:
        if dataset_id not in self._datasets:
            raise KeyError(f"数据集不存在: {dataset_id}")
        return self._datasets[dataset_id]

    def format_dist(self) -> dict:
        dist = {"YOLO": 0, "COCO": 0, "VOC": 0}
        for d in self._datasets.values():
            f = d.get("format")
            dist[f] = dist.get(f, 0) + 1
        return dist

    # ── 路径工具 ───────────────────────────────────────────
    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _to_relative(self, abs_path: Path) -> str:
        try:
            return str(abs_path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")

    # 以下方法在 Task 7 实现
    def scan_path(self, path: str) -> dict:
        raise NotImplementedError

    def import_dataset(self, path: str, name=None, description=None) -> dict:
        raise NotImplementedError

    def delete_dataset(self, dataset_id: str, delete_files: bool = False):
        raise NotImplementedError

    def list_images(self, dataset_id, split, page, page_size) -> dict:
        raise NotImplementedError

    def get_image_preview(self, dataset_id, filename, split, size) -> bytes:
        raise NotImplementedError
