"""DetectionEngine 单元测试：原子化单图 YOLO 推理。

通过 MagicMock 模拟 registry 与 YOLO 引擎的 predict 结果，规避对
ultralytics / torch 的真实依赖。运行：cd backend && python -m pytest tests/test_detector.py -v
"""
import base64
from unittest.mock import MagicMock

import numpy as np
import pytest

from core.detector import DetectionEngine


# ---------------------------------------------------------------------------
# 测试夹具：构造假的 registry + 假的 YOLO result
# ---------------------------------------------------------------------------
CONFIG = {
    "name": "test",
    "display_name": "Test",
    "imgsz": 640,
    "conf": 0.5,
    "iou": 0.3,
    "max_det": 300,
    "device": "cpu",
    "classes": ["Sugarcane Seedling"],
}


class FakeRegistry:
    """最小化的 registry 替身，仅暴露 get_config / get_engine。"""

    def __init__(self, engine, config=None):
        self._engine = engine
        self._config = config if config is not None else CONFIG

    def get_config(self, name=None):
        return dict(self._config)

    def get_engine(self, name=None):
        return self._engine


def _make_result_one_box():
    """构造一个含单个检测框的 fake YOLO result。"""
    result = MagicMock()
    boxes = MagicMock()
    # 让 len(result.boxes) == 1
    boxes.__len__.return_value = 1
    boxes.xyxy.cpu.return_value.numpy.return_value = np.array([[10, 20, 50, 60]])
    boxes.conf.cpu.return_value.numpy.return_value = np.array([0.9])
    boxes.cls.cpu.return_value.numpy.return_value = np.array([0])
    result.boxes = boxes
    return result


def _make_result_empty():
    """构造一个无检测框的 fake YOLO result（boxes 为 None）。"""
    result = MagicMock()
    result.boxes = None
    return result


def _build_engine(result):
    engine = MagicMock()
    engine.predict.return_value = [result]
    return engine


# ---------------------------------------------------------------------------
# 1. detect(draw=False)：解析检测数据，不绘制
# ---------------------------------------------------------------------------
def test_detect_no_draw():
    result = _make_result_one_box()
    engine = _build_engine(result)
    registry = FakeRegistry(engine)
    detector = DetectionEngine(registry)

    out = detector.detect("dummy.jpg", draw=False)

    detection_data = out["detection_data"]
    assert len(detection_data) == 1
    det = detection_data[0]
    assert det["bbox"] == [10.0, 20.0, 50.0, 60.0]
    assert det["confidence"] == pytest.approx(0.9)
    assert det["class"] == 0
    assert det["class_name"] == "Sugarcane Seedling"

    # draw=False 时不应绘制
    assert out["annotated_image"] is None

    # model_info 校验
    assert out["model_info"]["name"] == "test"
    assert out["model_info"]["display_name"] == "Test"
    assert out["model_info"]["imgsz"] == 640

    # 验证 predict 被以正确的推理参数调用
    engine.predict.assert_called_once()
    _, kwargs = engine.predict.call_args
    assert kwargs["imgsz"] == 640
    assert kwargs["conf"] == 0.5
    assert kwargs["iou"] == 0.3
    assert kwargs["max_det"] == 300
    assert kwargs["device"] == "cpu"
    assert kwargs["verbose"] is False


# ---------------------------------------------------------------------------
# 2. detect(draw=True) 传 numpy 图像：返回 base64 标注图
# ---------------------------------------------------------------------------
def test_detect_with_draw_numpy_image():
    result = _make_result_one_box()
    engine = _build_engine(result)
    registry = FakeRegistry(engine)
    detector = DetectionEngine(registry)

    image = np.zeros((100, 100, 3), dtype=np.uint8)
    out = detector.detect(image)  # draw 默认 True

    detection_data = out["detection_data"]
    assert len(detection_data) == 1

    annotated = out["annotated_image"]
    assert annotated is not None
    assert isinstance(annotated, str)
    assert len(annotated) > 0
    # 能解码为合法 base64 且可还原为图像
    decoded = base64.b64decode(annotated)
    assert len(decoded) > 0
    arr = np.frombuffer(decoded, dtype=np.uint8)
    img = __import__("cv2").imdecode(arr, __import__("cv2").IMREAD_COLOR)
    assert img is not None
    assert img.shape[0] == 100 and img.shape[1] == 100


# ---------------------------------------------------------------------------
# 3. 空结果：detection_data 为空且无标注图
# ---------------------------------------------------------------------------
def test_detect_empty_results():
    result = _make_result_empty()
    engine = _build_engine(result)
    registry = FakeRegistry(engine)
    detector = DetectionEngine(registry)

    image = np.zeros((50, 50, 3), dtype=np.uint8)
    out = detector.detect(image, draw=True)

    assert out["detection_data"] == []
    # 无检测结果时即使 draw=True 也不应绘制
    assert out["annotated_image"] is None
    assert out["model_info"]["name"] == "test"


# ---------------------------------------------------------------------------
# 4. 参数覆盖：params 优先于 config
# ---------------------------------------------------------------------------
def test_detect_params_override_config():
    result = _make_result_one_box()
    engine = _build_engine(result)
    registry = FakeRegistry(engine)
    detector = DetectionEngine(registry)

    detector.detect(
        "dummy.jpg",
        draw=False,
        params={"imgsz": 1280, "conf": 0.25, "iou": 0.5, "max_det": 10, "device": "cuda"},
    )

    _, kwargs = engine.predict.call_args
    assert kwargs["imgsz"] == 1280
    assert kwargs["conf"] == 0.25
    assert kwargs["iou"] == 0.5
    assert kwargs["max_det"] == 10
    assert kwargs["device"] == "cuda"


# ---------------------------------------------------------------------------
# 5. class_name 越界回退为字符串
# ---------------------------------------------------------------------------
def test_detect_class_index_out_of_range():
    result = _make_result_one_box()
    # 让类别索引超出 classes 列表长度
    result.boxes.cls.cpu.return_value.numpy.return_value = np.array([5])
    engine = _build_engine(result)
    registry = FakeRegistry(engine)
    detector = DetectionEngine(registry)

    out = detector.detect("dummy.jpg", draw=False)
    det = out["detection_data"][0]
    assert det["class"] == 5
    # 越界时 class_name 回退为字符串形式的索引
    assert det["class_name"] == "5"
