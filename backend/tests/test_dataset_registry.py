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
