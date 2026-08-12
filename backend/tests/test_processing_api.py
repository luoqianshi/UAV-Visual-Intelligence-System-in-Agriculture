"""processing_api 单元测试。"""
import shutil
from pathlib import Path

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """创建独立 app 实例，重定向 OUTPUT_DIR 与 PROCESSING_TASKS_YAML 到临时目录。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"

    import config
    monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(config, "PROCESSING_TASKS_YAML", yaml_path)

    flask_app = create_app()
    flask_app.config["TESTING"] = True

    # 在 create_app()→init_engines() 之后覆盖引擎实例，指向临时目录
    from core import engine
    from core.processing_engine import ProcessingEngine
    from core.processing_registry import ProcessingRegistry
    from core.task_manager import TaskManager
    engine.processing_engine = ProcessingEngine()
    engine.processing_registry = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    engine.processing_registry.load_from_yaml()
    engine.processing_task_manager = TaskManager(max_workers=1)

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def input_dir(tmp_path):
    """准备测试输入目录（含一张测试图）。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    d = tmp_path / "test_batch"
    d.mkdir()
    shutil.copy(fixtures / "small_640.jpg", d / "DJI_0001.jpg")
    return d


def test_list_tasks_empty(client):
    """空任务列表。"""
    r = client.get("/api/processing/tasks")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["total"] == 0


def test_submit_clahe(client, input_dir):
    """提交 CLAHE 任务。"""
    r = client.post("/api/processing/clahe", json={
        "name": "测试 CLAHE",
        "input_paths": [str(input_dir)],
        "params": {"clip_limit": 2.0, "grid_size": [8, 8]},
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"].startswith("clahe_")
    assert data["data"]["status"] == "pending"


def test_submit_crop(client, input_dir):
    """提交裁切任务。"""
    r = client.post("/api/processing/crop", json={
        "name": "测试裁切",
        "input_paths": [str(input_dir)],
        "params": {"tile_size": 640, "overlap_ratio": 0.05},
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"].startswith("crop_")


def test_submit_clahe_missing_input(client):
    """缺少 input_paths 时返回 400。"""
    r = client.post("/api/processing/clahe", json={
        "name": "无输入",
        "input_paths": [],
        "params": {"clip_limit": 2.0},
    })
    assert r.status_code == 400
    data = r.get_json()
    assert data["success"] is False


def test_get_task_not_found(client):
    """查询不存在的任务返回 404。"""
    r = client.get("/api/processing/tasks/nonexistent_001")
    assert r.status_code == 404
    data = r.get_json()
    assert data["success"] is False


def test_list_processed_empty(client):
    """空加工数据列表。"""
    r = client.get("/api/processing/processed")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["total"] == 0


def test_list_tasks_with_filter(client, input_dir):
    """任务列表过滤。"""
    client.post("/api/processing/clahe", json={
        "name": "t1", "input_paths": [str(input_dir)], "params": {"clip_limit": 2.0}
    })
    client.post("/api/processing/crop", json={
        "name": "t2", "input_paths": [str(input_dir)], "params": {"tile_size": 640}
    })

    r = client.get("/api/processing/tasks?type=clahe")
    data = r.get_json()
    assert data["data"]["total"] == 1
    assert data["data"]["tasks"][0]["task_type"] == "clahe"
