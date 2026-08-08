"""Task 13：Mock 只读 API 测试。

因 app.py 仅注册 health_bp（本任务不允许修改 app.py），故在测试内部
新建一个 Flask 应用并注册三个 mock blueprint，直接验证路由行为。
"""
import pytest
from flask import Flask

from api.batches_api import batches_bp
from api.processing_api import processing_bp
from api.datasets_api import datasets_bp


@pytest.fixture()
def client():
    def make_app():
        app = Flask(__name__)
        app.register_blueprint(batches_bp)
        app.register_blueprint(processing_bp)
        app.register_blueprint(datasets_bp)
        return app

    app = make_app()
    app.testing = True
    return app.test_client()


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------
def test_list_batches_default(client):
    resp = client.get("/api/batches")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["total"] == 3
    assert len(body["data"]["batches"]) == 3


def test_list_batches_filter_crop_type(client):
    # 甘蔗 → 3 条
    resp = client.get("/api/batches?crop_type=sugarcane")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 3
    # 小麦 → 0 条
    resp = client.get("/api/batches?crop_type=wheat")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["total"] == 0


def test_list_batches_filter_status(client):
    resp = client.get("/api/batches?status=已完成")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 1
    assert body["data"]["batches"][0]["status"] == "已完成"


def test_create_batch_demo(client):
    resp = client.post("/api/batches", json={"name": "demo"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert "V1 演示模式" in body["message"]


def test_get_batch_detail(client):
    first_id = client.get("/api/batches").get_json()["data"]["batches"][0]["id"]
    resp = client.get(f"/api/batches/{first_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == first_id


def test_get_batch_not_found(client):
    resp = client.get("/api/batches/nope_xyz")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False


def test_list_batch_images(client):
    first_id = client.get("/api/batches").get_json()["data"]["batches"][0]["id"]
    resp = client.get(f"/api/batches/{first_id}/images")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 12
    assert len(body["data"]["images"]) == 12
    assert body["data"]["images"][0]["file"] == "DJI_0001.jpg"
    assert body["data"]["images"][0]["width"] == 5472
    assert body["data"]["images"][0]["height"] == 3648


def test_batch_image_preview(client):
    first_id = client.get("/api/batches").get_json()["data"]["batches"][0]["id"]
    resp = client.get(f"/api/batches/{first_id}/images/DJI_0001.jpg/preview")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert len(resp.data) > 0


# ---------------------------------------------------------------------------
# Processing tasks
# ---------------------------------------------------------------------------
def test_list_tasks_default(client):
    resp = client.get("/api/processing/tasks")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 7
    assert len(body["data"]["tasks"]) == 7


def test_list_tasks_filter_type(client):
    resp = client.get("/api/processing/tasks?type=clahe")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 4
    assert all(t["type"] == "clahe" for t in body["data"]["tasks"])

    resp = client.get("/api/processing/tasks?type=crop")
    assert resp.get_json()["data"]["total"] == 3


def test_list_tasks_filter_status_processing(client):
    resp = client.get("/api/processing/tasks?status=processing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 1
    task = body["data"]["tasks"][0]
    assert task["status"] == "processing"
    assert task["progress"] == 72
    assert task["name"] == "滑窗裁切 640/0.1"


def test_list_tasks_status_distribution(client):
    tasks = client.get("/api/processing/tasks").get_json()["data"]["tasks"]
    from collections import Counter
    dist = dict(Counter(t["status"] for t in tasks))
    assert dist == {"completed": 5, "failed": 1, "processing": 1}


def test_get_task_detail(client):
    first_id = client.get(
        "/api/processing/tasks"
    ).get_json()["data"]["tasks"][0]["id"]
    resp = client.get(f"/api/processing/tasks/{first_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == first_id
    assert "params" in body["data"]


def test_get_task_not_found(client):
    resp = client.get("/api/processing/tasks/nope_xyz")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_task_preview(client):
    first_id = client.get(
        "/api/processing/tasks"
    ).get_json()["data"]["tasks"][0]["id"]
    resp = client.get(f"/api/processing/tasks/{first_id}/preview")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert len(resp.data) > 0


def test_task_preview_with_type_param(client):
    first_id = client.get(
        "/api/processing/tasks"
    ).get_json()["data"]["tasks"][0]["id"]
    resp = client.get(f"/api/processing/tasks/{first_id}/preview?type=original")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
def test_list_datasets_default(client):
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 4
    assert len(body["data"]["datasets"]) == 4
    dist = body["data"]["format_dist"]
    assert set(dist.keys()) >= {"YOLO", "COCO", "VOC"}
    assert dist["YOLO"] == 2
    assert dist["COCO"] == 1
    assert dist["VOC"] == 1


def test_list_datasets_filter_format(client):
    resp = client.get("/api/datasets?format=YOLO")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["total"] == 2
    assert all(d["format"] == "YOLO" for d in body["data"]["datasets"])

    resp = client.get("/api/datasets?format=COCO")
    assert resp.get_json()["data"]["total"] == 1


def test_get_dataset_detail(client):
    first_id = client.get("/api/datasets").get_json()["data"]["datasets"][0]["id"]
    resp = client.get(f"/api/datasets/{first_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == first_id


def test_get_dataset_not_found(client):
    resp = client.get("/api/datasets/nope_xyz")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_dataset_report(client):
    first_id = client.get("/api/datasets").get_json()["data"]["datasets"][0]["id"]
    resp = client.get(f"/api/datasets/{first_id}/report")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["dataset_id"] == first_id
    summary = data["summary"]
    # train + val + test 必须等于 total
    total = summary["total_samples"]
    assert summary["train_count"] + summary["val_count"] + summary["test_count"] == total
    assert "split_ratio" in summary
    assert isinstance(data["class_dist"], list)
    assert len(data["class_dist"]) >= 1
    assert "format" in data
    assert "generated_at" in data


def test_dataset_report_not_found(client):
    resp = client.get("/api/datasets/nope_xyz/report")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False
