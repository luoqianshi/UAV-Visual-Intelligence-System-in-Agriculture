"""模型注册中心：YAML加载 + LRU缓存 + 热切换 + 动态注册。"""
import yaml
from collections import OrderedDict
from typing import Optional


class ModelRegistry:
    """模型注册中心。

    - 通过 YAML 描述可用模型与默认模型；
    - 通过 OrderedDict 实现 LRU 缓存，缓存引擎实例（上限 ``lru_size``）；
    - 支持运行时热切换激活模型与动态注册新模型；
    - 引擎实例按需懒加载（``_load_engine``），避免启动期即导入 ultralytics。
    """

    def __init__(self, yaml_path: str, lru_size: int = 3):
        self._yaml_path = yaml_path
        self._lru_size = lru_size
        self._configs: dict = {}
        self._engines: OrderedDict = OrderedDict()
        self._active_model: Optional[str] = None

    def load_from_yaml(self) -> None:
        """从 YAML 文件加载模型配置，并确定默认激活模型。"""
        with open(self._yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._configs = {cfg["name"]: cfg for cfg in data.get("models", [])}
        default = data.get("default_model")
        if default in self._configs:
            self._active_model = default
        else:
            self._active_model = next(iter(self._configs), None)

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

    def register(self, config: dict) -> None:
        """动态注册一个模型配置；若当前无激活模型则自动激活。"""
        self._configs[config["name"]] = config
        if self._active_model is None:
            self._active_model = config["name"]

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
