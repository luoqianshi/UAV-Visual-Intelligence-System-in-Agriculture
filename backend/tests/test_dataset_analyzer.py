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


def test_compute_report_heavy_stats_and_cache(tmp_path):
    """报告重统计 + 缓存命中。"""
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    # 伪造一个 dataset 配置（registry 为 None 时直接传配置）
    cfg = {"dataset_id": "ds1", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    rep1 = az.compute_report(cfg, force=False)
    assert rep1["summary"]["total_images"] == 4
    assert rep1["summary"]["total_objects"] == 6
    assert rep1["summary"]["non_empty_images"] == 4
    assert abs(rep1["bbox_stats"]["avg_width"] - 43.75) < 1  # (30+50+60+20+40+40)/6
    assert rep1["cached"] is False
    # size_dist 分 split 分组：all/train/val/test 均存在
    sd = rep1["bbox_stats"]["size_dist"]
    assert {"all", "train", "val", "test"} <= set(sd)
    assert abs(sd["all"]["small"] + sd["all"]["medium"] + sd["all"]["large"] - 1.0) < 0.01
    # 每图实例数统计：[3,1,1,1] → avg 1.5
    ipi = rep1["image_stats"]["instances_per_image"]
    assert ipi["avg"] == 1.5
    assert ipi["max"] == 3 and ipi["min"] == 1
    assert sum(c for _, c in ipi["hist"]) == 4
    # 缓存命中
    rep2 = az.compute_report(cfg, force=False)
    assert rep2["cached"] is True


def test_compute_report_force_recompute(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    cfg = {"dataset_id": "ds2", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    az.compute_report(cfg, force=False)
    rep = az.compute_report(cfg, force=True)
    assert rep["cached"] is False


def test_compute_report_per_image_instances(tmp_path):
    """每图实例数直方图：mini_coco 为 [3,1,1,1]。"""
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    cfg = {"dataset_id": "ds3", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    rep = az.compute_report(cfg, force=True)
    ipi = rep["image_stats"]["instances_per_image"]
    assert ipi["avg"] == 1.5
    # 整数值直方图：1→3 张、3→1 张
    assert [[1, 1], 3] in ipi["hist"]
    assert [[3, 3], 1] in ipi["hist"]
    assert sum(c for _, c in ipi["hist"]) == 4
    # warnings 字段已移除
    assert "warnings" not in rep
