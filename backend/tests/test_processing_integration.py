"""端到端集成测试：提交任务 → 轮询状态 → 校验 output 结构。"""
import re
import shutil
import time
from pathlib import Path

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"

    import config
    monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(config, "PROCESSING_TASKS_YAML", yaml_path)

    flask_app = create_app()
    flask_app.config["TESTING"] = True

    # 在 create_app()→init_engines() 之后覆盖引擎实例，指向临时目录
    # 必须在 create_app 之后覆盖，否则 init_engines() 会用默认路径重置实例
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


def test_clahe_end_to_end(client, tmp_path):
    """提交 CLAHE 任务 → 等待完成 → 校验 output 目录与 index.json。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    input_dir = tmp_path / "batch_e2e"
    input_dir.mkdir()
    shutil.copy(fixtures / "small_640.jpg", input_dir / "DJI_0001.jpg")
    shutil.copy(fixtures / "small_640.jpg", input_dir / "DJI_0002.jpg")

    # 提交任务
    r = client.post("/api/processing/clahe", json={
        "name": "E2E CLAHE",
        "input_paths": [str(input_dir)],
        "params": {"clip_limit": 2.0, "grid_size": [8, 8]},
    })
    assert r.status_code == 200
    task_id = r.get_json()["data"]["task_id"]

    # 轮询直到完成
    status = "pending"
    for _ in range(30):
        time.sleep(0.5)
        r = client.get(f"/api/processing/tasks/{task_id}")
        status = r.get_json()["data"]["status"]
        if status in ("completed", "failed"):
            break
    assert status == "completed", f"任务未完成: status={status}"

    # 校验任务详情
    r = client.get(f"/api/processing/tasks/{task_id}")
    cfg = r.get_json()["data"]
    assert cfg["processed_images"] == 2
    assert len(cfg["sub_dirs"]) == 1
    assert cfg["sub_dirs"][0]["sub_dir"] == "batch_e2e"

    # 校验文件清单
    r = client.get(f"/api/processing/tasks/{task_id}/files?sub_dir={cfg['sub_dirs'][0]['sub_dir']}")
    assert r.status_code == 200
    files_data = r.get_json()["data"]
    assert files_data["total"] == 2

    # 校验加工数据列表
    r = client.get("/api/processing/processed")
    items = r.get_json()["data"]["items"]
    assert any(i["task_id"] == task_id for i in items)

    # 校验预览
    r = client.get(f"/api/processing/tasks/{task_id}/preview?filename=DJI_0001.jpg&sub_dir={cfg['sub_dirs'][0]['sub_dir']}&size=thumbnail")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_crop_end_to_end(client, tmp_path):
    """提交裁切任务 → 校验子图命名规范。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    input_dir = tmp_path / "crop_e2e"
    input_dir.mkdir()
    shutil.copy(fixtures / "medium_1280.jpg", input_dir / "DJI_0001.JPG")

    r = client.post("/api/processing/crop", json={
        "name": "E2E Crop",
        "input_paths": [str(input_dir)],
        "params": {"tile_size": 640, "overlap_ratio": 0.05},
    })
    task_id = r.get_json()["data"]["task_id"]

    # 等待完成
    status = "pending"
    for _ in range(30):
        time.sleep(0.5)
        r = client.get(f"/api/processing/tasks/{task_id}")
        status = r.get_json()["data"]["status"]
        if status in ("completed", "failed"):
            break
    assert status == "completed", f"任务未完成: status={status}"

    # 校验子图命名
    r = client.get(f"/api/processing/tasks/{task_id}/files?sub_dir=crop_e2e")
    assert r.status_code == 200
    files = r.get_json()["data"]["files"]
    pattern = r"^DJI_0001_tile_\d{4}_x\d+_y\d+\.jpg$"
    for f in files:
        assert re.match(pattern, f["filename"]), f"命名不符: {f['filename']}"

    # 校验 total_tiles > 0
    r = client.get(f"/api/processing/tasks/{task_id}")
    cfg = r.get_json()["data"]
    assert cfg["total_tiles"] > 0


def test_delete_processed_end_to_end(client, tmp_path):
    """提交任务 → 完成 → 删除加工数据 → 确认目录已清理。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    input_dir = tmp_path / "del_e2e"
    input_dir.mkdir()
    shutil.copy(fixtures / "small_640.jpg", input_dir / "a.jpg")

    # 提交并等待完成
    r = client.post("/api/processing/clahe", json={
        "name": "Delete E2E",
        "input_paths": [str(input_dir)],
        "params": {"clip_limit": 2.0, "grid_size": [8, 8]},
    })
    task_id = r.get_json()["data"]["task_id"]

    for _ in range(30):
        time.sleep(0.5)
        r = client.get(f"/api/processing/tasks/{task_id}")
        if r.get_json()["data"]["status"] in ("completed", "failed"):
            break
    assert r.get_json()["data"]["status"] == "completed"

    # 删除加工数据
    r = client.delete(f"/api/processing/processed/{task_id}?delete_output=true")
    assert r.status_code == 200
    assert r.get_json()["success"] is True

    # 确认任务已删除
    r = client.get(f"/api/processing/tasks/{task_id}")
    assert r.status_code == 404

    # 确认加工数据列表中不再包含
    r = client.get("/api/processing/processed")
    items = r.get_json()["data"]["items"]
    assert not any(i["task_id"] == task_id for i in items)
