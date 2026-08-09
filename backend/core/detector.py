"""检测引擎：原子化单图 YOLO 推理。无 CLAHE/分块/NMS合并。"""
import base64
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DetectionEngine:
    """原子化单图检测引擎。

    - 由外部注入 registry，按模型名取配置与引擎实例；
    - 推理参数优先取 params，其次取模型 config，最后用内置默认值；
    - 解析结果为结构化 detection_data，可选绘制 base64 JPEG 标注图。
    """

    def __init__(self, registry):
        self.registry = registry

    def detect(self, image, model_name=None, params=None, draw=True) -> dict:
        params = params or {}
        cfg = self.registry.get_config(model_name)
        imgsz = params.get("imgsz", cfg.get("imgsz", 640))
        conf = params.get("conf", cfg.get("conf", 0.25))
        iou = params.get("iou", cfg.get("iou", 0.7))
        max_det = params.get("max_det", cfg.get("max_det", 300))
        device = self._normalize_device(
            params.get("device", cfg.get("device"))
        )  # 归一化：'auto'/''/None → None；'cuda:0' → 0

        engine = self.registry.get_engine(model_name)
        try:
            results = engine.predict(
                image,
                imgsz=imgsz,
                conf=conf,
                iou=iou,
                max_det=max_det,
                device=device,
                verbose=False,
            )
        except Exception as exc:
            # GPU 间歇性不可用时降级到 CPU 重试（应对 device_count=0）
            if device not in (None, "cpu") and self._is_cuda_error(exc):
                logger.warning("GPU 推理失败，降级到 CPU 重试：%s", exc)
                results = engine.predict(
                    image,
                    imgsz=imgsz,
                    conf=conf,
                    iou=iou,
                    max_det=max_det,
                    device="cpu",
                    verbose=False,
                )
            else:
                raise

        classes = cfg.get("classes", [])
        detection_data = self._parse(results[0], classes)
        annotated = self._draw(image, detection_data) if draw and detection_data else None
        return {
            "detection_data": detection_data,
            "annotated_image": annotated,
            "model_info": {
                "name": cfg["name"],
                "display_name": cfg.get("display_name", cfg["name"]),
                "imgsz": imgsz,
            },
        }

    @staticmethod
    def _normalize_device(device):
        """将 device 归一化为 ultralytics 可接受的值。

        - None / '' / 'auto' → None（ultralytics 自动选择：GPU 优先，无 GPU 则 CPU）；
          注：'auto' 字符串在 ultralytics 8.4.60 中无效（select_device 抛 ValueError），
          必须转为 None。
        - 'cuda:0' / 'cuda:1' 等 → 0 / 1（int，ultralytics 期望的格式）；
          'cuda:N' 同样无效，需转为 int N。
        - 'cpu' → 'cpu'（原样保留）。
        - '0' / 0 → 0（字符串数字转 int）。
        """
        if device is None or device == "" or device == "auto":
            return None
        if isinstance(device, str) and device.startswith("cuda:"):
            try:
                return int(device.split(":")[1])
            except (IndexError, ValueError):
                return 0
        if isinstance(device, str) and device.isdigit():
            return int(device)
        return device

    @staticmethod
    def _is_cuda_error(exc):
        """判断异常是否与 CUDA 不可用相关（用于决定是否降级到 CPU）。"""
        msg = str(exc).lower()
        return any(k in msg for k in ("cuda", "device", "gpu"))

    def _parse(self, result, classes):
        """将 YOLO result 解析为检测字典列表；无框时返回空列表。"""
        if result.boxes is None or len(result.boxes) == 0:
            return []
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        clss = result.boxes.cls.cpu().numpy().astype(int)
        return [
            {
                "bbox": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
                "confidence": float(c),
                "class": int(cl),
                "class_name": classes[cl] if cl < len(classes) else str(cl),
            }
            for b, c, cl in zip(boxes, confs, clss)
        ]

    def _draw(self, image, detections):
        """在图像上绘制检测框与置信度，返回 base64 JPEG 字符串。"""
        img = cv2.imread(image) if isinstance(image, str) else image.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            cv2.rectangle(img, (x1, y1), (x2, y2), (229, 57, 53), 2)
            cv2.putText(
                img,
                f'{det["confidence"]:.2f}',
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (229, 57, 53),
                1,
            )
        _, buf = cv2.imencode(".jpg", img)
        return base64.b64encode(buf).decode("utf-8")
