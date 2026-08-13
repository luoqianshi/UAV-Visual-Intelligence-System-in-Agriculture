"""DatasetAnalyzer 测试。"""
from dataset_analyzer import DatasetAnalyzer
from dataset_factory import build_mini_coco, build_mini_yolo, build_mini_voc


def _make_analyzer(tmp_path, monkeypatch):
    """构建一个 analyzer，其 registry 仅用于路径解析（scan 不需要注册表）。"""
    from dataset_analyzer import DatasetAnalyzer
    return DatasetAnalyzer(registry=None)


def test_scan_coco(tmp_path):
    root = tmp_path / "mini_coco"
    expected = build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "COCO"
    assert result["image_count"] == expected["image_count"]
    assert result["object_count"] == expected["object_count"]
    assert result["classes"] == expected["classes"]
    assert result["splits"]["train"]["image_count"] == 2
    assert result["splits"]["val"]["object_count"] == 1
    assert result["image_size"] == "640x640"
    assert result["version"] == "1.0"
    assert "Mini COCO" in result["description"]


def test_scan_yolo(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "YOLO"
    assert result["image_count"] == 4
    assert result["object_count"] == 6


def test_scan_voc(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "VOC"
    assert result["image_count"] == 4


def test_scan_invalid_path(tmp_path):
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(tmp_path / "nope"))
    assert result["valid"] is False
    assert result["format"] is None


def test_scan_unrecognized(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is False
    assert result["format"] is None


def test_scan_origin_image_count(tmp_path):
    """tile 文件名聚合原图数。"""
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    # mini_coco 4 张图文件名各异 → 4 张原图
    assert result["origin_image_count"] == 4
