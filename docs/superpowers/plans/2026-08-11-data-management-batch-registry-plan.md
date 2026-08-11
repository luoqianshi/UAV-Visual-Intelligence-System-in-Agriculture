# 数据管理模块（架次真实功能替代 Mock）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将数据管理模块从静态 mock 数据替换为基于本机文件系统的真实功能，实现架次 YAML 持久化、启动自动扫描 data/ 目录、图片分页浏览与动态缩略图。

**Architecture:** 后端参照现有 `ModelRegistry`（`backend/core/registry.py`）模式创建 `BatchRegistry` 类，通过 `data/batches.yaml` 持久化架次配置，启动时自动扫描 `data/` 目录注册已有批次；前端新建 `batches.ts` API 客户端，替换 3 个 Vue 视图中的 mock 调用，图片浏览改为分页+懒加载模式。

**Tech Stack:** Flask, PyYAML, Pillow (PIL), Vue 3 Composition API, Axios, TypeScript

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/config.py` | 修改 | 添加 DATA_DIR, BATCHES_YAML, IMAGE_EXTENSIONS 等常量 |
| `backend/core/batch_registry.py` | 新建 | BatchRegistry 类：YAML 加载/保存、自动扫描、CRUD、图片索引、缩略图生成 |
| `backend/core/engine.py` | 修改 | 添加 batch_registry 单例初始化与 getter |
| `backend/api/batches_api.py` | 修改 | 替换 mock 实现，对接 BatchRegistry 真实 API |
| `backend/tests/test_batch_registry.py` | 新建 | BatchRegistry 单元测试 |
| `frontend/src/api/batches.ts` | 新建 | 架次 API 客户端（参考 models.ts 模式） |
| `frontend/src/views/data/Batches.vue` | 修改 | 替换 mock store 为 batchesApi，字段映射，增删功能 |
| `frontend/src/views/data/BatchNew.vue` | 修改 | 真实路径扫描+表单提交，字段对齐 PRD |
| `frontend/src/views/data/BatchDetail.vue` | 修改 | 编辑功能+分页图片浏览+懒加载 Lightbox |
| `frontend/src/stores/mock.ts` | 修改 | 移除 batches 相关 state 和 fetchBatches 方法 |
| `frontend/src/api/mock.ts` | 修改 | 移除 Batch 类型和 batches 相关 API 方法 |

---

## Task 1: 更新 config.py 添加数据目录常量

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: 读取当前 config.py 内容，在 RESULTS_DIR 相关配置后添加数据目录常量**

在 `backend/config.py` 的 `RESULTS_DIR.mkdir...` 之前添加 DATA_DIR 等常量：

```python
DATA_DIR = PROJECT_ROOT / "data"
BATCHES_YAML = DATA_DIR / "batches.yaml"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_IMAGES_PER_BATCH = 2000
MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
THUMBNAIL_MAX_SIZE = 400
PREVIEW_MEDIUM_SIZE = 1920
CROP_NAME_MAP = {"sugarcane": "甘蔗", "corn": "玉米", "wheat": "小麦", "rice": "水稻"}
DEFAULT_DRONE_MODEL = "DJI Mavic 3 M"
DEFAULT_OVERLAP_FRONT = 0.8
DEFAULT_OVERLAP_SIDE = 0.7
```

并在文件末尾目录创建部分添加：

```python
DATA_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: 验证 Python 语法正确**

Run: `cd backend && python -c "from config import DATA_DIR, BATCHES_YAML, IMAGE_EXTENSIONS; print('DATA_DIR:', DATA_DIR); print('OK')"`
Expected: 打印 DATA_DIR 路径和 OK，无报错。

---

## Task 2: 创建 BatchRegistry 类

**Files:**
- Create: `backend/core/batch_registry.py`

- [ ] **Step 1: 创建 batch_registry.py，实现 BatchRegistry 类完整代码**

参考 `backend/core/registry.py` 的代码风格（OrderedDict、_InlineList、yaml representer、字段顺序排列等），创建完整实现：

```python
"""架次注册中心：YAML加载 + 自动扫描 + CRUD + 图片索引 + 动态缩略图生成。

参考 ModelRegistry（core/registry.py）的设计模式：
- YAML 持久化，字段顺序统一
- 启动时自动扫描 data/ 目录发现新架次
- 内存维护图片索引，避免重复磁盘扫描
"""
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from PIL import Image

from config import (
    BATCHES_YAML, CROP_NAME_MAP, DATA_DIR, DEFAULT_DRONE_MODEL,
    DEFAULT_OVERLAP_FRONT, DEFAULT_OVERLAP_SIDE, IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES, MAX_IMAGES_PER_BATCH, PREVIEW_MEDIUM_SIZE,
    THUMBNAIL_MAX_SIZE,
)

_BATCH_FIELD_ORDER = [
    "batch_id", "batch_name", "crop_type", "flight_date", "plot_name",
    "drone_model", "flight_altitude_m", "overlap_front", "overlap_side",
    "image_folder_path", "image_count", "total_size_bytes", "created_at",
    "image_formats", "status", "description",
]


class _InlineList(list):
    """标记为内联输出的列表（保持 ["JPEG"] 这种 flow 风格）"""
    pass


def _inline_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


yaml.add_representer(_InlineList, _inline_list_representer)


def _sanitize_name(name: str) -> str:
    """将名称转换为安全 ID 字符串（只保留字母数字下划线连字符）。"""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


class BatchRegistry:
    """架次注册中心。

    - 通过 YAML 描述所有已登记架次；
    - 启动时自动扫描 data/ 目录发现新架次并自动注册；
    - 内存维护图片索引（文件名、大小、尺寸），支持分页查询；
    - 动态生成缩略图/预览图，不缓存到磁盘。
    """

    def __init__(self, data_dir: Path = DATA_DIR, yaml_path: Path = BATCHES_YAML):
        self._data_dir = Path(data_dir)
        self._yaml_path = Path(yaml_path)
        self._batches: dict[str, dict] = {}
        self._image_index: dict[str, list[dict]] = {}
        self._ignored_folders: set[str] = set()

    def load_from_yaml(self) -> None:
        """从 YAML 加载架次配置，自动发现新架次，构建内存图片索引。"""
        # 1. 读取 YAML（不存在则初始化为空）
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            batches_list = data.get("batches", []) or []
            self._ignored_folders = set(data.get("ignored_folders", []) or [])
        else:
            batches_list = []
            self._ignored_folders = set()

        self._batches = {b["batch_id"]: b for b in batches_list}

        # 2. 扫描 data_dir 自动发现未注册的架次
        discovered = self._auto_discover_batches()
        newly_added = False
        for folder_path in discovered:
            folder_name = folder_path.name
            metadata = self._infer_metadata(folder_name, folder_path)
            images, count, total_bytes, formats = self._scan_images(folder_path)
            batch_id = f"batch_{_sanitize_name(folder_name)}"
            rel_path = self._to_relative_path(folder_path)
            now = datetime.now().isoformat(timespec="seconds")
            cfg = {
                "batch_id": batch_id,
                "batch_name": metadata["batch_name"],
                "crop_type": metadata["crop_type"],
                "flight_date": metadata["flight_date"],
                "plot_name": "",
                "drone_model": DEFAULT_DRONE_MODEL,
                "flight_altitude_m": metadata["flight_altitude_m"],
                "overlap_front": DEFAULT_OVERLAP_FRONT,
                "overlap_side": DEFAULT_OVERLAP_SIDE,
                "image_folder_path": rel_path,
                "image_count": count,
                "total_size_bytes": total_bytes,
                "created_at": now,
                "image_formats": _InlineList(formats),
                "status": "ready",
                "description": f"自动扫描注册：{metadata['crop_type']}，{metadata['flight_altitude_m'] or '?'}m高度采集",
            }
            self._batches[batch_id] = cfg
            self._image_index[batch_id] = images
            newly_added = True

        # 3. 对 YAML 中已有的架次（非自动发现）也构建图片索引
        for bid, cfg in self._batches.items():
            if bid not in self._image_index:
                folder = self._resolve_path(cfg["image_folder_path"])
                if folder.is_dir():
                    images, count, total_bytes, formats = self._scan_images(folder)
                    self._image_index[bid] = images
                    cfg["image_count"] = count
                    cfg["total_size_bytes"] = total_bytes
                    cfg["image_formats"] = _InlineList(formats)

        # 4. 如有新增，保存回 YAML
        if newly_added:
            self.save_to_yaml()

    def save_to_yaml(self) -> None:
        """将当前架次配置持久化到 YAML 文件。"""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        batches_list = [self._ordered_config(cfg) for cfg in self._batches.values()]
        data = {
            "batches": batches_list,
            "ignored_folders": sorted(list(self._ignored_folders)),
        }
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                data, f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                indent=2,
                width=1000,
            )

    def _ordered_config(self, cfg: dict) -> dict:
        """按标准字段顺序排列，确保 YAML 输出格式一致。"""
        ordered = {}
        for key in _BATCH_FIELD_ORDER:
            if key in cfg:
                val = cfg[key]
                if key == "image_formats" and isinstance(val, list):
                    val = _InlineList(sorted(set(val)))
                ordered[key] = val
        for key, val in cfg.items():
            if key not in ordered:
                ordered[key] = val
        return ordered

    def list_batches(self, crop_type: Optional[str] = None,
                     flight_date: Optional[str] = None,
                     plot_name: Optional[str] = None) -> list[dict]:
        """返回架次列表，支持过滤条件。"""
        result = []
        for cfg in self._batches.values():
            if crop_type and cfg.get("crop_type") != crop_type:
                continue
            if flight_date and cfg.get("flight_date") != flight_date:
                continue
            if plot_name and plot_name.lower() not in (cfg.get("plot_name") or "").lower():
                continue
            result.append(cfg)
        return result

    def get_summary(self) -> dict:
        """返回数据总览统计。"""
        all_batches = list(self._batches.values())
        total_batches = len(all_batches)
        total_images = sum(b.get("image_count", 0) for b in all_batches)
        total_size = sum(b.get("total_size_bytes", 0) for b in all_batches)
        formats_set = set()
        resolutions_set = set()
        for bid in self._batches:
            for img in self._image_index.get(bid, []):
                formats_set.add(img["format"])
                resolutions_set.add(f"{img['width']}x{img['height']}")
        return {
            "total_batches": total_batches,
            "total_images": total_images,
            "total_size_bytes": total_size,
            "resolutions": sorted(list(resolutions_set)),
            "formats": sorted(list(formats_set)),
        }

    def get_batch(self, batch_id: str) -> dict:
        """获取单个架次详情，不存在抛 KeyError。"""
        if batch_id not in self._batches:
            raise KeyError(f"架次不存在: {batch_id}")
        return self._batches[batch_id]

    def create_batch(self, config: dict) -> dict:
        """创建新架次（表单提交），校验后持久化。"""
        # 必填字段校验
        required = ["batch_name", "crop_type", "flight_date", "image_folder_path"]
        for field in required:
            if not config.get(field):
                raise ValueError(f"缺少必填字段: {field}")

        folder = self._resolve_path(config["image_folder_path"])
        if not folder.exists():
            raise ValueError(f"图片路径不存在或不可访问: {config['image_folder_path']}")
        if not folder.is_dir():
            raise ValueError("指定的路径不是文件夹")

        # 检查名称重名
        for existing in self._batches.values():
            if existing["batch_name"] == config["batch_name"]:
                raise ValueError(f"架次名称已存在: {config['batch_name']}")
            try:
                existing_resolved = self._resolve_path(existing["image_folder_path"])
                if existing_resolved == folder.resolve():
                    raise ValueError(f"该路径已被架次 {existing['batch_id']} 注册")
            except Exception:
                pass

        # 扫描图片
        images, count, total_bytes, formats = self._scan_images(folder)
        if count == 0:
            raise ValueError("指定路径下未找到合法图片文件")
        if count > MAX_IMAGES_PER_BATCH:
            raise ValueError(f"图片数量超过上限（{MAX_IMAGES_PER_BATCH}张），当前: {count}张")

        batch_id = f"batch_{_sanitize_name(config['batch_name'])}_{datetime.now().strftime('%H%M%S')}"
        # 确保 ID 唯一
        while batch_id in self._batches:
            batch_id = f"batch_{_sanitize_name(config['batch_name'])}_{datetime.now().strftime('%H%M%S%f')}"

        now = datetime.now().isoformat(timespec="seconds")
        rel_path = self._to_relative_path(folder)
        cfg = {
            "batch_id": batch_id,
            "batch_name": config["batch_name"],
            "crop_type": config["crop_type"],
            "flight_date": config["flight_date"],
            "plot_name": config.get("plot_name", ""),
            "drone_model": config.get("drone_model") or DEFAULT_DRONE_MODEL,
            "flight_altitude_m": config.get("flight_altitude_m"),
            "overlap_front": float(config.get("overlap_front", DEFAULT_OVERLAP_FRONT)),
            "overlap_side": float(config.get("overlap_side", DEFAULT_OVERLAP_SIDE)),
            "image_folder_path": rel_path,
            "image_count": count,
            "total_size_bytes": total_bytes,
            "created_at": now,
            "image_formats": _InlineList(formats),
            "status": "ready",
            "description": config.get("description", ""),
        }
        self._batches[batch_id] = cfg
        self._image_index[batch_id] = images
        self.save_to_yaml()
        return cfg

    def update_batch(self, batch_id: str, updates: dict) -> dict:
        """更新架次元数据（不可变字段会被忽略）。"""
        if batch_id not in self._batches:
            raise KeyError(f"架次不存在: {batch_id}")
        immutable = {"batch_id", "image_folder_path", "image_count",
                     "total_size_bytes", "created_at", "status"}
        cfg = self._batches[batch_id]
        for key, val in updates.items():
            if key in immutable:
                continue
            if val is not None:
                cfg[key] = val
        # 数值字段规范化
        if "overlap_front" in cfg and cfg["overlap_front"] is not None:
            cfg["overlap_front"] = float(cfg["overlap_front"])
        if "overlap_side" in cfg and cfg["overlap_side"] is not None:
            cfg["overlap_side"] = float(cfg["overlap_side"])
        if "flight_altitude_m" in cfg and cfg["flight_altitude_m"] is not None:
            cfg["flight_altitude_m"] = float(cfg["flight_altitude_m"])
        self.save_to_yaml()
        return cfg

    def delete_batch(self, batch_id: str) -> None:
        """删除架次登记（不删除原始文件）。自动扫描的架次加入忽略列表。"""
        if batch_id not in self._batches:
            raise KeyError(f"架次不存在: {batch_id}")
        cfg = self._batches[batch_id]
        folder_path = self._resolve_path(cfg["image_folder_path"])
        # 如果路径在 data_dir 下，加入忽略列表
        try:
            folder_path.resolve().relative_to(self._data_dir.resolve())
            self._ignored_folders.add(folder_path.name)
        except ValueError:
            pass  # 外部路径不加入忽略列表
        del self._batches[batch_id]
        self._image_index.pop(batch_id, None)
        self.save_to_yaml()

    def scan_path(self, folder_path_str: str) -> dict:
        """路径预检（表单扫描按钮）：不持久化，仅返回扫描结果。"""
        folder = self._resolve_path(folder_path_str)
        if not folder.exists():
            return {"valid": False, "image_count": 0, "total_size_bytes": 0,
                    "formats": [], "message": f"路径不存在: {folder_path_str}"}
        if not folder.is_dir():
            return {"valid": False, "image_count": 0, "total_size_bytes": 0,
                    "formats": [], "message": "指定路径不是文件夹"}
        images, count, total_bytes, formats = self._scan_images(folder)
        if count == 0:
            return {"valid": False, "image_count": 0, "total_size_bytes": 0,
                    "formats": [], "message": "未找到合法图片文件"}
        warnings = []
        if count > MAX_IMAGES_PER_BATCH:
            warnings.append(f"图片数量（{count}）超过上限{MAX_IMAGES_PER_BATCH}张")
        return {
            "valid": True,
            "image_count": count,
            "total_size_bytes": total_bytes,
            "formats": formats,
            "message": "; ".join(warnings) if warnings else f"发现 {count} 张图片",
        }

    def list_images(self, batch_id: str, page: int = 1, page_size: int = 50,
                    sort_by: str = "filename", order: str = "asc") -> dict:
        """分页获取架次下的图片列表。"""
        if batch_id not in self._batches:
            raise KeyError(f"架次不存在: {batch_id}")
        images = list(self._image_index.get(batch_id, []))
        # 排序
        reverse = order.lower() == "desc"
        if sort_by == "size":
            images.sort(key=lambda x: x["size_bytes"], reverse=reverse)
        else:
            images.sort(key=lambda x: x["filename"].lower(), reverse=reverse)
        total = len(images)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        end = start + page_size
        paged = images[start:end]
        # 构造 URL
        for img in paged:
            fname = img["filename"]
            img["thumbnail_url"] = f"/api/batches/{batch_id}/images/{fname}/preview?size=thumbnail"
            img["preview_url"] = f"/api/batches/{batch_id}/images/{fname}/preview?size=medium"
        return {
            "images": paged,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_image_preview(self, batch_id: str, filename: str, size: str = "thumbnail") -> bytes:
        """生成图片预览 JPEG 字节流。size: thumbnail(400px) / medium(1920px) / original。"""
        if batch_id not in self._batches:
            raise KeyError(f"架次不存在: {batch_id}")
        folder = self._resolve_path(self._batches[batch_id]["image_folder_path"])
        image_path = folder / filename
        if not image_path.is_file():
            raise FileNotFoundError(f"图片不存在: {filename}")
        if size == "original":
            with open(image_path, "rb") as f:
                return f.read()
        max_size = THUMBNAIL_MAX_SIZE if size == "thumbnail" else PREVIEW_MEDIUM_SIZE
        quality = 80 if size == "thumbnail" else 85
        return self._generate_thumbnail(image_path, max_size, quality)

    def _scan_images(self, folder_path: Path) -> tuple[list[dict], int, int, list[str]]:
        """扫描文件夹下所有合法图片，返回 (images_list, count, total_bytes, formats)。"""
        images = []
        total_bytes = 0
        formats_set = set()
        for entry in sorted(folder_path.iterdir()):
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue
            try:
                stat = entry.stat()
                if stat.st_size > MAX_IMAGE_SIZE_BYTES:
                    continue  # 跳过超限文件
                total_bytes += stat.st_size
                # 读取图片尺寸
                with Image.open(entry) as im:
                    width, height = im.size
                    fmt = (im.format or ext.lstrip('.').upper())
                formats_set.add(fmt)
                images.append({
                    "filename": entry.name,
                    "size_bytes": stat.st_size,
                    "width": width,
                    "height": height,
                    "format": fmt,
                })
            except Exception:
                continue  # 跳过无法读取的文件
        return images, len(images), total_bytes, sorted(list(formats_set))

    def _generate_thumbnail(self, image_path: Path, max_size: int, quality: int) -> bytes:
        """使用 Pillow 生成缩略图 JPEG 字节流。"""
        with Image.open(image_path) as im:
            im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
            im.thumbnail((max_size, max_size), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()

    def _auto_discover_batches(self) -> list[Path]:
        """扫描 data_dir 一级子目录，返回未注册且未忽略的有效图片文件夹。"""
        discovered = []
        if not self._data_dir.is_dir():
            return discovered
        # 收集已注册的路径
        registered_paths = set()
        for cfg in self._batches.values():
            try:
                registered_paths.add(str(self._resolve_path(cfg["image_folder_path"]).resolve()))
            except Exception:
                pass
        for entry in sorted(self._data_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith((".", "_")):
                continue
            if entry.name in self._ignored_folders:
                continue
            # 检查是否包含图片
            has_images = any(
                f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                for f in entry.iterdir()
            )
            if not has_images:
                continue
            try:
                resolved = str(entry.resolve())
            except Exception:
                continue
            if resolved in registered_paths:
                continue
            discovered.append(entry)
        return discovered

    def _infer_metadata(self, folder_name: str, folder_path: Path) -> dict:
        """从文件夹名推断元数据。"""
        # 尝试解析 {crop}_{date}_{altitude}m 格式
        pattern = r'^([a-zA-Z]+)_(\d{8})_(\d+)m$'
        m = re.match(pattern, folder_name)
        crop_type = "未知作物"
        flight_date = ""
        altitude = None
        batch_name = folder_name
        if m:
            crop_key = m.group(1).lower()
            crop_type = CROP_NAME_MAP.get(crop_key, crop_key)
            date_str = m.group(2)
            flight_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            altitude = float(m.group(3))
        else:
            # 使用文件夹 mtime 作为日期
            try:
                mtime = folder_path.stat().st_mtime
                flight_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except Exception:
                flight_date = datetime.now().strftime("%Y-%m-%d")
        return {
            "batch_name": batch_name,
            "crop_type": crop_type,
            "flight_date": flight_date,
            "flight_altitude_m": altitude,
        }

    def _resolve_path(self, path_str: str) -> Path:
        """将路径字符串解析为绝对 Path（相对路径相对 PROJECT_ROOT）。"""
        from config import PROJECT_ROOT
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _to_relative_path(self, abs_path: Path) -> str:
        """将绝对路径转换为相对 PROJECT_ROOT 的路径（如可能），否则返回绝对路径字符串。"""
        from config import PROJECT_ROOT
        try:
            rel = abs_path.resolve().relative_to(PROJECT_ROOT.resolve())
            return str(rel).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")
```

- [ ] **Step 2: 验证 Python 语法正确**

Run: `cd backend && python -c "from core.batch_registry import BatchRegistry; print('Import OK')"`
Expected: 打印 "Import OK"，无报错。

---

## Task 3: 编写 BatchRegistry 单元测试

**Files:**
- Create: `backend/tests/test_batch_registry.py`

- [ ] **Step 1: 创建测试文件**

```python
"""BatchRegistry 单元测试：YAML 加载 / 自动扫描 / CRUD / 图片索引 / 缩略图。

运行：cd backend && python -m pytest tests/test_batch_registry.py -v
"""
import io
import pytest
from pathlib import Path
from PIL import Image

from core.batch_registry import BatchRegistry


def _make_test_image(folder: Path, name: str, size=(100, 100), color=(255, 0, 0)):
    """在指定文件夹创建测试 JPEG 图片。"""
    img = Image.new("RGB", size, color)
    path = folder / name
    img.save(path, "JPEG")
    return path


def _make_batch_yaml(tmp_path: Path, batches=None, ignored=None):
    """写入临时 batches.yaml。"""
    import yaml
    content = {"batches": batches or [], "ignored_folders": ignored or []}
    yaml_file = tmp_path / "batches.yaml"
    yaml_file.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")
    return yaml_file


# ---------------------------------------------------------------------------
# 1. 空 YAML 加载 + 自动发现
# ---------------------------------------------------------------------------
def test_load_empty_yaml_and_autodiscover(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # 创建一个测试架次文件夹
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "DJI_0001.JPG")
    _make_test_image(batch_dir, "DJI_0002.JPG")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    batches = registry.list_batches()
    assert len(batches) == 1
    b = batches[0]
    assert b["batch_name"] == "sugarcane_20250419_5m"
    assert b["crop_type"] == "甘蔗"
    assert b["flight_date"] == "2025-04-19"
    assert b["flight_altitude_m"] == 5.0
    assert b["image_count"] == 2
    assert b["status"] == "ready"
    assert "JPEG" in b["image_formats"]
    # YAML 应已自动保存
    assert yaml_path.exists()


def test_autodiscover_skips_ignored_folders(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "DJI_0001.JPG")

    # 创建 YAML，标记该文件夹为已忽略
    yaml_path = _make_batch_yaml(tmp_path, ignored=["sugarcane_20250419_5m"])
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    assert len(registry.list_batches()) == 0


# ---------------------------------------------------------------------------
# 2. CRUD 操作
# ---------------------------------------------------------------------------
def test_create_and_get_batch(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    external_dir = tmp_path / "external_images"
    external_dir.mkdir()
    _make_test_image(external_dir, "test1.jpg")
    _make_test_image(external_dir, "test2.jpg")
    _make_test_image(external_dir, "test3.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    cfg = registry.create_batch({
        "batch_name": "test_batch",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(external_dir),
        "plot_name": "A区",
    })

    assert cfg["image_count"] == 3
    assert cfg["crop_type"] == "甘蔗"
    assert cfg["status"] == "ready"

    fetched = registry.get_batch(cfg["batch_id"])
    assert fetched["batch_name"] == "test_batch"
    assert fetched["plot_name"] == "A区"


def test_create_batch_invalid_path(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    with pytest.raises(ValueError, match="路径不存在"):
        registry.create_batch({
            "batch_name": "bad",
            "crop_type": "甘蔗",
            "flight_date": "2026-08-10",
            "image_folder_path": str(tmp_path / "nonexistent"),
        })


def test_update_batch(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "t.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "update_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })
    bid = cfg["batch_id"]

    updated = registry.update_batch(bid, {"plot_name": "B区", "description": "更新了描述"})
    assert updated["plot_name"] == "B区"
    assert updated["description"] == "更新了描述"
    # batch_id 和 image_folder_path 不可变
    assert updated["batch_id"] == bid
    assert updated["image_count"] == 1


def test_delete_batch_autodiscovered_adds_to_ignored(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "dji.JPG")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    batches = registry.list_batches()
    assert len(batches) == 1
    bid = batches[0]["batch_id"]

    registry.delete_batch(bid)
    assert len(registry.list_batches()) == 0
    # 重新加载，该文件夹应被忽略
    registry2 = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry2.load_from_yaml()
    assert len(registry2.list_batches()) == 0


# ---------------------------------------------------------------------------
# 3. 图片列表分页
# ---------------------------------------------------------------------------
def test_list_images_pagination(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "imgs"
    ext_dir.mkdir()
    for i in range(15):
        _make_test_image(ext_dir, f"IMG_{i:03d}.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "pag_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })

    # 默认 page_size=50，一页显示全部
    result = registry.list_images(cfg["batch_id"], page=1, page_size=50)
    assert result["total"] == 15
    assert len(result["images"]) == 15

    # page_size=5
    result = registry.list_images(cfg["batch_id"], page=1, page_size=5)
    assert result["total"] == 15
    assert result["total_pages"] == 3
    assert len(result["images"]) == 5
    assert result["images"][0]["thumbnail_url"].startswith("/api/batches/")


# ---------------------------------------------------------------------------
# 4. 缩略图生成
# ---------------------------------------------------------------------------
def test_generate_thumbnail(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "imgs"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "test.jpg", size=(800, 600))

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "thumb_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })

    thumb = registry.get_image_preview(cfg["batch_id"], "test.jpg", size="thumbnail")
    assert len(thumb) > 0
    # 验证是有效 JPEG
    img = Image.open(io.BytesIO(thumb))
    assert img.format == "JPEG"
    assert max(img.size) <= 400


# ---------------------------------------------------------------------------
# 5. 路径预检扫描
# ---------------------------------------------------------------------------
def test_scan_path_valid(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "scan_me"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "a.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    result = registry.scan_path(str(ext_dir))
    assert result["valid"] is True
    assert result["image_count"] == 1


def test_scan_path_nonexistent(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    result = registry.scan_path(str(tmp_path / "no_such_dir"))
    assert result["valid"] is False
```

- [ ] **Step 2: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/test_batch_registry.py -v`
Expected: 全部 PASS（大约 8-10 个测试用例）。

---

## Task 4: 更新 engine.py 添加 batch_registry 单例

**Files:**
- Modify: `backend/core/engine.py`

- [ ] **Step 1: 在 engine.py 中添加 batch_registry 初始化**

在 `registry = None` 后面添加 `batch_registry = None`，在 `init_engines()` 中 registry 初始化之后添加 batch_registry 初始化，并添加 getter 函数：

修改后的 engine.py 关键部分（完整文件）：

```python
"""引擎单例容器：集中持有 registry / batch_registry / detector / counter / task_manager。

通过 init_engines() 一次性初始化，get_*() 在各处取用。

设计要点：registry 仅依赖 PyYAML，与 cv2/torch/ultralytics 解耦——
即便推理依赖缺失，模型管理（列表/注册/热切换）仍可正常工作，
检测/计数 API 以降级模式返回提示而非 500（见 README §环境要求）。
"""
import logging

from config import (BATCHES_YAML, DATA_DIR, LRU_CACHE_SIZE, MAX_WORKERS,
                    MODELS_DIR, MODELS_YAML)
from core.batch_registry import BatchRegistry
from core.registry import ModelRegistry
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)

registry = None
batch_registry = None
detector = None
counter = None
task_manager = None


def init_engines():
    """初始化全部引擎单例。

    - registry 从 models.yaml 加载配置（仅解析 YAML，不依赖 cv2/torch），
      始终优先初始化，确保模型管理/列表/注册可用；
    - batch_registry 从 batches.yaml 加载架次配置并自动扫描 data/，仅依赖
      PyYAML + Pillow，始终初始化；
    - task_manager 仅依赖标准库，同样始终初始化；
    - detector / counter 依赖 cv2/numpy/ultralytics，在独立 try/except 中
      初始化：缺失时降级（detector/counter 保持 None），仅影响检测/计数
      推理，不影响模型管理与 mock 页面。
    """
    global registry, batch_registry, detector, counter, task_manager

    # ① 模型注册中心：仅依赖 PyYAML，必须成功
    registry = ModelRegistry(str(MODELS_YAML), str(MODELS_DIR), lru_size=LRU_CACHE_SIZE)
    registry.load_from_yaml()

    # ② 架次注册中心：仅依赖 PyYAML + Pillow，必须成功
    batch_registry = BatchRegistry(DATA_DIR, BATCHES_YAML)
    batch_registry.load_from_yaml()

    # ③ 任务管理器：仅依赖标准库
    task_manager = TaskManager(max_workers=MAX_WORKERS)

    # ④ 检测/计数引擎：依赖 cv2/numpy/ultralytics，缺失时降级
    try:
        from core.counter import CountingEngine
        from core.detector import DetectionEngine
        detector = DetectionEngine(registry)
        counter = CountingEngine(detector, task_manager)
    except Exception as exc:
        logger.warning(
            "检测/计数引擎初始化失败（推理功能不可用，模型管理正常）：%s", exc
        )


def get_registry():
    return registry


def get_batch_registry():
    return batch_registry


def get_detector():
    return detector


def get_counter():
    return counter


def get_task_manager():
    return task_manager
```

- [ ] **Step 2: 验证导入正确**

Run: `cd backend && python -c "from core.engine import init_engines, get_batch_registry; init_engines(); br = get_batch_registry(); print('Batches loaded:', len(br.list_batches()))"`
Expected: 打印 "Batches loaded: 3"（自动发现 data/ 下 3 个批次），无报错。

---

## Task 5: 替换 batches_api.py 为真实 API 实现

**Files:**
- Modify: `backend/api/batches_api.py`

- [ ] **Step 1: 完全替换 batches_api.py 内容**

```python
"""原始架次 API：架次 CRUD、图片列表分页、动态缩略图预览。

所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
from flask import Blueprint, Response, jsonify, request, send_file

from core.engine import get_batch_registry

batches_bp = Blueprint("batches", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


@batches_bp.route("/api/batches", methods=["GET"])
def list_batches():
    """GET /api/batches → 架次列表，支持过滤。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    crop_type = request.args.get("crop_type") or None
    flight_date = request.args.get("flight_date") or None
    plot_name = request.args.get("plot_name") or None
    try:
        batches = br.list_batches(crop_type=crop_type, flight_date=flight_date, plot_name=plot_name)
        summary = br.get_summary()
    except Exception as exc:
        return _error(f"读取架次列表失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": {"batches": batches, "total": len(batches), "summary": summary},
        "message": "获取架次列表成功",
    })


@batches_bp.route("/api/batches", methods=["POST"])
def create_batch():
    """POST /api/batches → 登记新架次。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    try:
        cfg = br.create_batch(body)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error(f"创建架次失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": {
            "batch_id": cfg["batch_id"],
            "image_count": cfg["image_count"],
            "total_size_mb": round(cfg["total_size_bytes"] / (1024 * 1024), 1),
        },
        "message": "架次登记成功",
    }), 201


@batches_bp.route("/api/batches/<batch_id>", methods=["GET"])
def get_batch(batch_id):
    """GET /api/batches/<batch_id> → 单个架次详情。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        batch = br.get_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    return jsonify({
        "success": True,
        "data": batch,
        "message": "获取架次详情成功",
    })


@batches_bp.route("/api/batches/<batch_id>", methods=["PUT"])
def update_batch(batch_id):
    """PUT /api/batches/<batch_id> → 更新架次元数据。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    try:
        cfg = br.update_batch(batch_id, body)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    except ValueError as exc:
        return _error(str(exc), 400)
    return jsonify({
        "success": True,
        "data": cfg,
        "message": "架次更新成功",
    })


@batches_bp.route("/api/batches/<batch_id>", methods=["DELETE"])
def delete_batch(batch_id):
    """DELETE /api/batches/<batch_id> → 删除架次登记（不删除原始文件）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        br.delete_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    return jsonify({
        "success": True,
        "data": None,
        "message": "架次已删除（原始文件未删除）",
    })


@batches_bp.route("/api/batches/<batch_id>/images", methods=["GET"])
def list_batch_images(batch_id):
    """GET /api/batches/<batch_id>/images → 该架次下的图片列表（分页）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        br.get_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    sort_by = request.args.get("sort_by", "filename")
    order = request.args.get("order", "asc")
    try:
        result = br.list_images(batch_id, page=page, page_size=page_size, sort_by=sort_by, order=order)
    except Exception as exc:
        return _error(f"读取图片列表失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": result,
        "message": "获取图片列表成功",
    })


@batches_bp.route("/api/batches/<batch_id>/images/<path:filename>/preview", methods=["GET"])
def batch_image_preview(batch_id, filename):
    """GET /api/batches/<batch_id>/images/<file>/preview → 图片预览（缩略图/中图/原图）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    size = request.args.get("size", "thumbnail")
    if size not in ("thumbnail", "medium", "original"):
        size = "thumbnail"
    try:
        img_bytes = br.get_image_preview(batch_id, filename, size=size)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    except FileNotFoundError:
        return _error(f"图片不存在: {filename}", 404)
    except Exception as exc:
        return _error(f"读取图片失败: {exc}", 500)
    resp = Response(img_bytes, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@batches_bp.route("/api/batches/scan", methods=["POST"])
def scan_path():
    """POST /api/batches/scan → 路径预检扫描。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("image_folder_path", "")
    if not path:
        return _error("缺少 image_folder_path 参数", 400)
    try:
        result = br.scan_path(path)
    except Exception as exc:
        return _error(f"扫描失败: {exc}", 500)
    status = 200 if result["valid"] else 400
    return jsonify({
        "success": result["valid"],
        "data": result,
        "message": result.get("message", ""),
    }), status
```

- [ ] **Step 2: 验证后端 API 可启动**

Run: `cd backend && python -c "from app import create_app; app = create_app(); print('App created successfully')"`
Expected: 打印 "App created successfully"，无报错。

- [ ] **Step 3: 快速测试 API 端到端**

启动后端（在一个终端运行 `cd backend && python app.py`），然后在另一个终端：
Run: `curl -s http://localhost:5000/api/batches | python -m json.tool`
Expected: 返回包含 3 个架次的 JSON，success=true。

测试完毕后停止后端服务器。

---

## Task 6: 创建前端 batches.ts API 客户端

**Files:**
- Create: `frontend/src/api/batches.ts`

- [ ] **Step 1: 创建 batches.ts**

参考 `frontend/src/api/models.ts` 的 axios 模式和 client.ts 的拦截器使用：

```typescript
import client from './client'

export interface Batch {
  batch_id: string
  batch_name: string
  crop_type: string
  flight_date: string
  plot_name?: string
  drone_model?: string
  flight_altitude_m?: number
  overlap_front?: number
  overlap_side?: number
  image_folder_path: string
  image_count: number
  total_size_bytes: number
  created_at: string
  image_formats: string[]
  status: string
  description?: string
}

export interface BatchSummary {
  total_batches: number
  total_images: number
  total_size_bytes: number
  resolutions: string[]
  formats: string[]
}

export interface BatchImage {
  filename: string
  size_bytes: number
  width: number
  height: number
  format: string
  thumbnail_url: string
  preview_url: string
}

export interface BatchListResponse {
  batches: Batch[]
  total: number
  summary: BatchSummary
}

export interface BatchImageListResponse {
  images: BatchImage[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ScanResult {
  valid: boolean
  image_count: number
  total_size_bytes: number
  formats: string[]
  message?: string
}

export interface CreateBatchResponse {
  batch_id: string
  image_count: number
  total_size_mb: number
}

export const batchesApi = {
  list: (params?: { crop_type?: string; flight_date?: string; plot_name?: string }) =>
    client.get<unknown, { data: BatchListResponse }>('/batches', { params }),

  get: (batchId: string) =>
    client.get<unknown, { data: Batch }>(`/batches/${batchId}`),

  create: (data: Partial<Batch> & { image_folder_path: string }) =>
    client.post<unknown, { data: CreateBatchResponse }>('/batches', data),

  update: (batchId: string, data: Partial<Batch>) =>
    client.put<unknown, { data: Batch }>(`/batches/${batchId}`, data),

  delete: (batchId: string) =>
    client.delete<unknown, any>(`/batches/${batchId}`),

  listImages: (batchId: string, params?: { page?: number; page_size?: number; sort_by?: string; order?: string }) =>
    client.get<unknown, { data: BatchImageListResponse }>(`/batches/${batchId}/images`, { params }),

  imagePreviewUrl: (batchId: string, filename: string, size: 'thumbnail' | 'medium' | 'original' = 'thumbnail') =>
    `/api/batches/${batchId}/images/${encodeURIComponent(filename)}/preview?size=${size}`,

  scanPath: (image_folder_path: string) =>
    client.post<unknown, { data: ScanResult }>('/batches/scan', { image_folder_path }),
}
```

- [ ] **Step 2: 验证 TypeScript 编译通过**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无 batches.ts 相关错误输出。

---

## Task 7: 更新 Batches.vue（架次列表页）

**Files:**
- Modify: `frontend/src/views/data/Batches.vue`

- [ ] **Step 1: 替换 Batches.vue 内容**

关键变更：
- 移除 useMockStore，改用 batchesApi
- 字段名映射（id→batch_id, name→batch_name, altitude_m→flight_altitude_m, location/plot_id→plot_name）
- 总览数据从 API summary 获取
- 添加删除功能（带确认弹窗）
- 替换 Font Awesome 图标为 SVG Icon 组件

```vue
<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi, type Batch } from '@/api/batches'
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const router = useRouter()

const batches = ref<Batch[]>([])
const summary = ref({ total_batches: 0, total_images: 0, total_size_bytes: 0, resolutions: [] as string[], formats: [] as string[] })
const loading = ref(false)
const searchName = ref('')
const filterCrop = ref('')
const errorMsg = ref('')

const crops = computed(() => {
  const set = new Set<string>()
  batches.value.forEach((b) => set.add(b.crop_type))
  return Array.from(set)
})

const totalSizeGb = computed(() => (summary.value.total_size_bytes / (1024 ** 3)).toFixed(2))
const resolutionLabel = computed(() => summary.value.resolutions[0] || '-')
const primaryCrop = computed(() => summary.value.formats.length > 0 ? [...new Set(batches.value.map(b => b.crop_type))].join('、') : '-')

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process') || s.includes('进行') || s.includes('run'))
    return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail') || s.includes('错误') || s.includes('error'))
    return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('接入') || s.includes('完成') || s.includes('publish'))
    return { cls: 'badge-success', label: '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

async function applyFilters() {
  errorMsg.value = ''
  loading.value = true
  try {
    const res = await batchesApi.list({
      crop_type: filterCrop.value || undefined,
    })
    let list = res.batches
    if (searchName.value) {
      const q = searchName.value.toLowerCase()
      list = list.filter(b => b.batch_name.toLowerCase().includes(q) || (b.plot_name || '').toLowerCase().includes(q))
    }
    batches.value = list
    summary.value = res.summary
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchName.value = ''
  filterCrop.value = ''
  applyFilters()
}

async function deleteBatch(b: Batch) {
  if (!confirm(`确定要删除架次「${b.batch_name}」吗？\n（原始图片文件不会被删除）`)) return
  try {
    await batchesApi.delete(b.batch_id)
    await applyFilters()
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

onMounted(applyFilters)

function goDetail(b: Batch) {
  router.push(`/data/batches/${b.batch_id}`)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / (1024 ** 2)).toFixed(1) + ' MB'
  return (bytes / (1024 ** 3)).toFixed(2) + ' GB'
}
</script>

<template>
  <AppLayout>
    <!-- 头部 -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据管理 · 原始飞行数据</div>
        <h1 class="text-2xl font-semibold text-ink-primary">原始架次</h1>
        <p class="text-sm text-ink-secondary mt-1">
          按架次浏览本机路径下的大田农作物原始图像 · 每个架次文件夹代表一次拍摄
        </p>
      </div>
      <router-link
        to="/data/batch-new"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <Icon name="xi-import" :size="14" /> 新建架次
      </router-link>
    </div>

    <!-- 原始飞行数据总览 -->
    <div class="bg-white border border-surface-border rounded-card p-5 mb-6">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
            <Icon name="xi-sortie" :size="16" />
          </div>
          <h2 class="text-sm font-semibold text-ink-primary">原始飞行数据总览</h2>
        </div>
      </div>
      <div class="grid grid-cols-4 gap-4">
        <div>
          <div class="text-xs text-ink-tertiary">架次数</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ summary.total_batches }} <span class="text-sm text-ink-tertiary font-normal">个</span>
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">载入图片总数</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ summary.total_images }} <span class="text-sm text-ink-tertiary font-normal">张</span>
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">作物类型</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ primaryCrop || '-' }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">总大小 / 格式</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ totalSizeGb }} <span class="text-sm text-ink-tertiary font-normal">GB</span>
          </div>
          <div class="text-xs text-ink-tertiary mt-0.5">{{ summary.formats.join('、') || '-' }} · {{ resolutionLabel }}</div>
        </div>
      </div>
    </div>

    <!-- 检索栏 -->
    <div class="bg-white border border-surface-border rounded-card p-4 mb-4">
      <div class="grid grid-cols-4 gap-3">
        <div class="relative">
          <Icon name="xi-search" :size="12" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
          <input
            v-model="searchName"
            type="text"
            placeholder="架次名称 / 地块"
            class="w-full pl-8 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
          />
        </div>
        <select
          v-model="filterCrop"
          @change="applyFilters"
          class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm text-ink-secondary"
        >
          <option value="">全部作物</option>
          <option v-for="c in crops" :key="c" :value="c">{{ c }}</option>
        </select>
        <div></div>
        <div class="flex gap-2">
          <button
            @click="applyFilters"
            class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center justify-center gap-1.5"
          >
            <Icon name="xi-search" :size="12" /> 搜索
          </button>
          <button
            @click="resetFilters"
            class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-secondary"
          >
            重置
          </button>
        </div>
      </div>
    </div>

    <!-- 架次列表表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-2.5 px-5 font-medium">架次名称 / ID</th>
            <th class="text-left py-2.5 px-5 font-medium">作物</th>
            <th class="text-left py-2.5 px-5 font-medium">飞行日期</th>
            <th class="text-left py-2.5 px-5 font-medium">地块</th>
            <th class="text-left py-2.5 px-5 font-medium">机型</th>
            <th class="text-left py-2.5 px-5 font-medium">高度</th>
            <th class="text-right py-2.5 px-5 font-medium">图片数</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-right py-2.5 px-5 font-medium w-28">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="loading">
            <td colspan="9" class="py-10 text-center text-ink-tertiary text-sm">
              <Icon name="xi-sparkle" :size="16" class="animate-spin inline mr-2" /> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="9" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2">{{ errorMsg }}</div>
              <button @click="applyFilters" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="batches.length === 0">
            <td colspan="9" class="py-12 text-center text-ink-tertiary">
              <Icon name="xi-database" :size="32" class="mx-auto mb-2 opacity-40" />
              <div class="text-sm">暂无架次记录</div>
            </td>
          </tr>
          <tr
            v-for="b in batches"
            v-else
            :key="b.batch_id"
            class="border-t border-surface-border cursor-pointer"
            @click="goDetail(b)"
          >
            <td class="py-3 px-5">
              <div class="font-medium text-ink-primary hover:text-brand-700">{{ b.batch_name }}</div>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ b.batch_id }}</div>
            </td>
            <td class="py-3 px-5"><span class="tag tag-green">{{ b.crop_type }}</span></td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.flight_date }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.plot_name || '-' }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.drone_model || '-' }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.flight_altitude_m ? b.flight_altitude_m + ' m' : '-' }}</td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ b.image_count }}</td>
            <td class="py-3 px-5">
              <span class="badge" :class="statusBadge(b.status).cls">{{ statusBadge(b.status).label }}</span>
            </td>
            <td class="py-3 px-5 text-right" @click.stop>
              <router-link :to="`/data/batches/${b.batch_id}`" class="text-xs text-brand-700 hover:underline mr-2">查看</router-link>
              <button @click="deleteBatch(b)" class="text-xs text-red-500 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
      <Icon name="xi-grid" :size="12" class="text-brand-700" />
      共 {{ batches.length }} 个架次 · 点击行可进入架次详情查看元数据与图像
    </div>
  </AppLayout>
</template>
```

- [ ] **Step 2: 检查 Icon 组件的 props 确认正确**

Read: `frontend/src/components/common/Icon.vue` 确认 props（name, size 等），如果 Icon 组件使用不同的 prop 名（如 icon 而非 name），则相应调整模板中的用法。

---

## Task 8: 更新 BatchNew.vue（新建架次页）

**Files:**
- Modify: `frontend/src/views/data/BatchNew.vue`

- [ ] **Step 1: 替换 BatchNew.vue 内容**

关键变更：使用 batchesApi.scanPath 和 batchesApi.create，字段对齐 PRD，扫描真实化，提交后跳转详情页。

```vue
<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi } from '@/api/batches'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const form = ref({
  batch_name: '',
  crop_type: '甘蔗',
  flight_date: new Date().toISOString().slice(0, 10),
  plot_name: '',
  drone_model: 'DJI Mavic 3 M',
  flight_altitude_m: 5,
  description: '',
})
const imagePath = ref('')
const overlapFront = ref(0.8)
const overlapSide = ref(0.7)

const submitting = ref(false)
const scanning = ref(false)
const successMsg = ref('')
const errorMsg = ref('')
const scanResult = ref<{ valid: boolean; image_count: number; total_size_bytes: number; formats: string[]; message?: string } | null>(null)

const cropOptions = ['甘蔗', '玉米', '小麦', '水稻']
const droneOptions = ['DJI Mavic 3 M', 'DJI Mavic 3', 'DJI Phantom 4 Pro', '其他']

const canSubmit = computed(() =>
  form.value.batch_name && form.value.crop_type && form.value.flight_date &&
  imagePath.value && scanResult.value?.valid
)

async function doScan() {
  if (!imagePath.value) {
    errorMsg.value = '请输入图片文件夹路径'
    return
  }
  scanning.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    scanResult.value = await batchesApi.scanPath(imagePath.value)
    if (!scanResult.value.valid) {
      errorMsg.value = scanResult.value.message || '路径无效'
    }
  } catch (e: any) {
    errorMsg.value = e.message || '扫描失败'
    scanResult.value = null
  } finally {
    scanning.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const res = await batchesApi.create({
      ...form.value,
      image_folder_path: imagePath.value,
      overlap_front: overlapFront.value,
      overlap_side: overlapSide.value,
    })
    successMsg.value = '架次登记成功'
    setTimeout(() => {
      router.push(`/data/batches/${res.batch_id}`)
    }, 800)
  } catch (e: any) {
    errorMsg.value = e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  form.value = {
    batch_name: '', crop_type: '甘蔗', flight_date: new Date().toISOString().slice(0, 10),
    plot_name: '', drone_model: 'DJI Mavic 3 M', flight_altitude_m: 5, description: '',
  }
  imagePath.value = ''
  overlapFront.value = 0.8
  overlapSide.value = 0.7
  scanResult.value = null
  successMsg.value = ''
  errorMsg.value = ''
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / (1024 ** 2)).toFixed(1) + ' MB'
  return (bytes / (1024 ** 3)).toFixed(2) + ' GB'
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/batches" class="hover:text-brand-700">数据管理 / 原始架次</router-link>
      <Icon name="xi-grid" :size="8" />
      <span class="text-ink-primary">登记新架次</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">注册新架次</h1>
    <p class="text-sm text-ink-secondary mb-6">登记 UAV 采集架次元数据与本机图片文件夹路径，建立标准化的架次记录</p>

    <!-- 成功提示 -->
    <div
      v-if="successMsg"
      class="mb-5 bg-brand-50 border border-brand-300 rounded-card p-4 flex items-start gap-3"
    >
      <Icon name="xi-validate" :size="16" class="text-brand-700 mt-0.5" />
      <div class="flex-1">
        <div class="text-sm text-brand-700 font-medium">{{ successMsg }}</div>
        <div class="mt-2 flex gap-2">
          <span class="text-xs text-ink-tertiary">正在跳转…</span>
        </div>
      </div>
    </div>
    <!-- 错误提示 -->
    <div v-if="errorMsg" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 flex items-start gap-3">
      <Icon name="xi-bell" :size="16" class="text-red-600 mt-0.5" />
      <div class="text-sm text-red-600">{{ errorMsg }}</div>
    </div>

    <div class="grid grid-cols-3 gap-5">
      <div class="col-span-2 space-y-5">
        <!-- 基本信息 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">基本信息</h2>
          <p class="text-xs text-ink-tertiary mb-5">为架次命名并登记 UAV 采集参数</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">架次名称 <span class="text-red-500">*</span></label>
              <input v-model="form.batch_name" type="text" placeholder="如：sugarcane_20260805_001" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
              <p class="text-xs text-ink-tertiary mt-1.5">建议格式：<code class="px-1 py-0.5 bg-surface-hover rounded">作物_采集日期_编号</code></p>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">作物类型 <span class="text-red-500">*</span></label>
                <select v-model="form.crop_type" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm">
                  <option v-for="c in cropOptions" :key="c" :value="c">{{ c }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">采集日期 <span class="text-red-500">*</span></label>
                <input v-model="form.flight_date" type="date" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">地块名称</label>
                <input v-model="form.plot_name" type="text" placeholder="如：A区" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                <p class="text-xs text-ink-tertiary mt-1.5">采集地块标识（可选）</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">飞行高度（米）</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.flight_altitude_m" type="number" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">m</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 图片文件夹路径 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">图片文件夹路径</h2>
          <p class="text-xs text-ink-tertiary mb-5">输入本机存放该架次图片的文件夹绝对路径，系统将校验并扫描索引</p>
          <div class="flex gap-2">
            <div class="flex-1 relative">
              <Icon name="xi-folder" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
              <input v-model="imagePath" type="text" placeholder="如：D:/data/sugarcane_images" class="w-full pl-9 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
            </div>
            <button @click="doScan" :disabled="scanning" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium inline-flex items-center gap-1.5">
              <Icon name="xi-search" :size="12" /> {{ scanning ? '扫描中…' : '扫描' }}
            </button>
          </div>
          <p class="text-xs text-ink-tertiary mt-2 flex items-center gap-1.5">
            <Icon name="xi-grid" :size="12" />
            路径必须为本机绝对路径；支持 .jpg/.jpeg/.png/.bmp/.tif/.tiff；单架次 ≤2000 张，单张 ≤50MB
          </p>
          <div v-if="scanResult && scanResult.valid" class="mt-4 pt-4 border-t border-surface-border">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs font-medium text-ink-primary">扫描结果</div>
              <span class="text-xs text-brand-700 inline-flex items-center gap-1"><Icon name="xi-validate" :size="12" /> 路径有效可读</span>
            </div>
            <div class="grid grid-cols-3 gap-3 mb-3">
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">图片数量</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ scanResult.image_count }}</div></div>
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">总大小</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ formatBytes(scanResult.total_size_bytes) }}</div></div>
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">格式</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ scanResult.formats.join('、') }}</div></div>
            </div>
          </div>
        </div>

        <!-- 采集设备与航摄参数 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">采集设备与航摄参数</h2>
          <p class="text-xs text-ink-tertiary mb-5">记录无人机型号与航摄重叠率（可选）</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">无人机型号</label>
              <select v-model="form.drone_model" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm">
                <option v-for="d in droneOptions" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">航向重叠率</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="overlapFront" type="number" step="0.05" min="0" max="1" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">旁向重叠率</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="overlapSide" type="number" step="0.05" min="0" max="1" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
              <textarea v-model="form.description" rows="2" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm resize-none focus:outline-none focus:border-brand-300"></textarea>
            </div>
          </div>
        </div>
      </div>

      <!-- 配置摘要 -->
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">配置摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between"><span class="text-ink-tertiary">架次名称</span><span class="text-ink-primary font-medium">{{ form.batch_name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span class="text-ink-primary">{{ form.crop_type }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">采集日期</span><span class="text-ink-primary">{{ form.flight_date || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">地块名称</span><span class="text-ink-primary">{{ form.plot_name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">飞行高度</span><span class="text-ink-primary">{{ form.flight_altitude_m }} m</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">机型</span><span class="text-ink-primary">{{ form.drone_model }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">航向/旁向</span><span class="text-ink-primary">{{ overlapFront }} / {{ overlapSide }}</span></div>
            <div class="border-t border-surface-border my-1.5"></div>
            <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">图片路径</span><span class="text-ink-primary font-mono text-[11px] text-right break-all">{{ imagePath || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">图片数量</span><span class="text-ink-primary font-medium">{{ scanResult?.image_count || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">总大小</span><span class="text-ink-primary">{{ scanResult ? formatBytes(scanResult.total_size_bytes) : '—' }}</span></div>
          </div>
          <div class="divider my-4"></div>
          <div class="text-xs text-ink-tertiary mb-3">
            <Icon name="xi-sparkle" :size="12" class="text-amber-500 mr-1 inline" />
            提交后架次将进入"已接入"状态，原始图片保留在本机路径（不复制），可用于创建处理任务
          </div>
          <div class="flex gap-2">
            <router-link to="/data/batches" class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center">取消</router-link>
            <button
              @click="submit"
              :disabled="!canSubmit || submitting"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-btn text-sm font-medium"
            >{{ submitting ? '提交中…' : '注册架次' }}</button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
```

---

## Task 9: 更新 BatchDetail.vue（架次详情页，含编辑+分页图片浏览）

**Files:**
- Modify: `frontend/src/views/data/BatchDetail.vue`

- [ ] **Step 1: 替换 BatchDetail.vue 内容**

关键变更：使用 batchesApi，添加内联编辑表单、分页图片加载（加载更多）、懒加载 Lightbox、删除功能。

```vue
<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi, type Batch, type BatchImage } from '@/api/batches'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const batch = ref<Batch | null>(null)
const images = ref<BatchImage[]>([])
const imageTotal = ref(0)
const imagePage = ref(1)
const imagePageSize = 36
const totalPages = ref(1)
const loadingImages = ref(false)
const loading = ref(true)
const errorMsg = ref('')
const editing = ref(false)
const editForm = ref<Partial<Batch>>({})

// Lightbox
const lightboxIdx = ref(-1)
const lightboxOpen = computed(() => lightboxIdx.value >= 0)

const totalSizeGb = computed(() => (((batch.value?.total_size_bytes || 0) / (1024 ** 3)).toFixed(2)))
const hasMore = computed(() => imagePage.value < totalPages.value)

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process')) return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('完成')) return { cls: 'badge-success', label: '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const b = await batchesApi.get(id.value)
    batch.value = b
    await loadImages(1, true)
  } catch (e: any) {
    errorMsg.value = e.message || '加载架次详情失败'
  } finally {
    loading.value = false
  }
}

async function loadImages(page: number, reset: boolean = false) {
  if (loadingImages.value) return
  loadingImages.value = true
  try {
    const res = await batchesApi.listImages(id.value, { page, page_size: imagePageSize })
    if (reset) {
      images.value = res.images
    } else {
      images.value = [...images.value, ...res.images]
    }
    imageTotal.value = res.total
    totalPages.value = res.total_pages
    imagePage.value = res.page
  } catch (e: any) {
    console.error('加载图片失败:', e)
  } finally {
    loadingImages.value = false
  }
}

function loadMore() {
  if (hasMore.value) {
    loadImages(imagePage.value + 1)
  }
}

function startEdit() {
  if (!batch.value) return
  editForm.value = {
    batch_name: batch.value.batch_name,
    crop_type: batch.value.crop_type,
    flight_date: batch.value.flight_date,
    plot_name: batch.value.plot_name || '',
    drone_model: batch.value.drone_model || '',
    flight_altitude_m: batch.value.flight_altitude_m,
    overlap_front: batch.value.overlap_front,
    overlap_side: batch.value.overlap_side,
    description: batch.value.description || '',
  }
  editing.value = true
}

async function saveEdit() {
  try {
    const updated = await batchesApi.update(id.value, editForm.value)
    batch.value = updated
    editing.value = false
  } catch (e: any) {
    alert(e.message || '保存失败')
  }
}

function cancelEdit() {
  editing.value = false
}

async function deleteBatch() {
  if (!batch.value) return
  if (!confirm(`确定要删除架次「${batch.value.batch_name}」吗？\n（原始图片文件不会被删除）`)) return
  try {
    await batchesApi.delete(id.value)
    router.push('/data/batches')
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

function openLightbox(i: number) {
  lightboxIdx.value = i
}
function closeLightbox() {
  lightboxIdx.value = -1
}
function prevImg() {
  if (lightboxIdx.value > 0) lightboxIdx.value--
}
function nextImg() {
  if (lightboxIdx.value < images.value.length - 1) {
    lightboxIdx.value++
    // 如果接近末尾且有更多，自动加载
    if (lightboxIdx.value >= images.value.length - 3 && hasMore.value) {
      loadMore()
    }
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / (1024 ** 2)).toFixed(1) + ' MB'
  return (bytes / (1024 ** 3)).toFixed(2) + ' GB'
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/batches" class="hover:text-brand-700">数据管理 / 原始架次</router-link>
      <Icon name="xi-grid" :size="8" />
      <span class="text-ink-primary">{{ batch?.batch_name || id }}</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <Icon name="xi-sparkle" :size="24" class="animate-spin mx-auto" />
      <div class="mt-3 text-sm">加载中…</div>
    </div>

    <!-- 错误 -->
    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3">{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
      <router-link to="/data/batches" class="ml-2 text-brand-700 hover:underline text-sm">返回列表</router-link>
    </div>

    <template v-else-if="batch">
      <!-- 头部 -->
      <div class="flex items-end justify-between mb-6">
        <div>
          <div class="flex items-center gap-3 flex-wrap">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ batch.batch_name }}</h1>
            <span class="badge" :class="statusBadge(batch.status).cls">{{ statusBadge(batch.status).label }}</span>
            <span class="tag tag-green">{{ batch.crop_type }}</span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">
            采集于 {{ batch.flight_date }} · 登记于 {{ batch.created_at }} · 路径 <code class="text-xs bg-surface-hover px-1 rounded">{{ batch.image_folder_path }}</code>
          </p>
        </div>
        <div class="flex gap-2">
          <button @click="startEdit" v-if="!editing" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary inline-flex items-center gap-1.5">
            <Icon name="xi-tune" :size="12" /> 编辑
          </button>
          <button @click="deleteBatch" class="px-3 py-2 bg-white border border-red-200 hover:bg-red-50 text-red-600 rounded-btn text-sm inline-flex items-center gap-1.5">
            <Icon name="xi-bell" :size="12" /> 删除
          </button>
          <router-link
            to="/process/task-new"
            class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
          >
            <Icon name="xi-augment" :size="12" /> 创建处理任务
          </router-link>
        </div>
      </div>

      <!-- 编辑表单 -->
      <div v-if="editing" class="bg-white border border-brand-300 rounded-card p-5 mb-5">
        <h3 class="text-sm font-semibold text-ink-primary mb-4">编辑架次元数据</h3>
        <div class="grid grid-cols-2 gap-4">
          <div><label class="block text-xs font-medium mb-1">架次名称</label><input v-model="editForm.batch_name" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">作物类型</label><input v-model="editForm.crop_type" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">采集日期</label><input v-model="editForm.flight_date" type="date" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">地块名称</label><input v-model="editForm.plot_name" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">无人机型号</label><input v-model="editForm.drone_model" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">飞行高度（米）</label><input v-model.number="editForm.flight_altitude_m" type="number" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">航向重叠率</label><input v-model.number="editForm.overlap_front" type="number" step="0.05" min="0" max="1" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div><label class="block text-xs font-medium mb-1">旁向重叠率</label><input v-model.number="editForm.overlap_side" type="number" step="0.05" min="0" max="1" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm" /></div>
          <div class="col-span-2"><label class="block text-xs font-medium mb-1">描述</label><textarea v-model="editForm.description" rows="2" class="w-full px-3 py-2 border border-surface-border rounded-btn text-sm resize-none"></textarea></div>
        </div>
        <div class="flex gap-2 mt-4 justify-end">
          <button @click="cancelEdit" class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm">取消</button>
          <button @click="saveEdit" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium">保存</button>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-4 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">原图数量</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ batch.image_count }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">总大小</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ totalSizeGb }} GB</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">图片格式</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ batch.image_formats.join('、') }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">采集高度</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ batch.flight_altitude_m ? batch.flight_altitude_m + ' m' : '-' }}
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 元数据 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">元数据</h3>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">架次 ID</span><span class="font-mono">{{ batch.batch_id }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span>{{ batch.crop_type }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">采集日期</span><span>{{ batch.flight_date }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">地块名称</span><span>{{ batch.plot_name || '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">无人机型号</span><span>{{ batch.drone_model || '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">飞行高度</span><span>{{ batch.flight_altitude_m ? batch.flight_altitude_m + ' m' : '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">航向重叠率</span><span>{{ batch.overlap_front ?? '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">旁向重叠率</span><span>{{ batch.overlap_side ?? '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">图片数量</span><span>{{ batch.image_count }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">登记时间</span><span>{{ batch.created_at }}</span></div>
              <div class="flex justify-between col-span-2">
                <span class="text-ink-tertiary">图片路径</span>
                <span class="text-ink-primary text-right font-mono text-[11px] break-all">{{ batch.image_folder_path }}</span>
              </div>
              <div class="flex justify-between col-span-2" v-if="batch.description">
                <span class="text-ink-tertiary">描述</span>
                <span class="text-ink-primary text-right">{{ batch.description }}</span>
              </div>
            </div>
          </div>

          <!-- 图片网格 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-ink-primary">原始图片</h3>
              <span class="text-xs text-ink-tertiary">已加载 {{ images.length }}/{{ imageTotal }} 张</span>
            </div>
            <div v-if="images.length === 0 && !loadingImages" class="py-10 text-center text-ink-tertiary text-sm">
              <Icon name="xi-database" :size="24" class="mx-auto mb-2 opacity-40" />
              暂无图片
            </div>
            <div v-else class="grid grid-cols-6 gap-2">
              <div
                v-for="(img, i) in images"
                :key="img.filename"
                class="aspect-square bg-surface-bg rounded-btn overflow-hidden cursor-pointer relative group"
                @click="openLightbox(i)"
              >
                <img
                  :src="batchesApi.imagePreviewUrl(batch.batch_id, img.filename, 'thumbnail')"
                  :alt="img.filename"
                  loading="lazy"
                  class="w-full h-full object-cover transition-transform group-hover:scale-105"
                />
                <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
                  {{ img.filename }}
                </div>
              </div>
            </div>
            <div v-if="hasMore || loadingImages" class="mt-4 text-center">
              <button
                v-if="hasMore && !loadingImages"
                @click="loadMore"
                class="px-4 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-secondary"
              >
                加载更多
              </button>
              <span v-if="loadingImages" class="text-xs text-ink-tertiary inline-flex items-center gap-1">
                <Icon name="xi-sparkle" :size="12" class="animate-spin" /> 加载中…
              </span>
            </div>
          </div>
        </div>

        <div class="space-y-5">
          <!-- 快速信息 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">图片信息</h3>
            <div class="space-y-2.5 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">格式</span><span>{{ batch.image_formats.join('、') }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">状态</span><span class="badge badge-success">已接入</span></div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Lightbox -->
    <div
      v-if="lightboxOpen"
      class="fixed inset-0 bg-black/85 z-50 flex items-center justify-center"
      @click.self="closeLightbox"
    >
      <button class="absolute top-4 right-4 text-white text-2xl hover:text-gray-300" @click="closeLightbox">
        <Icon name="xi-bell" :size="20" />
      </button>
      <button
        v-if="lightboxIdx > 0"
        class="absolute left-4 text-white text-3xl hover:text-gray-300 p-2"
        @click="prevImg"
      ><Icon name="xi-grid" :size="24" /></button>
      <div class="max-w-5xl max-h-[85vh] flex flex-col items-center">
        <img
          :src="images[lightboxIdx] ? batchesApi.imagePreviewUrl(batch!.batch_id, images[lightboxIdx].filename, 'medium') : ''"
          class="max-w-full max-h-[80vh] object-contain rounded-btn"
        />
        <div class="mt-3 text-white text-xs font-mono flex items-center gap-4">
          <span>{{ images[lightboxIdx]?.filename }}</span>
          <span class="text-gray-400">{{ lightboxIdx + 1 }} / {{ images.length }}</span>
          <span v-if="images[lightboxIdx]" class="text-gray-400">{{ images[lightboxIdx].width }}×{{ images[lightboxIdx].height }} · {{ formatBytes(images[lightboxIdx].size_bytes) }}</span>
        </div>
      </div>
      <button
        v-if="lightboxIdx < images.length - 1 || hasMore"
        class="absolute right-4 text-white text-3xl hover:text-gray-300 p-2"
        @click="nextImg"
      ><Icon name="xi-grid" :size="24" class="rotate-180" /></button>
    </div>
  </AppLayout>
</template>
```

**注意：** 如果 Icon 组件不包含 `xi-grid` 作为方向箭头，需要检查可用图标并替换为合适的箭头图标（如在 Icon 组件中使用 chevron 样式的 SVG，或临时用字符 `<` `>` 代替）。

---

## Task 10: 清理 mock.ts 和 api/mock.ts 中 batches 相关内容

**Files:**
- Modify: `frontend/src/stores/mock.ts`
- Modify: `frontend/src/api/mock.ts`

- [ ] **Step 1: 更新 stores/mock.ts，移除 batches 相关**

将 mock store 中的 batches、batchTotal、fetchBatches 移除，保留 tasks 和 datasets：

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { mockApi, type ProcessingTask, type Dataset } from '@/api/mock'

export const useMockStore = defineStore('mock', () => {
  const tasks = ref<ProcessingTask[]>([])
  const taskTotal = ref(0)
  const datasets = ref<Dataset[]>([])
  const datasetTotal = ref(0)
  const formatDist = ref<Record<string, number>>({})
  const loading = ref(false)

  async function fetchTasks(params?: { type?: string; status?: string }) {
    loading.value = true
    try {
      const res = await mockApi.fetchTasks(params)
      tasks.value = res.data.tasks
      taskTotal.value = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchDatasets(params?: { format?: string }) {
    loading.value = true
    try {
      const res = await mockApi.fetchDatasets(params)
      datasets.value = res.data.datasets
      datasetTotal.value = res.data.total
      formatDist.value = res.data.format_dist
    } finally {
      loading.value = false
    }
  }

  return {
    tasks, taskTotal, datasets, datasetTotal, formatDist, loading,
    fetchTasks, fetchDatasets,
  }
})
```

- [ ] **Step 2: 更新 api/mock.ts，移除 Batch 类型和 batches 相关方法**

移除 Batch 接口、fetchBatches、createBatch、fetchBatch、fetchBatchImages、batchImagePreviewUrl，保留 ProcessingTask 和 Dataset 相关：

```typescript
import client from './client'

export interface ProcessingTask {
  id: string
  name: string
  type: 'clahe' | 'crop'
  batch_id: string
  status: 'processing' | 'completed' | 'failed'
  progress: number
  input_path: string
  output_path: string
  params: Record<string, any>
  total_images: number
  processed_images: number
  created_at: string
  completed_at?: string
  error?: string
}

export interface Dataset {
  id: string
  name: string
  version: string
  format: 'YOLO' | 'COCO' | 'VOC'
  crop_type: string
  sample_count: number
  train_count: number
  val_count: number
  test_count: number
  classes: string[]
  created_at: string
  status: string
  size_mb: number
  path: string
  description?: string
}

export const mockApi = {
  // 数据处理
  fetchTasks: (params?: { type?: string; status?: string }) =>
    client.get<unknown, { data: { tasks: ProcessingTask[]; total: number } }>('/processing/tasks', { params }),
  fetchTask: (id: string) => client.get<unknown, { data: ProcessingTask }>(`/processing/tasks/${id}`),
  taskPreviewUrl: (taskId: string, type?: 'original' | 'result') =>
    `/api/processing/tasks/${taskId}/preview${type ? `?type=${type}` : ''}`,

  // 数据集管理
  fetchDatasets: (params?: { format?: string }) =>
    client.get<unknown, { data: { datasets: Dataset[]; total: number; format_dist: Record<string, number> } }>('/datasets', { params }),
  fetchDataset: (id: string) => client.get<unknown, { data: Dataset }>(`/datasets/${id}`),
  fetchDatasetReport: (id: string) => client.get<unknown, { data: any }>(`/datasets/${id}/report`),
}
```

- [ ] **Step 3: 检查 Index.vue 是否引用了 mock batches**

Read: `frontend/src/views/index/Index.vue`，如果其中引用了 `useMockStore` 的 batches 相关内容，调整为使用 batchesApi 获取统计数据。如果首页只是展示 mock 数据暂时可以保留或改为调用 batchesApi.list() 获取真实统计。

---

## Task 11: 验证与构建

- [ ] **Step 1: 运行 Python 测试**

Run: `cd backend && python -m pytest tests/test_batch_registry.py tests/test_registry.py -v`
Expected: 全部 PASS。

- [ ] **Step 2: 运行 TypeScript 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误。如果有关于 mock.ts 的引用错误（如其他文件引用了已删除的 Batch 类型或 fetchBatches 方法），修复这些引用。

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，产物输出到 backend/static。

- [ ] **Step 4: 启动后端验证自动扫描**

Run: `cd backend && python app.py`
Wait for startup, then run: `curl -s http://localhost:5000/api/batches | python -c "import sys,json; d=json.load(sys.stdin); print('success:', d['success']); print('batches:', d['data']['total']); print('summary:', d['data']['summary'])"`
Expected: success=True, batches=3, summary 显示正确统计。

- [ ] **Step 5: 验证图片预览 API**

Run: `curl -s -o /tmp/thumb_test.jpg -w "%{http_code} %{size_download}" "http://localhost:5000/api/batches/batch_sugarcane_20250419_5m/images/DJI_20250511172207_0003_D.JPG/preview?size=thumbnail"`
Expected: 200 状态码，下载文件大小>0，且是有效 JPEG。

---

## 自审清单

1. **Spec 覆盖：** 所有 PRD 需求均有对应任务——架次 CRUD、自动扫描、YAML 持久化、分页图片列表、动态缩略图、路径预检、删除不删文件、外部路径支持。
2. **无占位符：** 所有步骤包含完整代码和命令。
3. **类型一致性：** Batch 接口在 batches.ts 中定义，三个 Vue 组件和 batches_api.py 字段名一致。
4. **已有模式遵循：** BatchRegistry 参考 ModelRegistry 的 _InlineList、_ordered_config、save_to_yaml 模式；engine.py 中的 get_batch_registry() 与 get_registry() 模式一致；batches.ts 参考 models.ts 风格。
