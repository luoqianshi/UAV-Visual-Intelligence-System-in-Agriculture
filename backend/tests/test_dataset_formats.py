"""dataset_formats 纯函数解析器测试。"""
from pathlib import Path

from dataset_formats import detect_format, parse_coco

from dataset_factory import build_mini_coco


def test_detect_coco(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    assert detect_format(root) == "COCO"


def test_detect_unknown(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    assert detect_format(root) is None


def test_parse_coco_coordinates_and_classes(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    ir = parse_coco(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert ir["meta"]["version"] == "1.0"
    assert ir["meta"]["contributor"] == "tester"
    # 4 张图
    assert len(ir["images"]) == 4
    # 第一张图 3 个框，绝对像素坐标 [x,y,w,h]
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    assert len(t1["boxes"]) == 3
    assert t1["boxes"][0]["bbox"] == [10, 20, 30, 40]
    assert t1["boxes"][0]["class_id"] == 0  # COCO category_id 1 → 内部 0
    assert t1["split"] == "train"
    # origin_stem 无 tile 后缀时等于 stem
    assert t1["origin_stem"] == "img_t1"


def test_parse_coco_tile_origin_stem(tmp_path):
    root = tmp_path / "mini_coco"
    expected = build_mini_coco(root)
    # 重命名为 tile 文件名验证 origin_stem 解析
    ir = parse_coco(root)
    img = ir["images"][0]
    # 夹具用普通名，手动验证解析函数逻辑
    import dataset_formats as df
    assert df._tile_origin_stem("DJI_20250511172207_0003_D_tile_0000_x0_y0") == \
        "DJI_20250511172207_0003_D"
    assert df._tile_origin_stem("plain_img") == "plain_img"
