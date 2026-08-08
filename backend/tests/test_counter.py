"""CountingEngine 单元测试：高分辨率原图 CLAHE→分块→逐块检测→坐标映射→全局NMS→计数统计。

通过 MagicMock 模拟 detector（规避 ultralytics / torch），patch clahe.enhance 为
passthrough，使整条管线对纯 numpy 数据确定性可测。
运行：cd backend && python -m pytest tests/test_counter.py -v
"""
from unittest.mock import MagicMock, patch

import numpy as np

from core.counter import CountingEngine


# ---------------------------------------------------------------------------
# 夹具：构造返回受控检测结果的 fake detector
# ---------------------------------------------------------------------------
MODEL_INFO = {"name": "test", "display_name": "Test", "imgsz": 640}


def _build_fake_detector():
    """构造一个 MagicMock detector，其 detect 按调用次序返回受控检测。

    - 第 1 次调用（tile 0, ox=0, oy=0）：返回 bbox [10,10,30,30] conf 0.9
      → map_to_original 后仍为 [10,10,30,30]
    - 第 2 次调用（tile 1, ox=640, oy=0）：返回 bbox [10,10,30,30] conf 0.8
      → map_to_original 后变为 [650,10,670,30]，与第一块不重叠，NMS 保留两者
    """
    detector = MagicMock()
    call_count = {"n": 0}

    def fake_detect(image, model_name=None, params=None, draw=False):
        call_count["n"] += 1
        if call_count["n"] == 1:
            dets = [
                {
                    "bbox": [10, 10, 30, 30],
                    "confidence": 0.9,
                    "class": 0,
                    "class_name": "Sugarcane Seedling",
                }
            ]
        else:
            dets = [
                {
                    "bbox": [10, 10, 30, 30],
                    "confidence": 0.8,
                    "class": 0,
                    "class_name": "Sugarcane Seedling",
                }
            ]
        return {
            "detection_data": dets,
            "annotated_image": None,
            "model_info": MODEL_INFO,
        }

    detector.detect.side_effect = fake_detect
    return detector


# ---------------------------------------------------------------------------
# 1. 端到端 count() 全流程
# ---------------------------------------------------------------------------
@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_count_full_pipeline(mock_enhance):
    detector = _build_fake_detector()
    task_manager = MagicMock()
    counter = CountingEngine(detector, task_manager)

    # 形状 (640, 1280, 3)：h=640, w=1280
    # slide_window(tile_size=640, overlap_ratio=0.0) → 恰好 2 个 tile
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    progress_calls = []

    def on_progress(stage, current, total):
        progress_calls.append((stage, current, total))

    result = counter.count(
        image,
        params={
            "tile_size": 640,
            "overlap_ratio": 0.0,
            "nms_iou": 0.5,
            "ground_resolution": 0.85,
            "grid_n": 8,
        },
        on_progress=on_progress,
    )

    # 1. count
    assert result["count"] == 2

    # 2. detection_data：2 项，带 id，bbox 已映射到原图坐标
    dets = result["detection_data"]
    assert len(dets) == 2
    assert dets[0]["id"] == 1
    assert dets[1]["id"] == 2
    # NMS 按置信度降序：0.9 在前 → bbox [10,10,30,30]；0.8 在后 → [650,10,670,30]
    assert dets[0]["bbox"] == [10, 10, 30, 30]
    assert dets[1]["bbox"] == [650, 10, 670, 30]

    # 3. heatmap：8×8，所有格子之和 == 2
    hm = result["heatmap"]
    assert len(hm) == 8
    assert all(len(row) == 8 for row in hm)
    assert sum(sum(row) for row in hm) == 2

    # 4. confidence_dist：两个 conf 均 ≥0.7 → high
    assert result["confidence_dist"] == {"high": 2, "mid": 0, "low": 0}

    # 5. area_m2
    assert result["area_m2"] == round(1280 * 640 * (0.85 / 100) ** 2, 2)

    # 6. tile_count
    assert result["tile_count"] == 2

    # 7. annotated_image：非空字符串
    assert isinstance(result["annotated_image"], str)
    assert len(result["annotated_image"]) > 0

    # 8. image_size：[w, h] = [1280, 640]（宽在前，与 spec §7.2 一致）
    assert result["image_size"] == [1280, 640]

    # 9. on_progress：至少一次 "enhancing"，至少两次 "detecting"
    stages = [c[0] for c in progress_calls]
    assert "enhancing" in stages
    assert stages.count("detecting") >= 2

    # 附带：model_info / params_snapshot 透传
    assert result["model_info"] == MODEL_INFO
    assert result["params_snapshot"]["tile_size"] == 640

    # clahe.enhance 被调用一次
    mock_enhance.assert_called_once()


# ---------------------------------------------------------------------------
# 2. _conf_dist 阈值分档
# ---------------------------------------------------------------------------
def test_conf_dist_thresholds():
    counter = CountingEngine(MagicMock(), MagicMock())
    dets = [
        {"confidence": 0.9},  # high (>=0.7)
        {"confidence": 0.5},  # mid  (>=0.4)
        {"confidence": 0.2},  # low  (<0.4)
    ]
    assert counter._conf_dist(dets) == {"high": 1, "mid": 1, "low": 1}


# ---------------------------------------------------------------------------
# 3. _heatmap 网格归属
# ---------------------------------------------------------------------------
def test_heatmap_grid_assignment():
    counter = CountingEngine(MagicMock(), MagicMock())
    # w=1280, h=640, n=8 → cw=160, ch=80
    dets = [
        # 中心 (20, 20) → col=0, row=0
        {"bbox": [10, 10, 30, 30]},
        # 中心 (660, 20) → col=4, row=0
        {"bbox": [650, 10, 670, 30]},
    ]
    hm = counter._heatmap(dets, 1280, 640, 8)
    assert len(hm) == 8 and all(len(r) == 8 for r in hm)
    assert hm[0][0] == 1
    assert hm[0][4] == 1
    assert sum(sum(r) for r in hm) == 2
