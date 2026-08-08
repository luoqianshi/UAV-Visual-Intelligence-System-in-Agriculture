"""检测引擎：原子化单图 YOLO 推理。无 CLAHE/分块/NMS合并。"""
import base64

import cv2
import numpy as np


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
        conf = params.get("conf", cfg.get("conf", 0.5))
        iou = params.get("iou", cfg.get("iou", 0.3))
        max_det = params.get("max_det", cfg.get("max_det", 300))
        device = params.get("device", cfg.get("device", "auto"))

        engine = self.registry.get_engine(model_name)
        results = engine.predict(
            image,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            max_det=max_det,
            device=device,
            verbose=False,
        )

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
