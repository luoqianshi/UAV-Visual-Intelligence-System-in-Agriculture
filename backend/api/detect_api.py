"""检测 API：POST /api/detect（同步单图 / 异步批量）、GET /api/detect/tasks/<id>(/result)。

- 单图：multipart 上传 image 文件 → 同步调用 detector.detect → 展开 bbox 为
  {x, y, width, height}（spec §7.3）。
- 批量：传 image_dir → 异步任务，逐图检测，进度通过 task_manager.update 上报。
- 引擎调用全部 try/except 兜底，ultralytics/torch 缺失时返回 success:False 而非 500。
"""
import os
import tempfile

from flask import Blueprint, jsonify, request

from core.engine import get_detector, get_task_manager

detect_bp = Blueprint("detect", __name__)

# 支持的图像扩展名
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

# 检测推理参数：键 → 类型转换
_DETECT_PARAM_TYPES = {
    "imgsz": int,
    "conf": float,
    "iou": float,
    "max_det": int,
    "device": str,  # 非数值，原样保留
}


def _parse_params(source, types=None):
    """从 form/dict 解析推理参数，忽略缺失或无法转换的键。"""
    types = types or _DETECT_PARAM_TYPES
    params = {}
    for key, cast in types.items():
        if key not in source:
            continue
        val = source[key]
        if val in (None, ""):
            continue
        try:
            params[key] = cast(val)
        except (TypeError, ValueError):
            continue
    return params


def _expand_bbox(det):
    """将 detection_data 中的 bbox [x1,y1,x2,y2] 展开为 {x,y,width,height}。"""
    x1, y1, x2, y2 = det["bbox"]
    return {
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "confidence": det["confidence"],
        "class": det["class"],
        "class_name": det["class_name"],
    }


@detect_bp.route("/api/detect", methods=["POST"])
def detect():
    detector = get_detector()
    if detector is None:
        return jsonify({
            "success": False, "data": None, "message": "detector 未初始化",
        })

    # ① 单图同步：multipart 上传 image 文件
    if "image" in request.files:
        file = request.files["image"]
        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            file.save(tmp.name)
            tmp.close()
            params = _parse_params(request.form)
            model_name = request.form.get("model_name")
            try:
                out = detector.detect(
                    tmp.name, model_name=model_name, params=params, draw=True
                )
            except Exception as exc:
                return jsonify({
                    "success": False, "data": None,
                    "message": f"检测失败: {exc}",
                })
            detection_data = [_expand_bbox(d) for d in out.get("detection_data", [])]
            return jsonify({
                "success": True,
                "data": {
                    "detection_count": len(detection_data),
                    "result_image": out.get("annotated_image"),
                    "detection_data": detection_data,
                    "model_info": out.get("model_info"),
                },
                "message": "ok",
            })
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # ② 批量异步：image_dir（form 或 json）
    body = request.form if request.form else (request.get_json(silent=True) or {})
    image_dir = body.get("image_dir")
    if image_dir:
        task_manager = get_task_manager()
        if task_manager is None:
            return jsonify({
                "success": False, "data": None, "message": "task_manager 未初始化",
            })
        params = _parse_params(body)
        model_name = body.get("model_name")

        def _run(task_id, image_dir, model_name, params):
            """批量检测任务体：逐图检测，上报进度，返回 {results, total}。"""
            results = []
            try:
                files = sorted(
                    f for f in os.listdir(image_dir)
                    if os.path.splitext(f)[1].lower() in _IMAGE_EXTS
                )
            except OSError as exc:
                raise RuntimeError(f"无法读取目录 {image_dir}: {exc}")
            total = len(files)
            for i, fname in enumerate(files, 1):
                path = os.path.join(image_dir, fname)
                out = detector.detect(
                    path, model_name=model_name, params=params, draw=True
                )
                results.append({
                    "filename": fname,
                    "detection_count": len(out.get("detection_data", [])),
                    "detection_data": out.get("detection_data", []),
                    "model_info": out.get("model_info"),
                })
                if total:
                    task_manager.update(task_id, progress=i / total)
            return {"results": results, "total": total}

        try:
            task_id = task_manager.submit(
                "detect_batch", _run, image_dir, model_name, params
            )
        except Exception as exc:
            return jsonify({
                "success": False, "data": None,
                "message": f"任务提交失败: {exc}",
            })
        return jsonify({
            "success": True, "data": {"task_id": task_id}, "message": "ok",
        })

    # ③ 无输入
    return jsonify({
        "success": False, "data": None,
        "message": "请提供 image 文件或 image_dir",
    })


@detect_bp.route("/api/detect/tasks/<task_id>", methods=["GET"])
def detect_task_status(task_id):
    """返回任务全量状态字典。"""
    task_manager = get_task_manager()
    if task_manager is None:
        return jsonify({
            "success": False, "data": None, "message": "task_manager 未初始化",
        })
    task = task_manager.get(task_id)
    if "error" in task:  # 不存在
        return jsonify({
            "success": False, "data": None, "message": task["error"],
        }), 404
    return jsonify({"success": True, "data": task, "message": "ok"})


@detect_bp.route("/api/detect/tasks/<task_id>/result", methods=["GET"])
def detect_task_result(task_id):
    """任务完成返回 result，否则返回当前状态。"""
    task_manager = get_task_manager()
    if task_manager is None:
        return jsonify({
            "success": False, "data": None, "message": "task_manager 未初始化",
        })
    task = task_manager.get(task_id)
    if "error" in task:
        return jsonify({
            "success": False, "data": None, "message": task["error"],
        }), 404
    if task.get("status") == "completed":
        return jsonify({
            "success": True, "data": task.get("result"), "message": "ok",
        })
    return jsonify({
        "success": False, "data": None,
        "message": f"任务尚未完成，当前状态: {task.get('status')}",
    })
