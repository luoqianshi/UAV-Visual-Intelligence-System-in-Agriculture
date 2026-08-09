"""原始架次（飞行批次）只读 Mock API。

提供架次列表、详情、图片清单与图片预览占位图。
所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
import io
import json

from flask import Blueprint, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import NotFound

from config import MOCK_DIR, MOCK_IMAGES_DIR

batches_bp = Blueprint("batches", __name__)


def _load_batches():
    """读取 mock/batches.json。"""
    with open(MOCK_DIR / "batches.json", encoding="utf-8") as f:
        return json.load(f)


def _placeholder_image(label, w=400, h=300):
    """生成带文字标签的占位 JPEG 图片响应；cv2 缺失时回退极简 JPEG。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return Response(b"\xff\xd8\xff\xe0\x00\x10JFIF", mimetype="image/jpeg")
    img = np.full((h, w, 3), 245, dtype=np.uint8)
    cv2.putText(
        img,
        label,
        (20, h // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (47, 125, 50),
        2,
        cv2.LINE_AA,
    )
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:  # 兜底：极简 1x1 JPEG
        return Response(b"\xff\xd8\xff\xe0\x00\x10JFIF", mimetype="image/jpeg")
    return Response(buf.tobytes(), mimetype="image/jpeg")


@batches_bp.route("/api/batches", methods=["GET"])
def list_batches():
    """GET /api/batches → 架次列表，支持 ?crop_type= 与 ?status= 过滤。"""
    batches = _load_batches()
    crop_type = request.args.get("crop_type")
    status = request.args.get("status")
    if crop_type:
        batches = [b for b in batches if b.get("crop_type") == crop_type]
    if status:
        batches = [b for b in batches if b.get("status") == status]
    return jsonify({
        "success": True,
        "data": {"batches": batches, "total": len(batches)},
        "message": "获取架次列表成功",
    })


@batches_bp.route("/api/batches", methods=["POST"])
def create_batch():
    """POST /api/batches → 登记新架次（V1 演示模式，不持久化）。"""
    # 接收 JSON body 但不落盘
    return jsonify({
        "success": True,
        "data": None,
        "message": "架次登记成功（V1 演示模式，未持久化）",
    }), 201


@batches_bp.route("/api/batches/<batch_id>", methods=["GET"])
def get_batch(batch_id):
    """GET /api/batches/<batch_id> → 单个架次详情。"""
    batches = _load_batches()
    for b in batches:
        if b.get("id") == batch_id:
            return jsonify({
                "success": True,
                "data": b,
                "message": "获取架次详情成功",
            })
    return jsonify({
        "success": False,
        "data": None,
        "message": f"架次不存在: {batch_id}",
    }), 404


@batches_bp.route("/api/batches/<batch_id>/images", methods=["GET"])
def list_batch_images(batch_id):
    """GET /api/batches/<batch_id>/images → 该架次下的图片清单（12 张示例）。"""
    # 确认架次存在
    batches = _load_batches()
    found = any(b.get("id") == batch_id for b in batches)
    if not found:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"架次不存在: {batch_id}",
        }), 404

    images = []
    for i in range(1, 13):
        fname = f"DJI_{i:04d}.jpg"
        images.append({
            "file": fname,
            "url": f"/api/batches/{batch_id}/images/{fname}/preview",
            "width": 5472,
            "height": 3648,
            "size_kb": 8234,
            "captured_at": "2026-08-05T10:30:00",
        })
    return jsonify({
        "success": True,
        "data": {"images": images, "total": len(images)},
        "message": "获取架次图片列表成功",
    })


@batches_bp.route(
    "/api/batches/<batch_id>/images/<file>/preview", methods=["GET"]
)
def batch_image_preview(batch_id, file):
    """GET /api/batches/<batch_id>/images/<file>/preview → 图片预览占位图。"""
    # 优先读取本机已有样图
    try:
        return send_from_directory(str(MOCK_IMAGES_DIR), file)
    except (FileNotFoundError, NotFound):
        pass
    label = file or "preview"
    return _placeholder_image(label)
