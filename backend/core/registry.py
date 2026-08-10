"""模型注册中心：YAML加载 + LRU缓存 + 热切换 + 动态注册 + 持久化。"""
import re
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import yaml


# 模型配置字段的标准顺序（与 config/models.yaml 保持一致）
_MODEL_FIELD_ORDER = [
    "name", "engine", "weight", "display_name", "category",
    "imgsz", "conf", "iou", "device", "classes", "max_det",
]


class _InlineList(list):
    """标记为内联输出的列表（用于 classes 字段，保持 ["a", "b"] 格式）"""
    pass


def _inline_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


yaml.add_representer(_InlineList, _inline_list_representer)


def _sanitize_name(name: str) -> str:
    """将模型名转换为安全的文件名（只保留字母数字下划线连字符）。"""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def _name_to_weight_filename(name: str) -> str:
    """将模型名转换为权重文件名（连字符转下划线，加.pt后缀）。
    例：yolo12s-sugarcane -> yolo12s_sugarcane.pt
    """
    return _sanitize_name(name).replace('-', '_') + '.pt'


class ModelRegistry:
    """模型注册中心。

    - 通过 YAML 描述可用模型与默认模型；
    - 通过 OrderedDict 实现 LRU 缓存，缓存引擎实例（上限 ``lru_size``）；
    - 支持运行时热切换激活模型与动态注册新模型；
    - 动态注册时自动持久化回 YAML；
    - 引擎实例按需懒加载（``_load_engine``），避免启动期即导入 ultralytics。
    """

    def __init__(self, yaml_path: str, models_dir: str, lru_size: int = 3):
        self._yaml_path = Path(yaml_path)
        self._models_dir = Path(models_dir)
        self._lru_size = lru_size
        self._configs: dict = {}
        self._engines: OrderedDict = OrderedDict()
        self._active_model: Optional[str] = None
        self._default_model: Optional[str] = None

    def load_from_yaml(self) -> None:
        """从 YAML 文件加载模型配置，并确定默认激活模型。"""
        with open(self._yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._configs = {cfg["name"]: cfg for cfg in data.get("models", [])}
        self._default_model = data.get("default_model")
        if self._default_model in self._configs:
            self._active_model = self._default_model
        else:
            self._active_model = next(iter(self._configs), None)

    def _ordered_config(self, cfg: dict) -> dict:
        """按标准顺序排列配置字段，确保 YAML 输出格式一致。"""
        ordered = {}
        for key in _MODEL_FIELD_ORDER:
            if key in cfg:
                val = cfg[key]
                # classes 列表使用内联格式
                if key == "classes" and isinstance(val, list):
                    val = _InlineList(val)
                ordered[key] = val
        # 追加任何未在标准顺序中的额外字段
        for key, val in cfg.items():
            if key not in ordered:
                ordered[key] = val
        return ordered

    def save_to_yaml(self) -> None:
        """将当前内存中的模型配置持久化回 YAML 文件。"""
        models_list = [self._ordered_config(cfg) for cfg in self._configs.values()]
        data = {
            "default_model": self._default_model or self._active_model,
            "models": models_list,
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

    def list_models(self) -> list:
        """返回所有模型配置列表，每项附带 ``is_active`` 标记。"""
        return [
            {**cfg, "is_active": cfg["name"] == self._active_model}
            for cfg in self._configs.values()
        ]

    def get_active(self) -> Optional[str]:
        """返回当前激活模型名。"""
        return self._active_model

    def get_config(self, name: Optional[str] = None) -> dict:
        """返回指定模型配置；未指定时返回激活模型配置。未知模型抛 KeyError。"""
        name = name or self._active_model
        if name not in self._configs:
            raise KeyError(f"模型 '{name}' 未注册")
        return self._configs[name]

    def switch(self, name: str) -> None:
        """热切换激活模型，切换前预加载引擎以提前暴露错误。"""
        if name not in self._configs:
            raise KeyError(f"模型 '{name}' 未注册")
        self.get_engine(name)  # 预加载
        self._active_model = name

    def register(self, config: dict, weight_file_path: Optional[Path] = None) -> None:
        """动态注册一个模型配置；若当前无激活模型则自动激活，并持久化到 YAML。

        Args:
            config: 模型配置字典
            weight_file_path: 可选的已上传权重文件临时路径，若提供则移动到 models 目录
        """
        name = config["name"]
        if not name:
            raise ValueError("模型名称不能为空")
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            raise ValueError("模型名称只能包含字母、数字、下划线和连字符")

        # 处理权重文件
        if weight_file_path is not None:
            weight_filename = _name_to_weight_filename(name)
            dest_path = self._models_dir / weight_filename
            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # 移动文件（跨设备时用复制+删除）
            import shutil
            shutil.move(str(weight_file_path), str(dest_path))
            config["weight"] = f"models/{weight_filename}"

        # 设置默认值
        cfg = {
            "engine": "ultralytics",
            "imgsz": 640,
            "conf": 0.25,
            "iou": 0.7,
            "device": None,
            "max_det": 300,
            **config,
        }

        self._configs[name] = cfg
        if self._active_model is None:
            self._active_model = name
            if self._default_model is None:
                self._default_model = name

        # 持久化到 YAML
        self.save_to_yaml()

    def get_engine(self, name: Optional[str] = None):
        """获取（必要时懒加载并缓存）模型引擎实例，命中缓存时更新 LRU 顺序。"""
        name = name or self._active_model
        if name is None:
            raise RuntimeError("无激活模型")
        if name in self._engines:
            self._engines.move_to_end(name)
            return self._engines[name]
        engine = self._load_engine(name)
        self._engines[name] = engine
        while len(self._engines) > self._lru_size:
            self._engines.popitem(last=False)
        return engine

    def _load_engine(self, name: str):
        """懒加载 YOLO 引擎。测试中通过 patch 此方法规避 ultralytics 依赖。"""
        from ultralytics import YOLO
        return YOLO(self._configs[name]["weight"])

    @property
    def ready(self) -> bool:
        """是否已有激活模型。"""
        return self._active_model is not None
