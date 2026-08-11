"""CountingEngine 单元测试：高分辨率原图 CLAHE→分块→批量检测→坐标映射→全局NMS→全局二次过滤→计数统计。

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
CONFIG = {
    "name": "test",
    "display_name": "Test",
    "imgsz": 640,
    "conf": 0.25,
    "iou": 0.7,
    "max_det": 300,
}
MODEL_INFO = {"name": "test", "display_name": "Test", "imgsz": 640}


def _build_fake_detector(tile_dets, max_det=300, batch_error=False):
    """构造 MagicMock detector。

    - tile_dets：按子块顺序组织的检测结果列表，无论分批方式如何均按序返回；
    - detect_batch 按批返回；batch_error=True 时抛异常，触发逐块回退路径；
    - detect 仅用于回退后的逐块串行检测。
    """
    detector = MagicMock()
    detector.registry.get_config.return_value = dict(CONFIG)
    state = {"n": 0}

    def next_dets():
        i = state["n"]
        state["n"] += 1
        return [dict(d) for d in tile_dets[i]]

    def fake_detect_batch(images, model_name=None, params=None):
        if batch_error:
            raise RuntimeError("batch inference failed")
        return {
            "batch_detections": [next_dets() for _ in images],
            "max_det": max_det,
            "model_info": MODEL_INFO,
        }

    def fake_detect(image, model_name=None, params=None, draw=False):
        return {
            "detection_data": next_dets(),
            "annotated_image": None,
            "model_info": MODEL_INFO,
            "max_det": max_det,
        }

    detector.detect_batch.side_effect = fake_detect_batch
    detector.detect.side_effect = fake_detect
    return detector


# 两子块受控检测：第 1 块 (ox=0) 检出 conf 0.9，第 2 块 (ox=640) 检出 conf 0.8，
# 映射后 bbox 分别为 [10,10,30,30] 与 [650,10,670,30]，不重叠，NMS 保留两者。
TILE0 = [{"bbox": [10, 10, 30, 30], "confidence": 0.9, "class": 0, "class_name": "Sugarcane Seedling"}]
TILE1 = [{"bbox": [10, 10, 30, 30], "confidence": 0.8, "class": 0, "class_name": "Sugarcane Seedling"}]

# 公共参数：640×1280 图像 + tile_size=640 + overlap=0 → 恰好 2 个子块
TWO_TILE_PARAMS = {"tile_size": 640, "overlap_ratio": 0.0, "nms_iou": 0.5}


# ---------------------------------------------------------------------------
# 1. 端到端 count() 全流程（默认 batch_size，两块同批推理）
# ---------------------------------------------------------------------------
@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_count_full_pipeline(mock_enhance):
    detector = _build_fake_detector([TILE0, TILE1])
    counter = CountingEngine(detector, MagicMock())

    # 形状 (640, 1280, 3)：h=640, w=1280 → slide_window 恰好 2 个 tile
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    progress_calls = []

    def on_progress(stage, current, total):
        progress_calls.append((stage, current, total))

    result = counter.count(
        image,
        params={
            **TWO_TILE_PARAMS,
            "ground_resolution": 0.85,
            "grid_n": 8,
            "enhance": True,  # 显式启用 CLAHE 以测试完整管线（默认已改为关闭）
        },
        on_progress=on_progress,
    )

    # 1. count（默认 global_conf=0.0 关闭二次过滤，0.9/0.8 均保留）
    assert result["count"] == 2
    assert result["filtered_count"] == 0

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

    # 6. tile_count 与子块结果日志：索引/偏移/检出数/未触顶
    assert result["tile_count"] == 2
    assert result["tile_results"] == [
        {"tile_index": 0, "offset_x": 0, "offset_y": 0, "det_count": 1, "max_det_reached": False},
        {"tile_index": 1, "offset_x": 640, "offset_y": 0, "det_count": 1, "max_det_reached": False},
    ]
    assert result["max_det_reached_tiles"] == []

    # 7. annotated_image：非空字符串
    assert isinstance(result["annotated_image"], str)
    assert len(result["annotated_image"]) > 0

    # 8. image_size：[w, h] = [1280, 640]（宽在前，与 spec §7.2 一致）
    assert result["image_size"] == [1280, 640]

    # 9. on_progress：至少一次 "enhancing"，至少两次 "detecting"
    stages = [c[0] for c in progress_calls]
    assert "enhancing" in stages
    assert stages.count("detecting") >= 2

    # 10. 两块同批：detect_batch 仅调用一次，未走逐块 detect
    assert detector.detect_batch.call_count == 1
    assert detector.detect.call_count == 0

    # 附带：model_info 取自 registry 配置 / params_snapshot 透传
    assert result["model_info"] == MODEL_INFO
    assert result["params_snapshot"]["tile_size"] == 640

    # clahe.enhance 被调用一次
    mock_enhance.assert_called_once()


# ---------------------------------------------------------------------------
# 2. 全局二次过滤：global_conf 移除低置信度检测
# ---------------------------------------------------------------------------
@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_count_global_conf_filter(mock_enhance):
    low_conf_tile = [{"bbox": [10, 10, 30, 30], "confidence": 0.3, "class": 0, "class_name": "S"}]
    detector = _build_fake_detector([TILE0, low_conf_tile])
    counter = CountingEngine(detector, MagicMock())
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    result = counter.count(image, params={**TWO_TILE_PARAMS, "global_conf": 0.5})

    # conf 0.3 < global_conf 0.5 → 被二次过滤移除
    assert result["count"] == 1
    assert result["filtered_count"] == 1
    assert result["detection_data"][0]["confidence"] == 0.9
    # 子块日志仍如实记录原始检出数（过滤发生在合并后）
    assert result["tile_results"][1]["det_count"] == 1


@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_count_global_conf_disabled_when_zero(mock_enhance):
    """global_conf <= 0 时关闭二次过滤。"""
    low_conf_tile = [{"bbox": [10, 10, 30, 30], "confidence": 0.3, "class": 0, "class_name": "S"}]
    detector = _build_fake_detector([TILE0, low_conf_tile])
    counter = CountingEngine(detector, MagicMock())
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    result = counter.count(image, params={**TWO_TILE_PARAMS, "global_conf": 0})

    assert result["count"] == 2
    assert result["filtered_count"] == 0


# ---------------------------------------------------------------------------
# 3. max_det 触顶汇总：检出数达到单块上限的块索引写入结果
# ---------------------------------------------------------------------------
@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_max_det_reached_tiles(mock_enhance):
    detector = _build_fake_detector([TILE0, TILE1], max_det=1)
    counter = CountingEngine(detector, MagicMock())
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    result = counter.count(image, params={**TWO_TILE_PARAMS, "max_det": 1})

    assert result["max_det_reached_tiles"] == [0, 1]
    assert all(t["max_det_reached"] for t in result["tile_results"])


# ---------------------------------------------------------------------------
# 4. 批量推理：batch_size 分批 + 失败回退逐块
# ---------------------------------------------------------------------------
@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_batch_size_splits_batches(mock_enhance):
    """batch_size=1：每块单独成批，detect_batch 被逐块调用。"""
    detector = _build_fake_detector([TILE0, TILE1])
    counter = CountingEngine(detector, MagicMock())
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    result = counter.count(image, params={**TWO_TILE_PARAMS, "batch_size": 1})

    assert detector.detect_batch.call_count == 2
    assert result["count"] == 2


@patch("core.counter.clahe.enhance", side_effect=lambda x: x)
def test_batch_fallback_to_sequential(mock_enhance):
    """批量推理异常时回退批内逐块串行检测，结果仍正常产出。"""
    detector = _build_fake_detector([TILE0, TILE1], batch_error=True)
    counter = CountingEngine(detector, MagicMock())
    image = np.zeros((640, 1280, 3), dtype=np.uint8)

    result = counter.count(image, params=TWO_TILE_PARAMS)

    assert detector.detect_batch.call_count == 1
    assert detector.detect.call_count == 2
    assert result["count"] == 2
    assert result["tile_results"][1]["offset_x"] == 640


# ---------------------------------------------------------------------------
# 5. _conf_dist 阈值分档
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
# 6. _heatmap 网格归属
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
