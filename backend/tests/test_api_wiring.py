"""API 接线验证测试：通过 Flask test client 验证 /api/health、/api/models、
/api/detect、/api/counting 的路由接线与响应信封（spec §5.3）。

说明：app.py 的 Blueprint 注册由编排器统一完成，本测试在 create_app() 之后
手动注册尚未接入的 models/detect/counting 蓝图，确保在 ultralytics/torch 缺失的
开发环境下也能验证 endpoint 路由可达、响应格式合法、错误兜底正确。

运行：cd backend && python -m pytest tests/test_api_wiring.py -v
"""
import pytest


@pytest.fixture(scope="module")
def app():
    """创建 Flask app（app.py 已统一注册全部 Blueprint）。"""
    from app import create_app
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _restore_active_model():
    """每个测试前将激活模型复位为默认值，避免 switch 测试污染后续断言。

    autouse + function 作用域，会在 module 级 app 夹具初始化之后运行。
    """
    from core.engine import get_registry
    registry = get_registry()
    if registry is not None and registry.ready:
        registry._active_model = "yolov8s-sugarcane"
    yield
    if registry is not None and registry.ready:
        registry._active_model = "yolov8s-sugarcane"


# ---------------------------------------------------------------------------
# 1. GET /api/health：真实 registry 状态
# ---------------------------------------------------------------------------
def test_health_real_registry(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["registry_ready"] is True
    assert data["current_model"] == "yolov8s-sugarcane"


# ---------------------------------------------------------------------------
# 2. GET /api/models：4 个模型，默认激活 yolov8s-sugarcane
# ---------------------------------------------------------------------------
def test_models_list(client):
    resp = client.get("/api/models")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert len(data["models"]) == 4
    assert data["current_model"] == "yolov8s-sugarcane"
    by_name = {m["name"]: m for m in data["models"]}
    assert by_name["yolov8s-sugarcane"]["is_active"] is True
    assert by_name["yolov5su-sugarcane"]["is_active"] is False


# ---------------------------------------------------------------------------
# 3. POST /api/models/switch（合法模型名）：响应必须是合法 JSON 且带 success
#    无 ultralytics/torch 时 switch 因 _load_engine 失败而 success:False（也合法）
# ---------------------------------------------------------------------------
def test_models_switch_valid_returns_json(client):
    resp = client.post(
        "/api/models/switch", json={"model_name": "yolov5su-sugarcane"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "success" in body
    assert isinstance(body["success"], bool)


# ---------------------------------------------------------------------------
# 4. POST /api/models/switch（未知模型）：success:False（KeyError 兜底）
# ---------------------------------------------------------------------------
def test_models_switch_unknown_model(client):
    resp = client.post(
        "/api/models/switch", json={"model_name": "nonexistent"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["message"]


# ---------------------------------------------------------------------------
# 5. POST /api/detect（无 image、无 image_dir）：success:False + message
# ---------------------------------------------------------------------------
def test_detect_no_input(client):
    resp = client.post("/api/detect", json={})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["message"]


# ---------------------------------------------------------------------------
# 6. GET /api/counting/history：data 为列表（可能为空）
# ---------------------------------------------------------------------------
def test_counting_history(client):
    resp = client.get("/api/counting/history")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


# ---------------------------------------------------------------------------
# 7. SPA 客户端路由回退：非 /api、非真实文件路径应返回 index.html（200）
#    回归测试：曾因 Flask 内置 static 端点优先于 serve_spa 导致 /algo/models 等
#    客户端路由返回 404，刷新页面白屏。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("spa_route", [
    "/algo/models",
    "/algo/counting",
    "/data/batches",
    "/process/tasks",
    "/dataset/datasets",
])
def test_spa_route_fallback(client, spa_route):
    resp = client.get(spa_route)
    assert resp.status_code == 200
    assert b"<div id=\"app\">" in resp.data


# ---------------------------------------------------------------------------
# 8. 未匹配的 /api 路由应返回 404 JSON（而非 SPA index.html）
# ---------------------------------------------------------------------------
def test_unknown_api_route_returns_404_json(client):
    resp = client.get("/api/nonexistent-endpoint")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
