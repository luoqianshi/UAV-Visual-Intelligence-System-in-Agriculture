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


from dataset_factory import build_mini_yolo, build_mini_voc
from dataset_formats import detect_format, parse_yolo, parse_voc


def test_detect_yolo(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    assert detect_format(root) == "YOLO"


def test_detect_voc(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    assert detect_format(root) == "VOC"


def test_parse_yolo_ignores_stale_path(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    ir = parse_yolo(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert ir["meta"]["format"] == "YOLO"
    assert len(ir["images"]) == 4
    # 归一化坐标 → 绝对像素（640x640），IR bbox 为左上角 [x,y,w,h]
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    # 中心点 0.078125*640=50, 0.34375*640=220；宽高 0.046875*640=30, 0.0625*640=40
    # 左上角 x=50-30/2=35, y=220-40/2=200
    bx = t1["boxes"][0]["bbox"]
    assert abs(bx[0] - 35.0) < 1 and abs(bx[1] - 200.0) < 1
    assert abs(bx[2] - 30.0) < 1 and abs(bx[3] - 40.0) < 1
    assert t1["boxes"][0]["class_id"] == 0
    assert t1["split"] == "train"


def test_parse_voc_ignores_stale_path(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    ir = parse_voc(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert len(ir["images"]) == 4
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    # VOC xmin,ymin,xmax,ymax → [x,y,w,h]
    assert t1["boxes"][0]["bbox"] == [10.0, 20.0, 30.0, 40.0]  # 10,20,40,60 → 10,20,30,40
    assert t1["boxes"][0]["class_id"] == 0
    assert t1["split"] == "train"


def test_parse_yolo_empty_label(tmp_path):
    """空标注 .txt 保留空 boxes。"""
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    # 追加一张空标注图
    from dataset_factory import _make_jpg
    _make_jpg(root / "images" / "train" / "empty.jpg")
    (root / "labels" / "train" / "empty.txt").write_text("", encoding="utf-8")
    ir = parse_yolo(root)
    empty = next(im for im in ir["images"] if im["filename"] == "empty.jpg")
    assert empty["boxes"] == []
