"""BatchRegistry 单元测试：YAML 加载 / 自动扫描 / CRUD / 图片索引 / 缩略图。

运行：cd backend && python -m pytest tests/test_batch_registry.py -v
"""
import io
import pytest
from pathlib import Path
from PIL import Image

from core.batch_registry import BatchRegistry


def _make_test_image(folder: Path, name: str, size=(100, 100), color=(255, 0, 0)):
    """在指定文件夹创建测试 JPEG 图片。"""
    img = Image.new("RGB", size, color)
    path = folder / name
    img.save(path, "JPEG")
    return path


def _make_batch_yaml(tmp_path: Path, batches=None, ignored=None):
    """写入临时 batches.yaml。"""
    import yaml
    content = {"batches": batches or [], "ignored_folders": ignored or []}
    yaml_file = tmp_path / "batches.yaml"
    yaml_file.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")
    return yaml_file


# ---------------------------------------------------------------------------
# 1. 空 YAML 加载 + 自动发现
# ---------------------------------------------------------------------------
def test_load_empty_yaml_and_autodiscover(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # 创建一个测试架次文件夹
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "DJI_0001.JPG")
    _make_test_image(batch_dir, "DJI_0002.JPG")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    batches = registry.list_batches()
    assert len(batches) == 1
    b = batches[0]
    assert b["batch_name"] == "sugarcane_20250419_5m"
    assert b["crop_type"] == "甘蔗"
    assert b["flight_date"] == "2025-04-19"
    assert b["flight_altitude_m"] == 5.0
    assert b["image_count"] == 2
    assert b["status"] == "ready"
    assert "JPEG" in b["image_formats"]
    # YAML 应已自动保存
    assert yaml_path.exists()


def test_autodiscover_skips_ignored_folders(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "DJI_0001.JPG")

    # 创建 YAML，标记该文件夹为已忽略
    yaml_path = _make_batch_yaml(tmp_path, ignored=["sugarcane_20250419_5m"])
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    assert len(registry.list_batches()) == 0


# ---------------------------------------------------------------------------
# 2. CRUD 操作
# ---------------------------------------------------------------------------
def test_create_and_get_batch(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    external_dir = tmp_path / "external_images"
    external_dir.mkdir()
    _make_test_image(external_dir, "test1.jpg")
    _make_test_image(external_dir, "test2.jpg")
    _make_test_image(external_dir, "test3.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    cfg = registry.create_batch({
        "batch_name": "test_batch",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(external_dir),
        "plot_name": "A区",
    })

    assert cfg["image_count"] == 3
    assert cfg["crop_type"] == "甘蔗"
    assert cfg["status"] == "ready"

    fetched = registry.get_batch(cfg["batch_id"])
    assert fetched["batch_name"] == "test_batch"
    assert fetched["plot_name"] == "A区"


def test_create_batch_invalid_path(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    with pytest.raises(ValueError, match="路径不存在"):
        registry.create_batch({
            "batch_name": "bad",
            "crop_type": "甘蔗",
            "flight_date": "2026-08-10",
            "image_folder_path": str(tmp_path / "nonexistent"),
        })


def test_update_batch(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "t.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "update_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })
    bid = cfg["batch_id"]

    updated = registry.update_batch(bid, {"plot_name": "B区", "description": "更新了描述"})
    assert updated["plot_name"] == "B区"
    assert updated["description"] == "更新了描述"
    # batch_id 和 image_folder_path 不可变
    assert updated["batch_id"] == bid
    assert updated["image_count"] == 1


def test_delete_batch_autodiscovered_adds_to_ignored(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    batch_dir = data_dir / "sugarcane_20250419_5m"
    batch_dir.mkdir()
    _make_test_image(batch_dir, "dji.JPG")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    batches = registry.list_batches()
    assert len(batches) == 1
    bid = batches[0]["batch_id"]

    registry.delete_batch(bid)
    assert len(registry.list_batches()) == 0
    # 重新加载，该文件夹应被忽略
    registry2 = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry2.load_from_yaml()
    assert len(registry2.list_batches()) == 0


# ---------------------------------------------------------------------------
# 3. 图片列表分页
# ---------------------------------------------------------------------------
def test_list_images_pagination(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "imgs"
    ext_dir.mkdir()
    for i in range(15):
        _make_test_image(ext_dir, f"IMG_{i:03d}.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "pag_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })

    # 默认 page_size=50，一页显示全部
    result = registry.list_images(cfg["batch_id"], page=1, page_size=50)
    assert result["total"] == 15
    assert len(result["images"]) == 15

    # page_size=5
    result = registry.list_images(cfg["batch_id"], page=1, page_size=5)
    assert result["total"] == 15
    assert result["total_pages"] == 3
    assert len(result["images"]) == 5
    assert result["images"][0]["thumbnail_url"].startswith("/api/batches/")


# ---------------------------------------------------------------------------
# 4. 缩略图生成
# ---------------------------------------------------------------------------
def test_generate_thumbnail(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "imgs"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "test.jpg", size=(800, 600))

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()
    cfg = registry.create_batch({
        "batch_name": "thumb_test",
        "crop_type": "甘蔗",
        "flight_date": "2026-08-10",
        "image_folder_path": str(ext_dir),
    })

    thumb = registry.get_image_preview(cfg["batch_id"], "test.jpg", size="thumbnail")
    assert len(thumb) > 0
    # 验证是有效 JPEG
    img = Image.open(io.BytesIO(thumb))
    assert img.format == "JPEG"
    assert max(img.size) <= 400


# ---------------------------------------------------------------------------
# 5. 路径预检扫描
# ---------------------------------------------------------------------------
def test_scan_path_valid(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ext_dir = tmp_path / "scan_me"
    ext_dir.mkdir()
    _make_test_image(ext_dir, "a.jpg")

    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    result = registry.scan_path(str(ext_dir))
    assert result["valid"] is True
    assert result["image_count"] == 1


def test_scan_path_nonexistent(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    yaml_path = tmp_path / "batches.yaml"
    registry = BatchRegistry(data_dir=data_dir, yaml_path=yaml_path)
    registry.load_from_yaml()

    result = registry.scan_path(str(tmp_path / "no_such_dir"))
    assert result["valid"] is False
