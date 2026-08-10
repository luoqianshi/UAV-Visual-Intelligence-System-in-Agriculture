"""模型管理 API：GET /api/models、POST /api/models/switch、POST /api/models/load。

响应信封遵循 spec §5.3：成功/失败均返回 ``{success, data, message}``。
引擎调用（switch 会触发懒加载 ultralytics）用 try/except 兜底，避免 500。
模型注册支持 multipart/form-data 上传权重文件，注册后持久化到 YAML。
"""
import os
import tempfile

from flask import Blueprint, jsonify, request

from core.engine import get_registry

models_bp = Blueprint("models", __name__)


def _parse_form_value(val, type_cast=None):
    """解析表单值，空字符串返回None，支持类型转换。"""
    if val in (None, ""):
        return None
    if type_cast:
        try:
            return type_cast(val)
        except (TypeError, ValueError):
            return None
    return val


@models_bp.route("/api/models", methods=["GET"])
def list_models():
    """返回所有已注册模型与当前激活模型。"""
    registry = get_registry()
    if registry is None:
        return jsonify({
            "success": False, "data": None, "message": "registry 未初始化",
        })
    try:
        models = registry.list_models()
        current = registry.get_active()
    except Exception as exc:
        return jsonify({
            "success": False, "data": None, "message": f"读取模型列表失败: {exc}",
        })
    return jsonify({
        "success": True,
        "data": {"models": models, "current_model": current},
        "message": "ok",
    })


@models_bp.route("/api/models/switch", methods=["POST"])
def switch_model():
    """热切换激活模型。switch 内部会预加载引擎，可能因 ultralytics 缺失而失败。"""
    registry = get_registry()
    if registry is None:
        return jsonify({
            "success": False, "data": None, "message": "registry 未初始化",
        })
    body = request.get_json(silent=True) or {}
    model_name = body.get("model_name")
    if not model_name:
        return jsonify({
            "success": False, "data": None, "message": "缺少 model_name",
        })
    try:
        registry.switch(model_name)
    except KeyError:
        return jsonify({
            "success": False, "data": None,
            "message": f"模型 '{model_name}' 未注册",
        })
    except Exception as exc:
        return jsonify({
            "success": False, "data": None,
            "message": f"切换失败: {exc}",
        })
    return jsonify({
        "success": True,
        "data": {"current_model": model_name, "models": registry.list_models()},
        "message": f"已切换到 {model_name}",
    })


@models_bp.route("/api/models/load", methods=["POST"])
def load_model():
    """动态注册一个模型配置，支持上传权重文件。

    支持两种 Content-Type：
    - multipart/form-data：包含文本字段和 weight_file 文件字段
    - application/json：仅包含配置（需weight为已有路径）
    """
    registry = get_registry()
    if registry is None:
        return jsonify({
            "success": False, "data": None, "message": "registry 未初始化",
        })

    weight_file_tmp = None
    try:
        # 处理文件上传
        weight_file = request.files.get("weight_file")
        if weight_file and weight_file.filename:
            # 保存到临时文件
            ext = os.path.splitext(weight_file.filename)[1] or ".pt"
            fd, tmp_path = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            weight_file.save(tmp_path)
            weight_file_tmp = tmp_path

        # 解析配置参数（兼容 form 和 json）
        if request.files:
            source = request.form
        else:
            source = request.get_json(silent=True) or {}

        name = _parse_form_value(source.get("name"))
        if not name:
            if weight_file_tmp and os.path.exists(weight_file_tmp):
                os.unlink(weight_file_tmp)
            return jsonify({
                "success": False, "data": None, "message": "缺少必填字段 name",
            })

        # 检查名称是否已存在
        try:
            existing = registry.get_config(name)
            if existing:
                if weight_file_tmp and os.path.exists(weight_file_tmp):
                    os.unlink(weight_file_tmp)
                return jsonify({
                    "success": False, "data": None,
                    "message": f"模型 '{name}' 已存在，请使用其他名称",
                })
        except KeyError:
            pass  # 不存在，正常

        # 解析 classes（逗号分隔字符串转数组）
        classes_raw = _parse_form_value(source.get("classes"))
        if isinstance(classes_raw, str):
            classes = [c.strip() for c in classes_raw.split(",") if c.strip()]
        elif isinstance(classes_raw, list):
            classes = classes_raw
        else:
            classes = ["Sugarcane Seedling"]

        config = {
            "name": name,
            "display_name": _parse_form_value(source.get("display_name")) or name,
            "engine": _parse_form_value(source.get("engine")) or "ultralytics",
            "category": _parse_form_value(source.get("category")) or "sugarcane_seedling",
            "classes": classes,
            "imgsz": _parse_form_value(source.get("imgsz"), int) or 640,
            "conf": _parse_form_value(source.get("conf"), float) or 0.25,
            "iou": _parse_form_value(source.get("iou"), float) or 0.7,
            "max_det": _parse_form_value(source.get("max_det"), int) or 300,
            "device": _parse_form_value(source.get("device")),
        }

        # 如果没有上传文件，使用表单中的 weight 路径
        if weight_file_tmp is None:
            weight_path = _parse_form_value(source.get("weight"))
            if weight_path:
                config["weight"] = weight_path
            else:
                return jsonify({
                    "success": False, "data": None,
                    "message": "请上传权重文件或提供 weight 路径",
                })

        registry.register(config, weight_file_path=weight_file_tmp)

    except ValueError as exc:
        if weight_file_tmp and os.path.exists(weight_file_tmp):
            os.unlink(weight_file_tmp)
        return jsonify({
            "success": False, "data": None, "message": str(exc),
        })
    except Exception as exc:
        if weight_file_tmp and os.path.exists(weight_file_tmp):
            os.unlink(weight_file_tmp)
        return jsonify({
            "success": False, "data": None, "message": f"注册失败: {exc}",
        })

    return jsonify({
        "success": True,
        "data": {
            "models": registry.list_models(),
            "current_model": registry.get_active(),
        },
        "message": f"已加载模型 {name}，配置已持久化",
    })
