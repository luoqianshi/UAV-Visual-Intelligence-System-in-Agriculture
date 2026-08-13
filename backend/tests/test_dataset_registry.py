"""DatasetRegistry 测试。"""
from dataset_registry import DatasetRegistry
from dataset_analyzer import DatasetAnalyzer
from dataset_factory import build_mini_coco


def _make_registry(tmp_path):
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir(exist_ok=True)
    yaml_path = tmp_path / "datasets.yaml"
    reg = DatasetRegistry(datasets_dir=datasets_dir, yaml_path=yaml_path)
    az = DatasetAnalyzer(registry=reg)
    reg.set_analyzer(az)
    return reg, datasets_dir, yaml_path


def test_auto_discover_registers_coco(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    reg.load_from_yaml()
    ds = reg.list_datasets()
    assert len(ds) == 1
    assert ds[0]["format"] == "COCO"
    assert ds[0]["source"] == "imported"
    assert ds[0]["image_count"] == 4
    assert ds[0]["dataset_id"] == "dataset_mini_coco"


def test_auto_discover_skips_unrecognized(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    (datasets_dir / "not_a_dataset").mkdir()
    (datasets_dir / "not_a_dataset" / "random.txt").write_text("x")
    reg.load_from_yaml()
    assert reg.list_datasets() == []


def test_yaml_persistence_roundtrip(tmp_path):
    reg, datasets_dir, yaml_path = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    # 重新加载验证持久化
    reg2, _, _ = _make_registry(tmp_path)
    reg2.load_from_yaml()
    assert len(reg2.list_datasets()) == 1
    assert yaml_path.exists()


def test_get_dataset_missing_raises(tmp_path):
    reg, _, _ = _make_registry(tmp_path)
    reg.load_from_yaml()
    try:
        reg.get_dataset("nope")
        assert False, "应抛 KeyError"
    except KeyError:
        pass


def test_format_dist(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    dist = reg.format_dist()
    assert dist["COCO"] == 1
    assert dist["YOLO"] == 0


def test_list_datasets_format_filter(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    assert len(reg.list_datasets(fmt="COCO")) == 1
    assert len(reg.list_datasets(fmt="YOLO")) == 0


from pathlib import Path


def test_scan_path(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    result = reg.scan_path(str(coco_dir))
    assert result["valid"] is True
    assert result["format"] == "COCO"


def test_import_dataset(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    assert cfg["dataset_id"] == "dataset_mini_coco"
    assert cfg["format"] == "COCO"
    assert cfg["source"] == "imported"
    # dataset_meta.json 生成
    assert (coco_dir / "dataset_meta.json").exists()
    # 已注册
    assert reg.get_dataset(cfg["dataset_id"])["image_count"] == 4


def test_import_duplicate_name_raises(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    reg.import_dataset(str(coco_dir))
    try:
        reg.import_dataset(str(coco_dir))
        assert False, "重复导入应抛 ValueError"
    except ValueError:
        pass


def test_import_unrecognized_raises(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    bad = datasets_dir / "bad"
    bad.mkdir()
    try:
        reg.import_dataset(str(bad))
        assert False
    except ValueError:
        pass


def test_delete_registry_only(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    reg.delete_dataset(cfg["dataset_id"], delete_files=False)
    # 注册删除，文件保留
    assert coco_dir.exists()
    # 加入 ignored_folders
    assert "Mini_COCO" in reg._ignored_folders


def test_delete_with_files(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    reg.delete_dataset(cfg["dataset_id"], delete_files=True)
    assert not coco_dir.exists()


def test_list_images_pagination(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    result = reg.list_images(cfg["dataset_id"], split="train", page=1, page_size=2)
    assert result["total"] == 2
    assert len(result["images"]) == 2
    assert result["images"][0]["thumbnail_url"].startswith(
        f"/api/datasets/{cfg['dataset_id']}/images/")


def test_list_images_missing_split(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    result = reg.list_images(cfg["dataset_id"], split="train", page=1, page_size=50)
    assert result["total"] == 2


def test_get_image_preview(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    img_bytes = reg.get_image_preview(cfg["dataset_id"], "img_t1.jpg",
                                      split="train", size="thumbnail")
    assert len(img_bytes) > 0
