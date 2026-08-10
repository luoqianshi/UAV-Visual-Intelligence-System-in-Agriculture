"""Flask 应用入口：注册 Blueprint，托管前端静态资源。

开发期：Vite :3000 代理 /api → :5000。
生产部署：npm run build 产物落入 backend/static/，Flask :5000 单端口提供 API 与静态资源。
"""
import os
import sys
from pathlib import Path

# 确保 backend/ 目录在 sys.path 上，使 bare 导入（from core.x / from config / from api.x）生效
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from flask import Flask, send_from_directory  # noqa: E402

from api.health_api import health_bp  # noqa: E402
from api.models_api import models_bp  # noqa: E402
from api.detect_api import detect_bp  # noqa: E402
from api.counting_api import counting_bp  # noqa: E402
from api.batches_api import batches_bp  # noqa: E402
from api.processing_api import processing_bp  # noqa: E402
from api.datasets_api import datasets_bp  # noqa: E402
from config import STATIC_DIR, HOST, PORT, DEBUG  # noqa: E402


def create_app() -> Flask:
    """创建并配置 Flask 应用。

    不启用 Flask 内置 static 端点（static_folder/static_url_path）：
    内置端点会注册 /<path:filename> 路由并优先于自定义 serve_spa，
    导致 /algo/models 等 SPA 客户端路由（非真实文件）被 static 端点拦截返回 404，
    而非回退到 index.html。改由下方 serve_spa 统一处理静态资源与 SPA 回退。
    """
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 文件上传限制

    # 引擎初始化（Task 9）：失败时降级运行，仅记录警告
    try:
        from core.engine import init_engines
        init_engines()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"引擎初始化失败（API 将以降级模式运行）：{exc}"
        )

    # 注册 Blueprint
    app.register_blueprint(health_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(detect_bp)
    app.register_blueprint(counting_bp)
    app.register_blueprint(batches_bp)
    app.register_blueprint(processing_bp)
    app.register_blueprint(datasets_bp)

    # 全局错误兜底：未捕获异常统一返回 JSON 信封，避免前端收到 HTML 500
    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc  # 404/405 等保持默认行为（SPA 回退不受影响）
        app.logger.exception("未捕获异常")
        return {"success": False, "data": None,
                "message": f"服务器内部错误: {exc}"}, 500

    # SPA 静态资源兜底：非 /api 路由回退到 index.html
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        if path.startswith("api"):
            # 未匹配的 API 路由返回 404 JSON
            return {"success": False, "data": None, "message": f"路由不存在: /{path}"}, 404
        full = STATIC_DIR / path
        if full.is_file():
            return send_from_directory(str(STATIC_DIR), path)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return send_from_directory(str(STATIC_DIR), "index.html")
        # 静态资源尚未构建
        return {"success": True, "data": {"service": "低空智瞰 UAV 智能监测系统"},
                "message": "前端尚未构建，请先 cd frontend && npm install && npm run build"}, 200

    return app


# 引擎初始化（Task 9 起启用）
def _init_engines():
    try:
        from core.engine import init_engines
        init_engines()
    except Exception as exc:  # pragma: no cover - 启动期容错
        print(f"[警告] 引擎初始化失败：{exc}")


app = create_app()


if __name__ == "__main__":
    # create_app() 已完成引擎初始化，此处直接启动
    app.run(host=HOST, port=PORT, debug=DEBUG)
