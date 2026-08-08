"""模型管理 API：GET /api/models、POST /api/models/switch、POST /api/models/load。

响应信封遵循 spec §5.3：成功/失败均返回 ``{success, data, message}``。
引擎调用（switch 会触发懒加载 ultralytics）用 try/except 兜底，避免 500。
"""
from flask import Blueprint, jsonify, request

from core.engine import get_registry

models_bp = Blueprint("models", __name__)


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
        # ultralytics/torch 缺失时 _load_engine 抛 ImportError，归到此处
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
    """动态注册一个模型配置。必填字段：name。"""
    registry = get_registry()
    if registry is None:
        return jsonify({
            "success": False, "data": None, "message": "registry 未初始化",
        })
    config = request.get_json(silent=True) or {}
    if not config.get("name"):
        return jsonify({
            "success": False, "data": None, "message": "缺少必填字段 name",
        })
    try:
        registry.register(config)
    except Exception as exc:
        return jsonify({
            "success": False, "data": None, "message": f"注册失败: {exc}",
        })
    return jsonify({
        "success": True,
        "data": {
            "models": registry.list_models(),
            "current_model": registry.get_active(),
        },
        "message": f"已加载模型 {config['name']}",
    })
