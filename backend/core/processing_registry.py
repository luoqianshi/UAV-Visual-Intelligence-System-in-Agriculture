"""处理任务注册中心：YAML 持久化 + output/ 自扫描 + CRUD。

参考 BatchRegistry 模式：
- data/processing_tasks.yaml 持久化任务元数据
- 启动时扫描 output/ 目录，发现未注册的 index.json 自动重建任务记录
- 内存维护任务索引，支持过滤查询
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from config import IMAGE_EXTENSIONS, OUTPUT_DIR, PROCESSING_TASKS_YAML, PROJECT_ROOT

logger = logging.getLogger(__name__)

_TASK_FIELD_ORDER = [
    "task_id", "name", "task_type", "status", "progress",
    "input_paths", "output_path", "params",
    "total_images", "processed_images", "total_tiles",
    "created_at", "started_at", "completed_at", "error",
    "sub_dirs",
]


class ProcessingRegistry:
    """处理任务注册中心。"""

    def __init__(self, output_dir=OUTPUT_DIR, yaml_path=PROCESSING_TASKS_YAML):
        self._output_dir = Path(output_dir)
        self._yaml_path = Path(yaml_path)
        self._tasks = {}

    def load_from_yaml(self):
        """启动时加载：
        1. 读取 processing_tasks.yaml
        2. processing 状态的任务标记为 interrupted（重启后无法恢复进程）
        3. 扫描 output/ 目录，发现未注册的 index.json 自动补全
        """
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            tasks_list = data.get("tasks", []) or []
            for t in tasks_list:
                if t.get("status") == "processing":
                    t["status"] = "interrupted"
                    t["error"] = "服务重启，任务被中断"
                self._tasks[t["task_id"]] = t

        newly_added = self._auto_discover_output()
        if newly_added:
            self.save_to_yaml()

    def save_to_yaml(self):
        """持久化任务列表到 YAML。"""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_list = [self._ordered_config(t) for t in self._tasks.values()]
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"tasks": tasks_list}, f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                indent=2,
                width=1000,
            )

    def create_task(self, name, task_type, input_paths, params):
        """创建任务记录。生成 task_id 与 output_path。

        task_id 格式：{task_type}_{ts}_{ms:03d}
        output_path 格式：output/{task_id}（与 task_id 完全一致）
        """
        if task_type not in ("clahe", "crop"):
            raise ValueError(f"未知任务类型: {task_type}")
        if not input_paths:
            raise ValueError("必须指定至少一个输入源")

        now = datetime.now().isoformat(timespec="seconds")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ms = datetime.now().microsecond % 1000
        task_id = f"{task_type}_{timestamp}_{ms:03d}"
        while task_id in self._tasks:
            ms += 1
            task_id = f"{task_type}_{timestamp}_{ms:03d}"

        output_path = f"output/{task_id}"
        total_images = self._count_input_images(input_paths)

        cfg = {
            "task_id": task_id,
            "name": name,
            "task_type": task_type,
            "status": "pending",
            "progress": 0,
            "input_paths": input_paths,
            "output_path": output_path,
            "params": params,
            "total_images": total_images,
            "processed_images": 0,
            "total_tiles": 0 if task_type == "crop" else None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "sub_dirs": [],
        }
        self._tasks[task_id] = cfg
        self.save_to_yaml()
        return cfg

    def update_task(self, task_id, **fields):
        """更新任务字段。"""
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        cfg = self._tasks[task_id]
        for k, v in fields.items():
            if k in cfg:
                cfg[k] = v
        self.save_to_yaml()
        return cfg

    def get_task(self, task_id):
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        return self._tasks[task_id]

    def list_tasks(self, task_type=None, status=None):
        result = list(self._tasks.values())
        if task_type:
            result = [t for t in result if t["task_type"] == task_type]
        if status:
            result = [t for t in result if t["status"] == status]
        return sorted(result, key=lambda t: t["created_at"], reverse=True)

    def delete_task(self, task_id, delete_output=False):
        """删除任务记录。delete_output=True 时同时删除 output 目录。"""
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        cfg = self._tasks[task_id]
        if delete_output:
            # output_path = "output/{task_id}"，目录名即 task_id，
            # 直接相对 self._output_dir 定位（与 _auto_discover_output 一致）
            out_dir = self._output_dir / task_id
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
        del self._tasks[task_id]
        self.save_to_yaml()

    def list_processed(self):
        """列出 output/ 下所有处理产物。"""
        items = []
        if not self._output_dir.is_dir():
            return items
        for entry in sorted(self._output_dir.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            name = entry.name
            task_type = None
            if name.startswith("clahe_"):
                task_type = "clahe"
            elif name.startswith("crop_"):
                task_type = "crop"
            else:
                continue
            task_id = name
            task_cfg = self._tasks.get(task_id, {})
            image_count = sum(
                1 for f in entry.rglob("*")
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            )
            index_path = entry / "index.json"
            index_data = {}
            if index_path.exists():
                try:
                    index_data = json.loads(index_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append({
                "output_path": f"output/{name}",
                "task_id": task_id,
                "task_type": task_type,
                "name": task_cfg.get("name") or index_data.get("name") or name,
                "status": task_cfg.get("status", "completed" if index_data else "unknown"),
                "params": task_cfg.get("params") or index_data.get("params", {}),
                "image_count": image_count,
                "total_tiles": index_data.get("total_tiles") or task_cfg.get("total_tiles") or 0,
                "created_at": task_cfg.get("created_at") or index_data.get("created_at", ""),
                "sub_dirs": index_data.get("sub_dirs", task_cfg.get("sub_dirs", [])),
                "has_task": task_id in self._tasks,
            })
        return items

    def _auto_discover_output(self):
        """扫描 output/ 目录，发现未注册的 index.json 自动重建任务记录。"""
        if not self._output_dir.is_dir():
            return False
        newly_added = False
        for entry in sorted(self._output_dir.iterdir()):
            if not entry.is_dir():
                continue
            index_path = entry / "index.json"
            if not index_path.exists():
                continue
            name = entry.name
            if name.startswith("clahe_"):
                task_type = "clahe"
            elif name.startswith("crop_"):
                task_type = "crop"
            else:
                continue
            task_id = name
            if task_id in self._tasks:
                continue
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
                cfg = {
                    "task_id": task_id,
                    "name": f"{task_type} 产物 {name}",
                    "task_type": task_type,
                    "status": "completed",
                    "progress": 100,
                    "input_paths": index_data.get("input_paths", []),
                    "output_path": f"output/{name}",
                    "params": index_data.get("params", {}),
                    "total_images": index_data.get("total_images", 0),
                    "processed_images": index_data.get("processed_images", 0),
                    "total_tiles": index_data.get("total_tiles") if task_type == "crop" else None,
                    "created_at": index_data.get("created_at", ""),
                    "started_at": None,
                    "completed_at": index_data.get("created_at"),
                    "error": None,
                    "sub_dirs": index_data.get("sub_dirs", []),
                }
                self._tasks[task_id] = cfg
                newly_added = True
                logger.info("自扫描发现未注册任务: %s", task_id)
            except Exception as e:
                logger.warning("读取 %s 失败: %s", index_path, e)
        return newly_added

    def _count_input_images(self, input_paths):
        """统计输入源图片总数。"""
        count = 0
        for p in input_paths:
            path = self._resolve_path(p)
            if not path.is_dir():
                continue
            count += sum(
                1 for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            )
        return count

    def _resolve_path(self, path_str):
        """路径解析：相对路径相对 PROJECT_ROOT。"""
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _ordered_config(self, cfg):
        """按标准字段顺序排列。"""
        ordered = {}
        for key in _TASK_FIELD_ORDER:
            if key in cfg:
                ordered[key] = cfg[key]
        for key, val in cfg.items():
            if key not in ordered:
                ordered[key] = val
        return ordered
