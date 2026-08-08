"""健康检查 API：GET /api/health。"""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    """返回服务状态与引擎就绪情况。

    Task 1 占位实现：registry 未集成时返回基础状态。
    Task 10 将更新为返回真实 registry 状态。
    """
    return jsonify({
        "success": True,
        "data": {
            "status": "ok",
            "version": "v1.0.0",
            "detector_ready": False,
            "registry_ready": False,
            "current_model": None,
        },
        "message": "服务运行中",
    })
