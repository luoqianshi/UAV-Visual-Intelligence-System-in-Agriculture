"""健康检查 API：GET /api/health。"""
from flask import Blueprint, jsonify

from core.engine import get_registry

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    registry = get_registry()
    ready = registry is not None and registry.ready
    active = registry.get_active() if ready else None
    return jsonify({
        "success": True,
        "data": {
            "status": "ok",
            "version": "v1.0.0",
            "detector_ready": ready,
            "registry_ready": ready,
            "current_model": active,
        },
        "message": "服务运行中",
    })
