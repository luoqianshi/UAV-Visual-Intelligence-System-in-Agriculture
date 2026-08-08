"""数据处理（CLAHE 增强 / 滑窗裁切）只读 Mock API。

提供任务列表、详情与结果预览占位图。
所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
import json

import cv2
import numpy as np
from flask import Blueprint, Response, jsonify, request

from config import MOCK_DIR

processing_bp = Blueprint("processing", __name__)


def _load_tasks():
    """读取 mock/tasks.json。"""
    with open(MOCK_DIR / "tasks.json", encoding="utf-8") as f:
        return json.load(f)


def _placeholder_image(label, w=400, h=300):
    """生成带文字标签的占位 JPEG 图片响应。"""
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


@processing_bp.route("/api/processing/tasks", methods=["GET"])
def list_tasks():
    """GET /api/processing/tasks → 任务列表，支持 ?type= 与 ?status= 过滤。"""
    tasks = _load_tasks()
    task_type = request.args.get("type")
    status = request.args.get("status")
    if task_type:
        tasks = [t for t in tasks if t.get("type") == task_type]
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return jsonify({
        "success": True,
        "data": {"tasks": tasks, "total": len(tasks)},
        "message": "获取任务列表成功",
    })


@processing_bp.route("/api/processing/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """GET /api/processing/tasks/<task_id> → 单个任务详情。"""
    tasks = _load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            return jsonify({
                "success": True,
                "data": t,
                "message": "获取任务详情成功",
            })
    return jsonify({
        "success": False,
        "data": None,
        "message": f"任务不存在: {task_id}",
    }), 404


@processing_bp.route("/api/processing/tasks/<task_id>/preview", methods=["GET"])
def task_preview(task_id):
    """GET /api/processing/tasks/<task_id>/preview → 任务结果预览占位图。

    查询参数 ?type=original|result 可用于区分原图/结果对比。
    """
    tasks = _load_tasks()
    task = next((t for t in tasks if t.get("id") == task_id), None)
    if task is None:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"任务不存在: {task_id}",
        }), 404

    preview_type = request.args.get("type", "result")
    name = task.get("name", task_id)
    label = f"{name} [{preview_type}]"
    return _placeholder_image(label)
