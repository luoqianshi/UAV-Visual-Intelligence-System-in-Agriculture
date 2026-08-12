"""数据处理执行引擎：批处理 CLAHE / 滑窗裁切。

复用 core/clahe.py 与 core/tiling.py 的纯算法函数，叠加文件 IO 与进度上报。
不持有状态，每次调用独立；由 processing_task_manager 异步驱动。
"""
import json
import logging
from pathlib import Path

import cv2

from core import clahe, tiling
from config import IMAGE_EXTENSIONS, PROJECT_ROOT

logger = logging.getLogger(__name__)


class ProcessingEngine:
    """批处理执行器：无状态，可被 task_manager 安全驱动。"""

    def __init__(self):
        pass

    def run_clahe(self, task_id, input_paths, params, output_dir, on_progress=None):
        """批量 CLAHE 增强。

        Args:
            task_id: 任务 ID
            input_paths: 输入源路径列表（架次文件夹路径 / 自定义目录路径）
            params: {clip_limit: float, grid_size: [int, int]}
            output_dir: output/{task_id}/ Path 对象
            on_progress: 回调 fn(processed: int, total: int)

        Returns:
            dict: {total_images, processed_images, output_dir, sub_dirs}
        """
        clip_limit = float(params.get("clip_limit", 2.0))
        grid_size_raw = params.get("grid_size", [8, 8])
        grid_size = tuple(grid_size_raw) if isinstance(grid_size_raw, (list, tuple)) else (8, 8)

        sources = self._collect_inputs(input_paths)
        total = sum(len(imgs) for _, imgs in sources)
        processed = 0
        sub_dir_stats = []

        for sub_name, img_paths in sources:
            sub_out = output_dir / sub_name
            sub_out.mkdir(parents=True, exist_ok=True)
            sub_count = 0
            for img_path in img_paths:
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        logger.warning("跳过无法读取: %s", img_path)
                        continue
                    enhanced = clahe.enhance(img, clip_limit=clip_limit, grid_size=grid_size)
                    cv2.imwrite(str(sub_out / img_path.name), enhanced)
                    processed += 1
                    sub_count += 1
                    if on_progress:
                        on_progress(processed, total)
                except Exception as e:
                    logger.warning("处理失败 %s: %s", img_path.name, e)
            sub_dir_stats.append({"sub_dir": sub_name, "image_count": sub_count})

        return {
            "total_images": total,
            "processed_images": processed,
            "output_dir": str(output_dir),
            "sub_dirs": sub_dir_stats,
        }

    def run_crop(self, task_id, input_paths, params, output_dir, on_progress=None):
        """批量滑窗裁切。命名：{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg

        Args:
            params: {tile_size: int, overlap_ratio: float}

        Returns:
            dict: {total_images, processed_images, total_tiles, output_dir, sub_dirs}
        """
        tile_size = int(params.get("tile_size", 640))
        overlap_ratio = float(params.get("overlap_ratio", 0.05))

        sources = self._collect_inputs(input_paths)
        total_images = sum(len(imgs) for _, imgs in sources)
        processed_images = 0
        total_tiles = 0
        sub_dir_stats = []

        for sub_name, img_paths in sources:
            sub_out = output_dir / sub_name
            sub_out.mkdir(parents=True, exist_ok=True)
            sub_tiles = 0
            sub_images = 0
            for img_path in img_paths:
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        logger.warning("跳过无法读取: %s", img_path)
                        continue
                    tiles = tiling.slide_window(img, tile_size, overlap_ratio)
                    seq = 0
                    for tile_img, ox, oy in tiles:
                        seq += 1
                        fname = f"{img_path.stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg"
                        cv2.imwrite(str(sub_out / fname), tile_img)
                    total_tiles += seq
                    sub_tiles += seq
                    processed_images += 1
                    sub_images += 1
                    if on_progress:
                        on_progress(processed_images, total_images)
                except Exception as e:
                    logger.warning("裁切失败 %s: %s", img_path.name, e)
            sub_dir_stats.append({
                "sub_dir": sub_name,
                "image_count": sub_images,
                "tiles_count": sub_tiles,
            })

        return {
            "total_images": total_images,
            "processed_images": processed_images,
            "total_tiles": total_tiles,
            "output_dir": str(output_dir),
            "sub_dirs": sub_dir_stats,
        }

    def write_index(self, output_dir, task_id, task_type, params, result, created_at):
        """写入 output/{task_id}/index.json（任务参数 + 输出统计快照）。"""
        index = {
            "task_id": task_id,
            "task_type": task_type,
            "params": params,
            "created_at": created_at,
            "total_images": result["total_images"],
            "processed_images": result["processed_images"],
            "sub_dirs": result["sub_dirs"],
        }
        if task_type == "crop":
            index["total_tiles"] = result.get("total_tiles", 0)
        (output_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _collect_inputs(self, input_paths):
        """输入源归一化为 [(sub_dir_name, [image_paths])]。

        sub_dir_name 用源目录名；若同名则追加 _2、_3 避免冲突。
        支持：
        1. 原始架次目录：图片直接在根目录
        2. 加工产物目录：包含 index.json，图片在 sub_dirs 子目录中
        3. 兜底递归：根目录无图但有子目录时，递归扫描子目录
        """
        sources = []
        used_names = set()
        for p in input_paths:
            path = Path(p)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.is_dir():
                logger.warning("跳过不存在的输入路径: %s", path)
                continue

            # 检查是否为加工产物目录（包含 index.json）
            index_path = path / "index.json"
            if index_path.exists():
                try:
                    import json
                    with open(index_path, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                    sub_dirs = index_data.get("sub_dirs", [])
                    for sd in sub_dirs:
                        sd_name = sd.get("sub_dir", "")
                        if not sd_name:
                            continue
                        sd_path = path / sd_name
                        if not sd_path.is_dir():
                            continue
                        img_paths = sorted([
                            f for f in sd_path.iterdir()
                            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                        ])
                        if not img_paths:
                            continue
                        # 子目录命名：task_id/sub_dir 避免冲突
                        base_name = f"{path.name}_{sd_name}"
                        sub_name = base_name
                        counter = 2
                        while sub_name in used_names:
                            sub_name = f"{base_name}_{counter}"
                            counter += 1
                        used_names.add(sub_name)
                        sources.append((sub_name, img_paths))
                    if sub_dirs:
                        continue  # 已通过 index.json 处理
                except Exception as e:
                    logger.warning("读取 index.json 失败，尝试普通扫描: %s", e)

            # 普通目录：直接扫描根目录
            img_paths = sorted([
                f for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            ])
            if img_paths:
                base_name = path.name
                sub_name = base_name
                counter = 2
                while sub_name in used_names:
                    sub_name = f"{base_name}_{counter}"
                    counter += 1
                used_names.add(sub_name)
                sources.append((sub_name, img_paths))
                continue

            # 兜底：根目录无图，递归扫描一级子目录
            for sub_entry in sorted(path.iterdir()):
                if not sub_entry.is_dir():
                    continue
                sub_img_paths = sorted([
                    f for f in sub_entry.iterdir()
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                ])
                if not sub_img_paths:
                    continue
                base_name = f"{path.name}_{sub_entry.name}"
                sub_name = base_name
                counter = 2
                while sub_name in used_names:
                    sub_name = f"{base_name}_{counter}"
                    counter += 1
                used_names.add(sub_name)
                sources.append((sub_name, sub_img_paths))
        return sources
