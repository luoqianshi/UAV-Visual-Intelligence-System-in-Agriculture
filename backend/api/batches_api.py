"""原始架次 API：架次 CRUD、图片列表分页、动态缩略图预览。

所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
from flask import Blueprint, Response, jsonify, request

from core.engine import get_batch_registry

batches_bp = Blueprint("batches", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


@batches_bp.route("/api/batches", methods=["GET"])
def list_batches():
    """GET /api/batches → 架次列表，支持过滤。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    crop_type = request.args.get("crop_type") or None
    flight_date = request.args.get("flight_date") or None
    plot_name = request.args.get("plot_name") or None
    try:
        batches = br.list_batches(crop_type=crop_type, flight_date=flight_date, plot_name=plot_name)
        summary = br.get_summary()
    except Exception as exc:
        return _error(f"读取架次列表失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": {"batches": batches, "total": len(batches), "summary": summary},
        "message": "获取架次列表成功",
    })


@batches_bp.route("/api/batches", methods=["POST"])
def create_batch():
    """POST /api/batches → 登记新架次。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    try:
        cfg = br.create_batch(body)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error(f"创建架次失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": {
            "batch_id": cfg["batch_id"],
            "image_count": cfg["image_count"],
            "total_size_mb": round(cfg["total_size_bytes"] / (1024 * 1024), 1),
        },
        "message": "架次登记成功",
    }), 201


@batches_bp.route("/api/batches/<batch_id>", methods=["GET"])
def get_batch(batch_id):
    """GET /api/batches/<batch_id> → 单个架次详情。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        batch = br.get_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    return jsonify({
        "success": True,
        "data": batch,
        "message": "获取架次详情成功",
    })


@batches_bp.route("/api/batches/<batch_id>", methods=["PUT"])
def update_batch(batch_id):
    """PUT /api/batches/<batch_id> → 更新架次元数据。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    try:
        cfg = br.update_batch(batch_id, body)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    except ValueError as exc:
        return _error(str(exc), 400)
    return jsonify({
        "success": True,
        "data": cfg,
        "message": "架次更新成功",
    })


@batches_bp.route("/api/batches/<batch_id>", methods=["DELETE"])
def delete_batch(batch_id):
    """DELETE /api/batches/<batch_id> → 删除架次登记（不删除原始文件）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        br.delete_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    return jsonify({
        "success": True,
        "data": None,
        "message": "架次已删除（原始文件未删除）",
    })


@batches_bp.route("/api/batches/<batch_id>/images", methods=["GET"])
def list_batch_images(batch_id):
    """GET /api/batches/<batch_id>/images → 该架次下的图片列表（分页）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    try:
        br.get_batch(batch_id)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    sort_by = request.args.get("sort_by", "filename")
    order = request.args.get("order", "asc")
    try:
        result = br.list_images(batch_id, page=page, page_size=page_size, sort_by=sort_by, order=order)
    except Exception as exc:
        return _error(f"读取图片列表失败: {exc}", 500)
    return jsonify({
        "success": True,
        "data": result,
        "message": "获取图片列表成功",
    })


@batches_bp.route("/api/batches/<batch_id>/images/<path:filename>/preview", methods=["GET"])
def batch_image_preview(batch_id, filename):
    """GET /api/batches/<batch_id>/images/<file>/preview → 图片预览（缩略图/中图/原图）。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    size = request.args.get("size", "thumbnail")
    if size not in ("thumbnail", "medium", "original"):
        size = "thumbnail"
    try:
        img_bytes = br.get_image_preview(batch_id, filename, size=size)
    except KeyError:
        return _error(f"架次不存在: {batch_id}", 404)
    except FileNotFoundError:
        return _error(f"图片不存在: {filename}", 404)
    except Exception as exc:
        return _error(f"读取图片失败: {exc}", 500)
    resp = Response(img_bytes, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@batches_bp.route("/api/batches/scan", methods=["POST"])
def scan_path():
    """POST /api/batches/scan → 路径预检扫描。"""
    br = get_batch_registry()
    if br is None:
        return _error("batch_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("image_folder_path", "")
    if not path:
        return _error("缺少 image_folder_path 参数", 400)
    try:
        result = br.scan_path(path)
    except Exception as exc:
        return _error(f"扫描失败: {exc}", 500)
    status = 200 if result["valid"] else 400
    return jsonify({
        "success": result["valid"],
        "data": result,
        "message": result.get("message", ""),
    }), status


@batches_bp.route("/api/batches/pick-folder", methods=["POST"])
def pick_folder():
    """POST /api/batches/pick-folder → 弹出系统原生文件夹选择对话框，返回所选绝对路径。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return _error("当前环境未安装 tkinter，无法弹出系统对话框，请手动输入路径", 500)
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="选择 UAV 架次图片文件夹")
        root.destroy()
    except Exception as exc:
        return _error(f"打开文件夹对话框失败: {exc}", 500)
    if not folder:
        return jsonify({
            "success": False,
            "data": {"cancelled": True},
            "message": "用户取消选择",
        }), 200
    return jsonify({
        "success": True,
        "data": {"path": folder.replace("\\", "/")},
        "message": "文件夹选择成功",
    })
