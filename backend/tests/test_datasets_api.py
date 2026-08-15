"""数据集 API 集成测试。"""
import pytest

from dataset_factory import build_mini_coco


@pytest.fixture
def app_with_datasets(tmp_path, monkeypatch):
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    yaml_path = tmp_path / "datasets.yaml"
    from app import create_app
    app = create_app()  # init_engines 用 conftest 重定向的空目录，快
    app.config["TESTING"] = True
    # create_app 后覆盖引擎实例指向 tmp 目录（对齐 test_processing_api 模式）
    from core import engine
    from core.dataset_registry import DatasetRegistry
    from core.dataset_analyzer import DatasetAnalyzer
    reg = DatasetRegistry(datasets_dir=datasets_dir, yaml_path=yaml_path)
    az = DatasetAnalyzer(registry=reg)
    reg.set_analyzer(az)
    reg.load_from_yaml()
    monkeypatch.setattr(engine, "dataset_registry", reg)
    monkeypatch.setattr(engine, "dataset_analyzer", az)
    return app, datasets_dir


def test_list_datasets_empty(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.get("/api/datasets")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["data"]["total"] == 0
    assert body["data"]["format_dist"] == {"YOLO": 0, "COCO": 0, "VOC": 0}


def test_scan_and_import_flow(app_with_datasets):
    app, datasets_dir = app_with_datasets
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    client = app.test_client()
    # scan
    r = client.post("/api/datasets/scan", json={"path": str(coco_dir)})
    assert r.status_code == 200
    assert r.get_json()["data"]["format"] == "COCO"
    # import
    r = client.post("/api/datasets/import", json={"path": str(coco_dir)})
    assert r.status_code == 201
    did = r.get_json()["data"]["dataset_id"]
    # list
    r = client.get("/api/datasets")
    assert r.get_json()["data"]["total"] == 1
    # detail
    r = client.get(f"/api/datasets/{did}")
    assert r.status_code == 200
    assert r.get_json()["data"]["dataset_id"] == did
    # report
    r = client.get(f"/api/datasets/{did}/report")
    assert r.status_code == 200
    rep = r.get_json()["data"]
    assert rep["summary"]["total_images"] == 4
    assert rep["cached"] is False
    # report 缓存命中
    r = client.get(f"/api/datasets/{did}/report")
    assert r.get_json()["data"]["cached"] is True
    # images
    r = client.get(f"/api/datasets/{did}/images?split=train")
    assert r.status_code == 200
    assert r.get_json()["data"]["total"] == 2
    # 随机抽样 50%：train 2 张 → sample_total 1
    r = client.get(f"/api/datasets/{did}/images?split=train&sample_ratio=0.5")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["sampled"] is True
    assert data["sample_total"] == 1
    # preview
    r = client.get(f"/api/datasets/{did}/images/img_t1.jpg/preview?split=train&size=thumbnail")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_scan_invalid_returns_400(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.post("/api/datasets/scan", json={"path": "/nope/missing"})
    assert r.status_code == 400


def test_get_missing_404(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.get("/api/datasets/nope")
    assert r.status_code == 404


def test_delete_registry_only(app_with_datasets):
    app, datasets_dir = app_with_datasets
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    client = app.test_client()
    did = client.post("/api/datasets/import", json={"path": str(coco_dir)}).get_json()["data"]["dataset_id"]
    r = client.delete(f"/api/datasets/{did}")
    assert r.status_code == 200
    assert coco_dir.exists()  # 文件保留
    r = client.get(f"/api/datasets/{did}")
    assert r.status_code == 404
