"""数据处理 API：CLAHE 增强 / 滑窗裁切 任务提交 + 查询 + 预览 + 加工数据列表。

所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
import io
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

import config
from config import IMAGE_EXTENSIONS, PROJECT_ROOT
from core.engine import (get_processing_engine, get_processing_registry,
                          get_processing_task_manager)

processing_bp = Blueprint("processing", __name__)


def _error(message, status_code=400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


def _get_output_dir(cfg):
    """获取任务输出目录，使用 config.OUTPUT_DIR（支持测试 monkeypatching）。"""
    return Path(config.OUTPUT_DIR) / cfg["task_id"]


def _resolve_path(path_str):
    """解析相对路径（相对 PROJECT_ROOT）。"""
    p = Path(path_str)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


# ── 任务提交 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/clahe", methods=["POST"])
def submit_clahe():
    """POST /api/processing/clahe → 提交 CLAHE 任务（异步）。"""
    engine = get_processing_engine()
    registry = get_processing_registry()
    tm = get_processing_task_manager()
    if engine is None or registry is None or tm is None:
        return _error("处理引擎未初始化（依赖 cv2/numpy）", 503)

    body = request.get_json(silent=True) or {}
    name = body.get("name") or "CLAHE 任务"
    input_paths = body.get("input_paths") or []
    params = body.get("params") or {}
    if not input_paths:
        return _error("必须指定 input_paths（至少一个架次或目录）")

    try:
        cfg = registry.create_task(
            name=name, task_type="clahe",
            input_paths=input_paths, params=params
        )
    except ValueError as e:
        return _error(str(e))

    response_data = dict(cfg)  # 提交前快照，避免异步 worker 改写 status
    _submit_async(engine, registry, tm, cfg, "clahe")
    return jsonify({"success": True, "data": response_data, "message": "任务已提交"})


@processing_bp.route("/api/processing/crop", methods=["POST"])
def submit_crop():
    """POST /api/processing/crop → 提交滑窗裁切任务（异步）。"""
    engine = get_processing_engine()
    registry = get_processing_registry()
    tm = get_processing_task_manager()
    if engine is None or registry is None or tm is None:
        return _error("处理引擎未初始化（依赖 cv2/numpy）", 503)

    body = request.get_json(silent=True) or {}
    name = body.get("name") or "裁切任务"
    input_paths = body.get("input_paths") or []
    params = body.get("params") or {}
    if not input_paths:
        return _error("必须指定 input_paths（至少一个架次或目录）")

    try:
        cfg = registry.create_task(
            name=name, task_type="crop",
            input_paths=input_paths, params=params
        )
    except ValueError as e:
        return _error(str(e))

    response_data = dict(cfg)  # 提交前快照，避免异步 worker 改写 status
    _submit_async(engine, registry, tm, cfg, "crop")
    return jsonify({"success": True, "data": response_data, "message": "任务已提交"})


def _submit_async(engine, registry, tm, cfg, task_type):
    """提交异步任务到 task_manager。"""
    task_id = cfg["task_id"]
    input_paths = cfg["input_paths"]
    params = cfg["params"]
    output_dir = _get_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _progress(processed, total):
        pct = int(processed / total * 100) if total else 0
        registry.update_task(
            task_id, progress=pct, processed_images=processed, status="processing"
        )

    def _run(tid):
        registry.update_task(task_id, status="processing",
                             started_at=datetime.now().isoformat(timespec="seconds"))
        try:
            if task_type == "clahe":
                result = engine.run_clahe(task_id, input_paths, params, output_dir, _progress)
            else:
                result = engine.run_crop(task_id, input_paths, params, output_dir, _progress)
            engine.write_index(
                output_dir, task_id, task_type, params, result, cfg["created_at"]
            )
            registry.update_task(
                task_id, status="completed", progress=100,
                processed_images=result["processed_images"],
                sub_dirs=result["sub_dirs"],
                total_tiles=result.get("total_tiles") if task_type == "crop" else None,
                completed_at=datetime.now().isoformat(timespec="seconds"),
            )
            return result
        except Exception as e:
            registry.update_task(task_id, status="failed", error=str(e),
                                 completed_at=datetime.now().isoformat(timespec="seconds"))
            raise

    tm.submit("processing", _run, task_id=task_id)


# ── 任务查询 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks", methods=["GET"])
def list_tasks():
    """GET /api/processing/tasks → 任务列表，支持 ?type= &status= 过滤。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    task_type = request.args.get("type")
    status = request.args.get("status")
    tasks = registry.list_tasks(task_type=task_type, status=status)
    return jsonify({
        "success": True,
        "data": {"tasks": tasks, "total": len(tasks)},
        "message": "获取任务列表成功",
    })


@processing_bp.route("/api/processing/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """GET /api/processing/tasks/<task_id> → 任务详情。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)
    return jsonify({"success": True, "data": cfg, "message": "获取任务详情成功"})


# ── 结果文件清单 ──────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks/<task_id>/files", methods=["GET"])
def list_task_files(task_id):
    """GET /api/processing/tasks/<task_id>/files?sub_dir=&page=&page_size="""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)

    sub_dir = request.args.get("sub_dir")
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(200, max(1, int(request.args.get("page_size", 50))))

    out_dir = _get_output_dir(cfg)
    target_dir = out_dir / sub_dir if sub_dir else out_dir
    if not target_dir.is_dir():
        return _error(f"目录不存在: {sub_dir or '/'}", 404)

    files = sorted([
        f for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ])
    total = len(files)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    paged = files[start:start + page_size]

    from PIL import Image
    result_files = []
    for f in paged:
        try:
            with Image.open(f) as im:
                width, height = im.size
            stat = f.stat()
            sub_param = f"&sub_dir={sub_dir}" if sub_dir else ""
            result_files.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "width": width,
                "height": height,
                "format": f.suffix.lstrip(".").upper(),
                "thumbnail_url": f"/api/processing/tasks/{task_id}/preview?filename={f.name}&size=thumbnail{sub_param}",
                "preview_url": f"/api/processing/tasks/{task_id}/preview?filename={f.name}&size=medium{sub_param}",
            })
        except Exception:
            continue

    return jsonify({
        "success": True,
        "data": {
            "files": result_files, "total": total,
            "page": page, "page_size": page_size, "total_pages": total_pages,
            "sub_dir": sub_dir or "",
        },
        "message": "获取文件列表成功",
    })


# ── 结果预览 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks/<task_id>/preview", methods=["GET"])
def task_preview(task_id):
    """GET /api/processing/tasks/<task_id>/preview?filename=&sub_dir=&size="""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)

    filename = request.args.get("filename")
    if not filename:
        return _error("必须指定 filename 参数")
    sub_dir = request.args.get("sub_dir")
    size = request.args.get("size", "medium")

    out_dir = _get_output_dir(cfg)
    img_path = out_dir / sub_dir / filename if sub_dir else out_dir / filename
    if not img_path.is_file():
        return _error(f"图片不存在: {filename}", 404)

    if size == "original":
        with open(img_path, "rb") as f:
            return Response(f.read(), mimetype="image/jpeg")

    from PIL import Image
    max_size = 400 if size == "thumbnail" else 1920
    quality = 80 if size == "thumbnail" else 85
    with Image.open(img_path) as im:
        im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
        im.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return Response(buf.getvalue(), mimetype="image/jpeg")


# ── 加工数据列表 ─────────────────────────────────────────────
@processing_bp.route("/api/processing/processed", methods=["GET"])
def list_processed():
    """GET /api/processing/processed → 加工数据列表。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    items = registry.list_processed()
    return jsonify({
        "success": True,
        "data": {"items": items, "total": len(items)},
        "message": "获取加工数据列表成功",
    })


@processing_bp.route("/api/processing/processed/<processed_id>", methods=["GET"])
def get_processed(processed_id):
    """GET /api/processing/processed/<id> → 加工数据详情。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    items = registry.list_processed()
    for item in items:
        if Path(item["output_path"]).name == processed_id:
            return jsonify({"success": True, "data": item, "message": "获取加工数据详情成功"})
    return _error(f"加工数据不存在: {processed_id}", 404)


@processing_bp.route("/api/processing/processed/<processed_id>/files", methods=["GET"])
def list_processed_files(processed_id):
    """GET /api/processing/processed/<id>/files?sub_dir=&page=&page_size="""
    return list_task_files(processed_id)


@processing_bp.route("/api/processing/processed/<processed_id>", methods=["DELETE"])
def delete_processed(processed_id):
    """DELETE /api/processing/processed/<id>?delete_output=true"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    delete_output = request.args.get("delete_output", "false").lower() == "true"
    try:
        registry.delete_task(processed_id, delete_output=delete_output)
    except KeyError as e:
        return _error(str(e), 404)
    return jsonify({"success": True, "data": None, "message": "加工数据已删除"})
