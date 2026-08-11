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
from typing import Dict, List, Optional

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
        self._batches: Dict[str, dict] = {}
        self._image_index: Dict[str, List[dict]] = {}
        self._ignored_folders: set = set()

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
                     plot_name: Optional[str] = None) -> List[dict]:
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

    def _scan_images(self, folder_path: Path) -> tuple:
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

    def _auto_discover_batches(self) -> List[Path]:
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
        # 尝试解析 {crop}_{date}_{altitude}m[_seq] 格式（新格式新增可选编号段）
        pattern = r'^([a-zA-Z]+)_(\d{8})_(\d+)(?:m)?(?:_(\d+))?$'
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
