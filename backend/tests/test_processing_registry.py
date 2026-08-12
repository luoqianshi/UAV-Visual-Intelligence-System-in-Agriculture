"""ProcessingRegistry 单元测试。"""
import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from core.processing_registry import ProcessingRegistry


@pytest.fixture
def registry(tmp_path):
    """独立 output_dir 与 yaml_path 的 registry。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()
    return reg


def test_create_task(registry, tmp_path):
    """create_task 生成 task_id 与 output_path。"""
    input_dir = tmp_path / "batch_input"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    cfg = registry.create_task(
        name="测试 CLAHE",
        task_type="clahe",
        input_paths=[str(input_dir)],
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
    )

    assert cfg["task_id"].startswith("clahe_")
    assert cfg["name"] == "测试 CLAHE"
    assert cfg["status"] == "pending"
    assert cfg["output_path"].startswith("output/clahe_")
    assert cfg["total_images"] == 1
    assert cfg["params"]["clip_limit"] == 2.0


def test_persist_and_reload(tmp_path):
    """任务记录持久化到 YAML 并能重新加载。"""
    yaml_path = tmp_path / "processing_tasks.yaml"
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    reg1 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg1.load_from_yaml()
    input_dir = tmp_path / "batch"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = reg1.create_task("持久化测试", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    reg2 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg2.load_from_yaml()
    loaded = reg2.get_task(cfg["task_id"])
    assert loaded["name"] == "持久化测试"
    assert loaded["task_type"] == "clahe"


def test_update_task(registry, tmp_path):
    """update_task 更新字段并持久化。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("up", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    updated = registry.update_task(
        cfg["task_id"], status="processing", progress=50, processed_images=1
    )
    assert updated["status"] == "processing"
    assert updated["progress"] == 50
    assert updated["processed_images"] == 1


def test_list_tasks_filter(registry, tmp_path):
    """list_tasks 支持 type 与 status 过滤。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg1 = registry.create_task("t1", "clahe", [str(input_dir)], {"clip_limit": 2.0})
    cfg2 = registry.create_task("t2", "crop", [str(input_dir)], {"tile_size": 640})
    registry.update_task(cfg1["task_id"], status="completed")

    assert len(registry.list_tasks()) == 2
    assert len(registry.list_tasks(task_type="clahe")) == 1
    assert len(registry.list_tasks(status="completed")) == 1
    assert len(registry.list_tasks(task_type="crop", status="completed")) == 0


def test_interrupted_on_reload(tmp_path):
    """重启时 processing 状态标记为 interrupted。"""
    yaml_path = tmp_path / "tasks.yaml"
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    reg1 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg1.load_from_yaml()
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = reg1.create_task("interrupted test", "clahe", [str(input_dir)], {"clip_limit": 2.0})
    reg1.update_task(cfg["task_id"], status="processing", progress=30)

    reg2 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg2.load_from_yaml()
    loaded = reg2.get_task(cfg["task_id"])
    assert loaded["status"] == "interrupted"
    assert "重启" in loaded["error"]


def test_auto_discover_output(tmp_path):
    """output/ 自扫描：未注册的 index.json 自动重建任务。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    clahe_dir = out_dir / "clahe_20260812_153000_456"
    clahe_dir.mkdir()
    (clahe_dir / "index.json").write_text(json.dumps({
        "task_id": "clahe_20260812_153000_456",
        "task_type": "clahe",
        "params": {"clip_limit": 2.0},
        "created_at": "2026-08-12T15:30:00",
        "total_images": 10,
        "processed_images": 10,
        "sub_dirs": [{"sub_dir": "batch1", "image_count": 10}],
    }), encoding="utf-8")

    yaml_path = tmp_path / "tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()

    cfg = reg.get_task("clahe_20260812_153000_456")
    assert cfg["status"] == "completed"
    assert cfg["total_images"] == 10


def test_list_processed(registry, tmp_path):
    """list_processed 返回 output/ 下所有处理产物。"""
    out_dir = tmp_path / "output"
    for name in ["clahe_20260812_150000_001", "crop_20260812_160000_002"]:
        d = out_dir / name
        d.mkdir(parents=True)
        (d / "index.json").write_text(json.dumps({
            "task_id": name,
            "task_type": name.split("_")[0],
            "params": {},
            "created_at": "2026-08-12T15:00:00",
            "total_images": 5,
            "processed_images": 5,
            "sub_dirs": [],
        }), encoding="utf-8")
        (d / "img.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    yaml_path = tmp_path / "tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()

    items = reg.list_processed()
    assert len(items) == 2
    types = {i["task_type"] for i in items}
    assert types == {"clahe", "crop"}


def test_delete_task(registry, tmp_path):
    """delete_task 删除任务记录。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("del", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    registry.delete_task(cfg["task_id"])
    with pytest.raises(KeyError):
        registry.get_task(cfg["task_id"])


def test_delete_task_with_output(registry, tmp_path):
    """delete_task(delete_output=True) 删除 output 目录。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("del2", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    out_path = tmp_path / "output" / cfg["task_id"]
    out_path.mkdir(parents=True)
    (out_path / "result.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    registry.delete_task(cfg["task_id"], delete_output=True)
    assert not out_path.exists()
