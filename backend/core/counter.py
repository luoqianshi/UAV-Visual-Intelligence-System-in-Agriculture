"""计数引擎：高分辨率原图 CLAHE→分块→批量检测→坐标映射→全局NMS→全局二次过滤→计数统计。

子块不落盘，内存直传；每块检测结果记入日志与 tile_results，全局计数在
子块结果基础上经全局合并（NMS）与二次过滤得出。
"""
import base64
import json
import logging
from pathlib import Path

import cv2
import numpy as np

from core import clahe, tiling, nms

logger = logging.getLogger(__name__)


class CountingEngine:
    """计数引擎：编排 CLAHE / 分块 / 检测 / 映射 / NMS / 统计 / 可视化。

    - 由外部注入 detector 与 task_manager；
    - count() 对整张原图执行全流程并返回结构化结果。
    """

    def __init__(self, detector, task_manager):
        self.detector = detector
        self.task_manager = task_manager

    def count(self, image, model_name=None, params=None, on_progress=None, result_dir=None) -> dict:
        params = params or {}
        tile_size = params.get("tile_size", 640)
        overlap_ratio = params.get("overlap_ratio", 0.05)
        nms_iou = params.get("nms_iou", 0.5)
        global_conf = params.get("global_conf", 0.0)  # 合并后全局二次过滤，<=0 关闭（默认关闭，与检测模式阈值对齐）
        batch_size = max(int(params.get("batch_size", 8)), 1)
        ground_res = params.get("ground_resolution", 0.85)  # cm/px
        grid_n = params.get("grid_n", 8)
        save_tiles = params.get("save_tiles", False) and result_dir is not None
        enhance = params.get("enhance", False)  # CLAHE 预处理，默认关闭（训练未用 CLAHE，开启会致分布偏移）

        # ① 加载原图（保持 BGR，与 cv2.imread / ultralytics ndarray 期望一致，
        #    避免颜色通道反转导致检测失准）
        if isinstance(image, str):
            original = cv2.imread(image)
        else:
            original = image
        h, w = original.shape[:2]

        # 单块短路：原图 ≤ tile_size 时仅 1 块、无重叠冗余，
        # 强制关闭 CLAHE / 全局 conf 过滤 / 全局 NMS，避免无意义计算
        # （640×640 输入配默认 tile_size=640 即命中此分支）
        is_single_tile = (w <= tile_size and h <= tile_size)
        if is_single_tile:
            if enhance:
                logger.info(
                    "原图 %dx%d ≤ tile_size=%d，单块模式：自动禁用 CLAHE/全局conf/全局NMS",
                    w, h, tile_size,
                )
            enhance = False
            global_conf = 0.0
            skip_global_nms = True
        else:
            skip_global_nms = False

        # ② CLAHE（可选，默认关闭）
        # 顺序对齐原始 crop.py：先对高分辨率原图整体做 CLAHE，再对增强后的图分块
        if on_progress:
            on_progress("enhancing", 0, 1)
        enhanced = clahe.enhance(original) if enhance else original

        # ③ 分块
        tiles = tiling.slide_window(enhanced, tile_size, overlap_ratio)

        # ④ 批量分块检测 + 坐标映射 + 子块结果日志
        all_dets = []
        tile_results = []
        max_det_reached_tiles = []
        tiles_meta_list = []
        tiles_dir = result_dir / "tiles" if save_tiles else None
        done = 0
        total = len(tiles)
        for start in range(0, total, batch_size):
            batch = tiles[start:start + batch_size]
            batch_dets, meta = self._detect_batch_with_fallback(batch, model_name, params)
            eff_max_det = meta.get("max_det")
            for (tile_img, ox, oy), dets in zip(batch, batch_dets):
                idx = start + len(tile_results)
                reached = eff_max_det is not None and len(dets) >= eff_max_det
                logger.info(
                    "子块检测完成：块 %d/%d 偏移=(%d,%d) 检出=%d%s",
                    idx + 1, total, ox, oy, len(dets),
                    "（已达 max_det 上限，密植截断风险）" if reached else "",
                )
                tile_results.append({
                    "tile_index": idx,
                    "offset_x": ox,
                    "offset_y": oy,
                    "det_count": len(dets),
                    "max_det_reached": reached,
                })
                if reached:
                    max_det_reached_tiles.append(idx)

                # —— 分块落盘（调试用）——
                if save_tiles:
                    try:
                        tile_idx_1based = idx + 1
                        tile_stem = f"tile_{tile_idx_1based:04d}_x{ox}_y{oy}"
                        tile_file = f"{tile_stem}.jpg"
                        annotated_file = f"{tile_stem}_annotated.jpg"

                        # 保存子块原图（已是 BGR，无需转换）
                        tile_bgr = tile_img
                        cv2.imwrite(str(tiles_dir / tile_file), tile_bgr)

                        # 保存子块检测框可视化（使用局部坐标，映射前）
                        tile_annotated = self._draw_tile(tile_bgr.copy(), dets)
                        cv2.imwrite(str(tiles_dir / annotated_file), tile_annotated)

                        # 记录元数据（局部坐标 + 映射后全局坐标）
                        dets_meta = []
                        for det in dets:
                            bbox_local = list(det["bbox"])
                            bbox_global = tiling.map_to_original(bbox_local, ox, oy)
                            dets_meta.append({
                                "bbox_local": [int(v) for v in bbox_local],
                                "bbox_global": [int(v) for v in bbox_global],
                                "confidence": float(det.get("confidence", 0)),
                                "class_id": int(det.get("class_id", 0)),
                            })
                        tiles_meta_list.append({
                            "index": tile_idx_1based,
                            "offset_x": ox,
                            "offset_y": oy,
                            "tile_file": tile_file,
                            "annotated_file": annotated_file,
                            "det_count": len(dets),
                            "max_det_reached": reached,
                            "detections": dets_meta,
                        })
                    except Exception as e:
                        logger.warning("子块 %d 落盘失败（不影响计数）：%s", idx + 1, e)

                # 坐标映射到全局
                for det in dets:
                    det["bbox"] = tiling.map_to_original(det["bbox"], ox, oy)
                    all_dets.append(det)
                done += 1
                if on_progress:
                    on_progress("detecting", done, total)

        # 写入分块元数据汇总
        if save_tiles and tiles_meta_list:
            try:
                tiles_meta = {
                    "tile_size": tile_size,
                    "overlap_ratio": overlap_ratio,
                    "total_tiles": total,
                    "tiles": tiles_meta_list,
                }
                (result_dir / "tiles_meta.json").write_text(
                    json.dumps(tiles_meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning("tiles_meta.json 写入失败：%s", e)

        # ⑤ 全局 conf 二次过滤 → 全局 NMS 去重 → 编号
        # 顺序：先按置信度过滤低分检测，再对存活框做 NMS 去重
        # （单块模式 skip_global_nms=True 时跳过 NMS）
        if global_conf > 0:
            before = len(all_dets)
            filtered = [d for d in all_dets if d["confidence"] >= global_conf]
            filtered_count = before - len(filtered)
        else:
            filtered = all_dets
            filtered_count = 0
        if skip_global_nms:
            merged = list(filtered)
        else:
            merged = nms.global_nms(filtered, nms_iou)
        for idx, det in enumerate(merged, 1):
            det["id"] = idx

        # ⑥ 统计
        count = len(merged)
        area_m2 = w * h * (ground_res / 100.0) ** 2
        density = count / area_m2 if area_m2 > 0 else 0

        # ⑦ 可视化
        annotated = self._draw(original, merged)
        cfg = self.detector.registry.get_config(model_name)
        return {
            "count": count,
            "density_per_m2": round(density, 2),
            "area_m2": round(area_m2, 2),
            "heatmap": self._heatmap(merged, w, h, grid_n),
            "confidence_dist": self._conf_dist(merged),
            "detection_data": merged,
            "annotated_image": annotated,
            "model_info": {
                "name": cfg["name"],
                "display_name": cfg.get("display_name", cfg["name"]),
                "imgsz": cfg.get("imgsz", 640),
            },
            "params_snapshot": params,
            "image_size": [w, h],
            "tile_count": len(tiles),
            "tile_results": tile_results,
            "max_det_reached_tiles": max_det_reached_tiles,
            "filtered_count": filtered_count,
        }

    def _detect_batch_with_fallback(self, batch, model_name, params):
        """批量推理一批子块；失败时回退为批内逐块串行检测。

        返回 (每块检测列表, meta)，meta 含 max_det（触顶判据）与 model_info。
        """
        try:
            r = self.detector.detect_batch(
                [tile for tile, _, _ in batch], model_name=model_name, params=params
            )
            return r["batch_detections"], r
        except Exception as exc:
            logger.warning("批量分块推理失败，回退逐块串行检测：%s", exc)
            batch_dets = []
            meta = {}
            for tile, _, _ in batch:
                r = self.detector.detect(tile, model_name=model_name, params=params, draw=False)
                batch_dets.append(r["detection_data"])
                meta = r
            return batch_dets, meta

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
        """在原图上绘制检测框与编号，返回 base64 JPEG 字符串。

        image 为 BGR 顺序（count() 中已保持 cv2.imread 的 BGR）；cv2 绘制与
        imencode 均以 BGR 为准，无需转换，颜色元组按 BGR 顺序书写。
        """
        img = image.copy()  # 已是 BGR
        for d in dets:
            x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
            cv2.rectangle(img, (x1, y1), (x2, y2), (53, 57, 229), 2)  # BGR: 红
            cv2.putText(
                img,
                str(d["id"]),
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (53, 57, 229),  # BGR: 红
                1,
            )
        _, buf = cv2.imencode(".jpg", img)
        return base64.b64encode(buf).decode("utf-8")

    def _draw_tile(self, img_bgr, dets):
        """在子块图像（BGR）上绘制局部坐标检测框，返回标注后的 BGR 图像。

        仅绘制检测框，不绘制编号（避免与全局编号混淆）。
        """
        for d in dets:
            x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
            cv2.rectangle(img_bgr, (x1, y1), (x2, y2), (53, 57, 229), 2)  # BGR: 红
        return img_bgr
