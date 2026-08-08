"""计数引擎：高分辨率原图 CLAHE→分块→逐块检测→坐标映射→全局NMS→计数统计。"""
import base64

import cv2
import numpy as np

from core import clahe, tiling, nms


class CountingEngine:
    """计数引擎：编排 CLAHE / 分块 / 检测 / 映射 / NMS / 统计 / 可视化。

    - 由外部注入 detector 与 task_manager；
    - count() 对整张原图执行全流程并返回结构化结果。
    """

    def __init__(self, detector, task_manager):
        self.detector = detector
        self.task_manager = task_manager

    def count(self, image, model_name=None, params=None, on_progress=None) -> dict:
        params = params or {}
        tile_size = params.get("tile_size", 640)
        overlap_ratio = params.get("overlap_ratio", 0.05)
        nms_iou = params.get("nms_iou", 0.5)
        ground_res = params.get("ground_resolution", 0.85)  # cm/px
        grid_n = params.get("grid_n", 8)

        # ① 加载原图
        if isinstance(image, str):
            original = cv2.imread(image)
            original = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
        else:
            original = image
        h, w = original.shape[:2]

        # ② CLAHE
        if on_progress:
            on_progress("enhancing", 0, 1)
        enhanced = clahe.enhance(original)

        # ③ 分块
        tiles = tiling.slide_window(enhanced, tile_size, overlap_ratio)

        # ④ 逐块检测 + 坐标映射
        all_dets = []
        r = {}
        for i, (tile, ox, oy) in enumerate(tiles):
            if on_progress:
                on_progress("detecting", i + 1, len(tiles))
            r = self.detector.detect(tile, model_name=model_name, params=params, draw=False)
            for det in r["detection_data"]:
                det["bbox"] = tiling.map_to_original(det["bbox"], ox, oy)
                all_dets.append(det)

        # ⑤ NMS + 编号
        merged = nms.global_nms(all_dets, nms_iou)
        for idx, det in enumerate(merged, 1):
            det["id"] = idx

        # ⑥ 统计
        count = len(merged)
        area_m2 = w * h * (ground_res / 100.0) ** 2
        density = count / area_m2 if area_m2 > 0 else 0

        # ⑦ 可视化
        annotated = self._draw(original, merged)
        return {
            "count": count,
            "density_per_m2": round(density, 2),
            "area_m2": round(area_m2, 2),
            "heatmap": self._heatmap(merged, w, h, grid_n),
            "confidence_dist": self._conf_dist(merged),
            "detection_data": merged,
            "annotated_image": annotated,
            "model_info": r.get("model_info"),
            "params_snapshot": params,
            "image_size": [w, h],
            "tile_count": len(tiles),
        }

    def _heatmap(self, dets, w, h, n):
        """将检测中心点落入 n×n 网格并计数。"""
        grid = [[0] * n for _ in range(n)]
        cw, ch = w / n, h / n
        for d in dets:
            cx = (d["bbox"][0] + d["bbox"][2]) / 2
            cy = (d["bbox"][1] + d["bbox"][3]) / 2
            grid[min(int(cy / ch), n - 1)][min(int(cx / cw), n - 1)] += 1
        return grid

    def _conf_dist(self, dets):
        """按置信度分档：high(≥0.7) / mid(≥0.4) / low。"""
        hi = mid = lo = 0
        for d in dets:
            c = d["confidence"]
            if c >= 0.7:
                hi += 1
            elif c >= 0.4:
                mid += 1
            else:
                lo += 1
        return {"high": hi, "mid": mid, "low": lo}

    def _draw(self, image, dets):
        """在原图上绘制检测框与编号，返回 base64 JPEG 字符串。"""
        img = image.copy()
        for d in dets:
            x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
            cv2.rectangle(img, (x1, y1), (x2, y2), (229, 57, 53), 2)
            cv2.putText(
                img,
                str(d["id"]),
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (229, 57, 53),
                1,
            )
        _, buf = cv2.imencode(".jpg", img)
        return base64.b64encode(buf).decode("utf-8")
