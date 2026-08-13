"""数据集管理 API（第一阶段：导入注册 + 统计报告 + 浏览删除）。

对齐 batches_api 风格：统一响应信封 {"success", "data", "message"}。
ValueError → 400，KeyError → 404，创建成功 → 201。
"""
from flask import Blueprint, Response, jsonify, request

from core.engine import get_dataset_analyzer, get_dataset_registry

datasets_bp = Blueprint("datasets", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


@datasets_bp.route("/api/datasets", methods=["GET"])
def list_datasets():
    """GET /api/datasets → 数据集列表，?format= 过滤，返回格式分布。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    fmt = request.args.get("format") or None
    datasets = reg.list_datasets(fmt=fmt)
    return jsonify({
        "success": True,
        "data": {"datasets": datasets, "total": len(datasets),
                 "format_dist": reg.format_dist()},
        "message": "获取数据集列表成功",
    })


@datasets_bp.route("/api/datasets/scan", methods=["POST"])
def scan_dataset():
    """POST /api/datasets/scan → 路径预检：格式识别 + 轻量统计。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("path", "")
    if not path:
        return _error("缺少 path 参数", 400)
    try:
        result = reg.scan_path(path)
    except Exception as exc:
        return _error(f"扫描失败: {exc}", 500)
    status = 200 if result["valid"] else 400
    return jsonify({
        "success": result["valid"],
        "data": result,
        "message": result.get("message", ""),
    }), status


@datasets_bp.route("/api/datasets/import", methods=["POST"])
def import_dataset():
    """POST /api/datasets/import → 导入注册。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("path", "")
    if not path:
        return _error("缺少 path 参数", 400)
    try:
        cfg = reg.import_dataset(path, name=body.get("name"),
                                 description=body.get("description"))
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error(f"导入失败: {exc}", 500)
    return jsonify({
        "success": True, "data": cfg, "message": "数据集导入成功",
    }), 201


@datasets_bp.route("/api/datasets/<dataset_id>", methods=["GET"])
def get_dataset(dataset_id):
    """GET /api/datasets/<dataset_id> → 数据集详情。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    try:
        cfg = reg.get_dataset(dataset_id)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    return jsonify({
        "success": True, "data": cfg, "message": "获取数据集详情成功",
    })


@datasets_bp.route("/api/datasets/<dataset_id>", methods=["DELETE"])
def delete_dataset(dataset_id):
    """DELETE /api/datasets/<dataset_id> → 删除（?delete_files=true 物理删除）。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    delete_files = request.args.get("delete_files", "false").lower() == "true"
    try:
        reg.delete_dataset(dataset_id, delete_files=delete_files)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    msg = "数据集目录已物理删除" if delete_files else "数据集已删除（原始文件未删除）"
    return jsonify({"success": True, "data": None, "message": msg})


@datasets_bp.route("/api/datasets/<dataset_id>/report", methods=["GET"])
def dataset_report(dataset_id):
    """GET /api/datasets/<dataset_id>/report → 统计报告（?force=true 强制重算）。"""
    reg = get_dataset_registry()
    az = get_dataset_analyzer()
    if reg is None or az is None:
        return _error("数据集引擎未初始化", 500)
    force = request.args.get("force", "false").lower() == "true"
    try:
        cfg = reg.get_dataset(dataset_id)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    try:
        report = az.compute_report(cfg, force=force)
    except Exception as exc:
        return _error(f"生成报告失败: {exc}", 500)
    return jsonify({"success": True, "data": report, "message": "ok"})


@datasets_bp.route("/api/datasets/<dataset_id>/images", methods=["GET"])
def list_dataset_images(dataset_id):
    """GET /api/datasets/<dataset_id>/images → 样本分页浏览。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    split = request.args.get("split", "train")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    try:
        result = reg.list_images(dataset_id, split=split, page=page, page_size=page_size)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    except Exception as exc:
        return _error(f"读取样本列表失败: {exc}", 500)
    return jsonify({"success": True, "data": result, "message": "获取样本列表成功"})


@datasets_bp.route("/api/datasets/<dataset_id>/images/<path:filename>/preview", methods=["GET"])
def dataset_image_preview(dataset_id, filename):
    """GET /api/datasets/<dataset_id>/images/<filename>/preview → 样本预览。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    split = request.args.get("split", "train")
    size = request.args.get("size", "thumbnail")
    if size not in ("thumbnail", "medium", "original"):
        size = "thumbnail"
    try:
        img_bytes = reg.get_image_preview(dataset_id, filename, split=split, size=size)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    except FileNotFoundError:
        return _error(f"图片不存在: {filename}", 404)
    except Exception as exc:
        return _error(f"读取图片失败: {exc}", 500)
    resp = Response(img_bytes, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@datasets_bp.route("/api/datasets/pick-folder", methods=["POST"])
def pick_folder():
    """POST /api/datasets/pick-folder → 系统原生文件夹选择对话框。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return _error("当前环境未安装 tkinter，请手动输入路径", 500)
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="选择数据集目录")
        root.destroy()
    except Exception as exc:
        return _error(f"打开文件夹对话框失败: {exc}", 500)
    if not folder:
        return jsonify({"success": False, "data": {"cancelled": True},
                        "message": "用户取消选择"}), 200
    return jsonify({"success": True, "data": {"path": folder.replace("\\", "/")},
                    "message": "文件夹选择成功"})
