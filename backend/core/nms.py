"""全局 NMS：IoU 贪心抑制，同类别才抑制。"""
def _iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2-x1) * max(0, y2-y1)
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / union if union > 0 else 0.0

def global_nms(detections: list, iou_threshold: float = 0.5) -> list:
    if not detections:
        return []
    sorted_dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    kept = []
    for det in sorted_dets:
        if not any(det["class"] == k["class"] and _iou(det["bbox"], k["bbox"]) > iou_threshold for k in kept):
            kept.append(det)
    return kept
