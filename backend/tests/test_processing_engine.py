"""ProcessingEngine 单元测试。"""
import json
from pathlib import Path

import pytest

from core.processing_engine import ProcessingEngine

FIXTURES = Path(__file__).parent / "fixtures" / "sample_images"


@pytest.fixture
def engine():
    return ProcessingEngine()


@pytest.fixture
def tmp_input_dir(tmp_path):
    """创建临时输入目录，复制一张测试图。"""
    import shutil
    src = FIXTURES / "small_640.jpg"
    dst_dir = tmp_path / "input_batch"
    dst_dir.mkdir()
    shutil.copy(src, dst_dir / "DJI_0001.jpg")
    shutil.copy(src, dst_dir / "DJI_0002.jpg")
    return dst_dir


def test_run_clahe_single_batch(engine, tmp_input_dir, tmp_path):
    """CLAHE 增强单架次：生成增强图与 index.json。"""
    output_dir = tmp_path / "clahe_test"
    output_dir.mkdir()
    params = {"clip_limit": 2.0, "grid_size": [8, 8]}

    result = engine.run_clahe(
        task_id="clahe_test_001",
        input_paths=[str(tmp_input_dir)],
        params=params,
        output_dir=output_dir,
    )

    assert result["total_images"] == 2
    assert result["processed_images"] == 2
    assert len(result["sub_dirs"]) == 1
    assert result["sub_dirs"][0]["sub_dir"] == "input_batch"
    sub_dir = output_dir / "input_batch"
    assert (sub_dir / "DJI_0001.jpg").is_file()
    assert (sub_dir / "DJI_0002.jpg").is_file()


def test_run_clahe_multiple_batches(engine, tmp_path):
    """CLAHE 多架次合并处理：按架次分子目录。"""
    import shutil
    batch1 = tmp_path / "batch1"
    batch1.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", batch1 / "a.jpg")
    batch2 = tmp_path / "batch2"
    batch2.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", batch2 / "b.jpg")

    output_dir = tmp_path / "clahe_multi"
    output_dir.mkdir()
    params = {"clip_limit": 2.0, "grid_size": [8, 8]}

    result = engine.run_clahe(
        task_id="clahe_multi_001",
        input_paths=[str(batch1), str(batch2)],
        params=params,
        output_dir=output_dir,
    )

    assert result["total_images"] == 2
    assert len(result["sub_dirs"]) == 2
    assert (output_dir / "batch1" / "a.jpg").is_file()
    assert (output_dir / "batch2" / "b.jpg").is_file()


def test_run_crop_naming_convention(engine, tmp_path):
    """裁切子图命名：{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg"""
    import shutil
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "medium_1280.jpg", input_dir / "DJI_0001.JPG")

    output_dir = tmp_path / "crop_test"
    output_dir.mkdir()
    params = {"tile_size": 640, "overlap_ratio": 0.05}

    result = engine.run_crop(
        task_id="crop_test_001",
        input_paths=[str(input_dir)],
        params=params,
        output_dir=output_dir,
    )

    sub_dir = output_dir / "input"
    files = list(sub_dir.glob("*.jpg"))
    assert len(files) > 0
    import re
    pattern = r"^DJI_0001_tile_\d{4}_x\d+_y\d+\.jpg$"
    for f in files:
        assert re.match(pattern, f.name), f"命名不符: {f.name}"
    assert result["total_tiles"] > 0


def test_run_crop_progress_callback(engine, tmp_path):
    """裁切进度回调被正确调用。"""
    import shutil
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "a.jpg")
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "b.jpg")

    output_dir = tmp_path / "crop_progress"
    output_dir.mkdir()
    progress_calls = []

    def on_progress(processed, total):
        progress_calls.append((processed, total))

    engine.run_crop(
        task_id="crop_progress_001",
        input_paths=[str(input_dir)],
        params={"tile_size": 640, "overlap_ratio": 0.05},
        output_dir=output_dir,
        on_progress=on_progress,
    )

    assert len(progress_calls) == 2
    assert progress_calls[-1] == (2, 2)


def test_write_index(engine, tmp_path):
    """write_index 生成 index.json。"""
    output_dir = tmp_path / "index_test"
    output_dir.mkdir()
    result = {
        "total_images": 2,
        "processed_images": 2,
        "output_dir": str(output_dir),
        "sub_dirs": [{"sub_dir": "batch1", "image_count": 2}],
    }
    engine.write_index(
        output_dir=output_dir,
        task_id="clahe_index_001",
        task_type="clahe",
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
        result=result,
        created_at="2026-08-12T15:30:00",
    )
    index_file = output_dir / "index.json"
    assert index_file.is_file()
    data = json.loads(index_file.read_text(encoding="utf-8"))
    assert data["task_id"] == "clahe_index_001"
    assert data["task_type"] == "clahe"
    assert data["total_images"] == 2
    assert data["sub_dirs"][0]["sub_dir"] == "batch1"


def test_collect_inputs_normalization(engine, tmp_path):
    """_collect_inputs 把路径列表归一化为 (sub_dir, [image_paths])。"""
    import shutil
    d1 = tmp_path / "batch_a"
    d1.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", d1 / "x.jpg")
    d2 = tmp_path / "batch_b"
    d2.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", d2 / "y.jpg")

    sources = engine._collect_inputs([str(d1), str(d2)])
    assert len(sources) == 2
    assert sources[0][0] == "batch_a"
    assert sources[1][0] == "batch_b"
    assert len(sources[0][1]) == 1
    assert len(sources[1][1]) == 1


def test_collect_inputs_subdir_collision(engine, tmp_path):
    """同名的输入目录会追加 _2/_3 后缀避免冲突。"""
    import shutil
    p1 = tmp_path / "parent1" / "sugarcane_5m"
    p1.mkdir(parents=True)
    shutil.copy(FIXTURES / "small_640.jpg", p1 / "a.jpg")
    p2 = tmp_path / "parent2" / "sugarcane_5m"
    p2.mkdir(parents=True)
    shutil.copy(FIXTURES / "small_640.jpg", p2 / "b.jpg")

    sources = engine._collect_inputs([str(p1), str(p2)])
    assert sources[0][0] == "sugarcane_5m"
    assert sources[1][0] == "sugarcane_5m_2"


def test_error_isolation(engine, tmp_path):
    """单张图片失败不中断整体处理。"""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    import shutil
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "good.jpg")
    (input_dir / "bad.txt").write_text("not an image")

    output_dir = tmp_path / "error_test"
    output_dir.mkdir()

    result = engine.run_clahe(
        task_id="err_001",
        input_paths=[str(input_dir)],
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
        output_dir=output_dir,
    )
    assert result["total_images"] == 1
    assert result["processed_images"] == 1
