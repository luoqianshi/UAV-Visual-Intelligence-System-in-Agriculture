"""计数结果持久化：保存到 results/{result_id}/，列历史，加载指定结果。"""
import base64
import json
from datetime import datetime, timezone

from config import RESULTS_DIR


def save_counting_result(result: dict) -> str:
    """保存计数结果，返回 result_id。

    产物目录 results/{result_id}/：
      - result_image.jpg   标注图（base64 解码后写入）
      - meta.json          轻量元信息（用于历史列表）
      - counting_data.json 完整计数数据（除 annotated_image 外）
    """
    result_id = result.get("result_id") or f"count_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    out_dir = RESULTS_DIR / result_id
    out_dir.mkdir(parents=True, exist_ok=True)

    annotated = result.get("annotated_image")
    if annotated:
        (out_dir / "result_image.jpg").write_bytes(base64.b64decode(annotated))

    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "result_id": result_id,
        "model_info": result.get("model_info"),
        "params_snapshot": result.get("params_snapshot"),
        "image_size": result.get("image_size"),
        "tile_count": result.get("tile_count"),
        "count": result.get("count"),
        "density_per_m2": result.get("density_per_m2"),
        "area_m2": result.get("area_m2"),
        "created_at": created_at,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    counting_data = {k: v for k, v in result.items() if k != "annotated_image"}
    counting_data["result_id"] = result_id
    counting_data["created_at"] = created_at
    (out_dir / "counting_data.json").write_text(
        json.dumps(counting_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return result_id


def list_counting_history() -> list:
    """列出所有历史计数结果（按 created_at 倒序）。"""
    if not RESULTS_DIR.exists():
        return []
    items = []
    for d in RESULTS_DIR.iterdir():
        if not d.is_dir():
            continue
        meta_file = d / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {"result_id": d.name}
        else:
            meta = {"result_id": d.name}
        meta["result_dir"] = str(d)
        items.append(meta)
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def load_counting_result(result_id: str) -> dict:
    """加载指定结果的完整计数数据。"""
    data_file = RESULTS_DIR / result_id / "counting_data.json"
    if not data_file.exists():
        raise FileNotFoundError(f"结果不存在: {result_id}")
    return json.loads(data_file.read_text(encoding="utf-8"))
