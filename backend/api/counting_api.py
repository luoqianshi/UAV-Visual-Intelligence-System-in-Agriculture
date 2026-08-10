"""计数 API：POST /api/counting（异步）、GET /api/counting/tasks/<id>(/result)、GET /api/counting/history。

- 单图高分辨率计数：multipart 文件上传或 image_path（或 image_dir 取首图）→ 异步任务 → CLAHE/分块/
  检测/NMS/统计 → 落盘到 result_store。
- on_progress 将 counter 的阶段回调映射到 0-1 进度并写入 task_manager。
- 引擎调用全部 try/except 兜底，ultralytics/torch 缺失时返回 success:False 而非 500。
"""
import os
import tempfile
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from core.engine import get_counter, get_task_manager
from core.result_store import (
    list_counting_history,
    load_counting_result,
    save_counting_result,
)

counting_bp = Blueprint("counting", __name__)

# 支持的图像扩展名
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

# 计数参数：键 → 类型转换
_COUNTING_PARAM_TYPES = {
    "tile_size": int,
    "overlap_ratio": float,
    "nms_iou": float,
    "global_conf": float,
    "batch_size": int,
    "ground_resolution": float,
    "grid_n": int,
    "conf": float,
    "iou": float,
    "max_det": int,
    "imgsz": int,
}


def _build_params(body):
    """从请求体解析计数参数，忽略缺失或无法转换的键。"""
    params = {}
    for key, cast in _COUNTING_PARAM_TYPES.items():
        if key not in body:
            continue
        val = body[key]
        if val in (None, ""):
            continue
        try:
            params[key] = cast(val)
        except (TypeError, ValueError):
            continue
    return params


def _pick_first_image(image_dir):
    """从目录中选取第一张支持的图像，返回完整路径；无则 None。"""
    try:
        for fname in sorted(os.listdir(image_dir)):
            if os.path.splitext(fname)[1].lower() in _IMAGE_EXTS:
                return os.path.join(image_dir, fname)
    except OSError:
        return None
    return None


@counting_bp.route("/api/counting", methods=["POST"])
def counting():
    counter = get_counter()
    task_manager = get_task_manager()
    if counter is None or task_manager is None:
        return jsonify({
            "success": False, "data": None, "message": "counter 未初始化",
        })

    cleanup_tmp = None
    # ① 优先处理 multipart 文件上传
    if "image" in request.files:
        file = request.files["image"]
        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            file.save(tmp.name)
            tmp.close()
            image_path = tmp.name
            cleanup_tmp = tmp.name
            model_name = request.form.get("model_name")
            params = _build_params(request.form)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
    else:
        # ② JSON 模式：image_path / image_dir
        body = request.get_json(silent=True) or {}
        image_path = body.get("image_path")
        image_dir = body.get("image_dir")
        model_name = body.get("model_name")
        params = _build_params(body)

        # image_dir 兜底：取首图作为单图计数输入
        if not image_path and image_dir:
            image_path = _pick_first_image(image_dir)

    if not image_path or not os.path.isfile(image_path):
        if cleanup_tmp:
            try:
                os.unlink(cleanup_tmp)
            except OSError:
                pass
        return jsonify({
            "success": False, "data": None,
            "message": "请提供有效的图片文件或 image_path / image_dir",
        })

    def _run(task_id, image_path, model_name, params, cleanup_tmp=None):
        """计数任务体：执行 counter.count → 落盘 → 返回轻量摘要。"""
        try:
            def on_progress(stage, current, total):
                if stage == "enhancing":
                    pct = 0.0
                elif stage == "detecting":
                    ratio = current / total if total else 1.0
                    pct = 0.05 + 0.9 * ratio
                else:
                    pct = 0.0
                task_manager.update(task_id, progress=pct, status="processing")

            result = counter.count(
                image_path, model_name=model_name, params=params,
                on_progress=on_progress,
            )
            result_id = (
                f"count_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                f"_{uuid.uuid4().hex[:6]}"
            )
            result["result_id"] = result_id
            save_counting_result(result)
            return {
                "result_id": result_id,
                "count": result.get("count"),
                "density_per_m2": result.get("density_per_m2"),
                "summary": {
                    "count": result.get("count"),
                    "density_per_m2": result.get("density_per_m2"),
                    "area_m2": result.get("area_m2"),
                    "tile_count": result.get("tile_count"),
                    "confidence_dist": result.get("confidence_dist"),
                    "image_size": result.get("image_size"),
                    "model_info": result.get("model_info"),
                },
            }
        finally:
            if cleanup_tmp:
                try:
                    os.unlink(cleanup_tmp)
                except OSError:
                    pass

    try:
        task_id = task_manager.submit(
            "counting", _run, image_path, model_name, params, cleanup_tmp
        )
    except Exception as exc:
        if cleanup_tmp:
            try:
                os.unlink(cleanup_tmp)
            except OSError:
                pass
        return jsonify({
            "success": False, "data": None,
            "message": f"任务提交失败: {exc}",
        })
    return jsonify({
        "success": True, "data": {"task_id": task_id}, "message": "ok",
    })


@counting_bp.route("/api/counting/tasks/<task_id>", methods=["GET"])
def counting_task_status(task_id):
    """返回任务全量状态字典。"""
    task_manager = get_task_manager()
    if task_manager is None:
        return jsonify({
            "success": False, "data": None, "message": "task_manager 未初始化",
        })
    task = task_manager.get(task_id)
    if task.get("error"):
        return jsonify({
            "success": False, "data": None, "message": task["error"],
        }), 404
    return jsonify({"success": True, "data": task, "message": "ok"})


@counting_bp.route("/api/counting/tasks/<task_id>/result", methods=["GET"])
def counting_task_result(task_id):
    """任务完成则从 result_store 加载完整结果，否则返回当前状态。"""
    task_manager = get_task_manager()
    if task_manager is None:
        return jsonify({
            "success": False, "data": None, "message": "task_manager 未初始化",
        })
    task = task_manager.get(task_id)
    if task.get("error"):
        return jsonify({
            "success": False, "data": None, "message": task["error"],
        }), 404
    if task.get("status") != "completed":
        return jsonify({
            "success": False, "data": None,
            "message": f"任务尚未完成，当前状态: {task.get('status')}",
        })
    result = task.get("result") or {}
    result_id = result.get("result_id") if isinstance(result, dict) else None
    if result_id:
        try:
            full = load_counting_result(result_id)
            return jsonify({"success": True, "data": full, "message": "ok"})
        except FileNotFoundError:
            # 落盘文件缺失，回退到任务 result 字段
            return jsonify({"success": True, "data": result, "message": "ok"})
    return jsonify({"success": True, "data": result, "message": "ok"})


@counting_bp.route("/api/counting/history", methods=["GET"])
def counting_history():
    """列出所有历史计数结果（按 created_at 倒序）。"""
    return jsonify({
        "success": True, "data": list_counting_history(), "message": "ok",
    })
