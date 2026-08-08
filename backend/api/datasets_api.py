"""数据集只读 Mock API。

提供数据集列表（含格式分布）、详情与统计报告。
所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from config import MOCK_DIR

datasets_bp = Blueprint("datasets", __name__)


def _load_datasets():
    """读取 mock/datasets.json。"""
    with open(MOCK_DIR / "datasets.json", encoding="utf-8") as f:
        return json.load(f)


def _format_dist(datasets):
    """按标注格式统计数据集数量。"""
    dist = {"YOLO": 0, "COCO": 0, "VOC": 0}
    for d in datasets:
        fmt = d.get("format")
        if fmt in dist:
            dist[fmt] += 1
        else:
            dist[fmt] = dist.get(fmt, 0) + 1
    return dist


@datasets_bp.route("/api/datasets", methods=["GET"])
def list_datasets():
    """GET /api/datasets → 数据集列表，支持 ?format= 过滤，并返回格式分布。"""
    datasets = _load_datasets()
    fmt = request.args.get("format")
    if fmt:
        filtered = [d for d in datasets if d.get("format") == fmt]
    else:
        filtered = datasets
    return jsonify({
        "success": True,
        "data": {
            "datasets": filtered,
            "total": len(filtered),
            "format_dist": _format_dist(datasets),
        },
        "message": "获取数据集列表成功",
    })


@datasets_bp.route("/api/datasets/<dataset_id>", methods=["GET"])
def get_dataset(dataset_id):
    """GET /api/datasets/<dataset_id> → 单个数据集详情。"""
    datasets = _load_datasets()
    for d in datasets:
        if d.get("id") == dataset_id:
            return jsonify({
                "success": True,
                "data": d,
                "message": "获取数据集详情成功",
            })
    return jsonify({
        "success": False,
        "data": None,
        "message": f"数据集不存在: {dataset_id}",
    }), 404


@datasets_bp.route("/api/datasets/<dataset_id>/report", methods=["GET"])
def dataset_report(dataset_id):
    """GET /api/datasets/<dataset_id>/report → 数据集统计报告。"""
    datasets = _load_datasets()
    dataset = next((d for d in datasets if d.get("id") == dataset_id), None)
    if dataset is None:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"数据集不存在: {dataset_id}",
        }), 404

    total = dataset.get("sample_count", 0)
    train = dataset.get("train_count", 0)
    val = dataset.get("val_count", 0)
    test = dataset.get("test_count", 0)
    object_count = dataset.get("object_count", 0)
    classes = dataset.get("classes", [])

    return jsonify({
        "success": True,
        "data": {
            "dataset_id": dataset_id,
            "summary": {
                "total_samples": total,
                "train_count": train,
                "val_count": val,
                "test_count": test,
                "split_ratio": dataset.get("split_ratio"),
                "object_count": object_count,
            },
            "class_dist": [
                {"class": c, "count": object_count}
                for c in classes
            ],
            "format": dataset.get("format"),
            "version": dataset.get("version"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": "获取数据集统计报告成功",
    })
