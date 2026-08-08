"""ModelRegistry 单元测试：YAML 加载 / 热切换 / 动态注册 / LRU 缓存。

通过 patch `_load_engine` 规避对 ultralytics 的真实依赖。
运行：cd backend && python -m pytest tests/test_registry.py -v
"""
import pytest
from unittest.mock import patch

from core.registry import ModelRegistry


def _write_yaml(tmp_path, models, default_model=None):
    """写入临时 YAML 配置并返回路径。"""
    import yaml

    content = {"models": models}
    if default_model is not None:
        content["default_model"] = default_model
    yaml_file = tmp_path / "models.yaml"
    yaml_file.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")
    return str(yaml_file)


# ---------------------------------------------------------------------------
# 1. YAML 加载 + list_models + get_active
# ---------------------------------------------------------------------------
def test_load_from_yaml_and_list_models(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[
            {"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"},
            {"name": "yolov8s", "display_name": "YOLOv8s", "weight": "w2.pt"},
        ],
        default_model="yolov8s",
    )

    registry = ModelRegistry(yaml_path)
    registry.load_from_yaml()

    models = registry.list_models()
    assert len(models) == 2

    by_name = {m["name"]: m for m in models}
    # 默认激活的是 yolov8s
    assert registry.get_active() == "yolov8s"
    assert by_name["yolov8s"]["is_active"] is True
    assert by_name["yolov8n"]["is_active"] is False


# ---------------------------------------------------------------------------
# 2. switch 热切换 + get_engine（patch _load_engine）
# ---------------------------------------------------------------------------
def test_switch_and_get_engine(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[
            {"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"},
            {"name": "yolov8s", "display_name": "YOLOv8s", "weight": "w2.pt"},
        ],
        default_model="yolov8n",
    )

    registry = ModelRegistry(yaml_path)
    registry.load_from_yaml()
    assert registry.get_active() == "yolov8n"

    with patch.object(registry, "_load_engine", return_value="fake_engine"):
        registry.switch("yolov8s")

    assert registry.get_active() == "yolov8s"

    with patch.object(registry, "_load_engine", return_value="fake_engine"):
        engine = registry.get_engine("yolov8s")
    assert engine == "fake_engine"


# ---------------------------------------------------------------------------
# 3. register 动态注册
# ---------------------------------------------------------------------------
def test_register_sets_active_when_none(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[{"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"}],
    )

    registry = ModelRegistry(yaml_path)
    # 未加载 YAML 前，无激活模型
    assert registry.get_active() is None
    assert registry.ready is False

    registry.register({"name": "dynamic", "display_name": "Dynamic", "weight": "w.pt"})
    # 之前无激活模型，注册后自动激活
    assert registry.get_active() == "dynamic"
    assert registry.ready is True

    cfg = registry.get_config("dynamic")
    assert cfg["weight"] == "w.pt"


def test_register_keeps_existing_active(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[{"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"}],
        default_model="yolov8n",
    )

    registry = ModelRegistry(yaml_path)
    registry.load_from_yaml()
    assert registry.get_active() == "yolov8n"

    registry.register({"name": "extra", "display_name": "Extra", "weight": "w2.pt"})
    # 已有激活模型，注册新模型不应改变激活项
    assert registry.get_active() == "yolov8n"
    assert "extra" in [m["name"] for m in registry.list_models()]


# ---------------------------------------------------------------------------
# 4. LRU 驱逐
# ---------------------------------------------------------------------------
def test_lru_eviction(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[
            {"name": "a", "weight": "wa.pt"},
            {"name": "b", "weight": "wb.pt"},
            {"name": "c", "weight": "wc.pt"},
        ],
    )

    registry = ModelRegistry(yaml_path, lru_size=2)
    registry.load_from_yaml()

    def fake_load(name):
        return f"engine_{name}"

    with patch.object(registry, "_load_engine", side_effect=fake_load):
        ea = registry.get_engine("a")
        eb = registry.get_engine("b")
        ec = registry.get_engine("c")

    assert ea == "engine_a"
    assert eb == "engine_b"
    assert ec == "engine_c"

    # 容量上限为 2，最早加载的 a 应被驱逐
    assert len(registry._engines) == 2
    assert "a" not in registry._engines
    assert "b" in registry._engines
    assert "c" in registry._engines


def test_lru_move_to_end_on_access(tmp_path):
    """命中缓存时应将条目移到末尾，从而改变驱逐顺序。"""
    yaml_path = _write_yaml(
        tmp_path,
        models=[
            {"name": "a", "weight": "wa.pt"},
            {"name": "b", "weight": "wb.pt"},
            {"name": "c", "weight": "wc.pt"},
        ],
    )

    registry = ModelRegistry(yaml_path, lru_size=2)
    registry.load_from_yaml()

    def fake_load(name):
        return f"engine_{name}"

    with patch.object(registry, "_load_engine", side_effect=fake_load):
        registry.get_engine("a")
        registry.get_engine("b")
        # 重新访问 a，使其成为最近使用
        registry.get_engine("a")
        # 现在加载 c，应驱逐最久未使用的 b
        registry.get_engine("c")

    assert len(registry._engines) == 2
    assert "b" not in registry._engines
    assert "a" in registry._engines
    assert "c" in registry._engines


# ---------------------------------------------------------------------------
# 5. get_config 未知模型抛 KeyError
# ---------------------------------------------------------------------------
def test_get_config_unknown_raises_keyerror(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[{"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"}],
        default_model="yolov8n",
    )

    registry = ModelRegistry(yaml_path)
    registry.load_from_yaml()

    with pytest.raises(KeyError):
        registry.get_config("not_exists")


def test_switch_unknown_raises_keyerror(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[{"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"}],
        default_model="yolov8n",
    )

    registry = ModelRegistry(yaml_path)
    registry.load_from_yaml()

    with pytest.raises(KeyError):
        registry.switch("not_exists")


def test_get_engine_without_active_raises_runtimeerror(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        models=[{"name": "yolov8n", "display_name": "YOLOv8n", "weight": "w1.pt"}],
    )

    registry = ModelRegistry(yaml_path)
    # 未加载，无激活模型
    with pytest.raises(RuntimeError):
        registry.get_engine()
