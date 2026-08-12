import time
from core.task_manager import TaskManager


def _wait(tm, task_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = tm.get(task_id)
        if t["status"] in ("completed", "failed"):
            return t
        time.sleep(0.02)
    return tm.get(task_id)


def test_submit_and_query_result():
    tm = TaskManager()

    def add_task(task_id, a, b):
        return a + b

    task_id = tm.submit("compute", add_task, 3, 4)
    t = _wait(tm, task_id)
    assert t["status"] == "completed"
    assert t["result"] == 7
    assert t["task_type"] == "compute"
    assert t["progress"] == 1.0
    assert t["error"] is None
    assert t["completed_at"] is not None


def test_progress_update_via_update():
    tm = TaskManager()

    def slow_task(task_id):
        time.sleep(0.3)
        return "done"

    task_id = tm.submit("slow", slow_task)
    # 让 worker 进入 processing；func 内部不触碰 progress，故 update 写入的值会保留
    time.sleep(0.05)
    tm.update(task_id, progress=0.5)
    t = tm.get(task_id)
    assert t["progress"] == 0.5
    # 等待完成，确认最终 progress 回到 1.0
    t_final = _wait(tm, task_id)
    assert t_final["status"] == "completed"
    assert t_final["progress"] == 1.0


def test_failed_status():
    tm = TaskManager()

    def failing_task(task_id):
        raise ValueError("boom")

    task_id = tm.submit("will_fail", failing_task)
    t = _wait(tm, task_id)
    assert t["status"] == "failed"
    assert t["result"] is None
    assert "boom" in t["error"]
    assert t["completed_at"] is not None


def test_list_by_type_and_status():
    tm = TaskManager()

    def ok_task(task_id):
        return 1

    def bad_task(task_id):
        raise RuntimeError("x")

    id_a = tm.submit("alpha", ok_task)
    id_b1 = tm.submit("beta", ok_task)
    id_b2 = tm.submit("beta", bad_task)

    for tid in (id_a, id_b1, id_b2):
        _wait(tm, tid)

    # 按 task_type 过滤
    alpha = tm.list(task_type="alpha")
    assert len(alpha) == 1
    assert alpha[0]["task_type"] == "alpha"
    assert alpha[0]["task_id"] == id_a

    beta = tm.list(task_type="beta")
    assert len(beta) == 2
    assert all(t["task_type"] == "beta" for t in beta)

    # 按 status 过滤
    completed = tm.list(status="completed")
    assert all(t["status"] == "completed" for t in completed)
    assert len(completed) == 2

    failed = tm.list(status="failed")
    assert len(failed) == 1
    assert failed[0]["task_id"] == id_b2


def test_get_nonexistent_task():
    tm = TaskManager()
    t = tm.get("does_not_exist")
    assert "error" in t


def test_submit_with_custom_task_id():
    """submit 支持自定义 task_id 参数。"""
    tm = TaskManager(max_workers=1)
    custom_id = "clahe_20260812_153000_456"

    def _dummy(task_id):
        return {"task_id": task_id}

    returned_id = tm.submit("processing", _dummy, task_id=custom_id)
    assert returned_id == custom_id
    # 等待任务完成
    import time
    time.sleep(0.2)
    task = tm.get(custom_id)
    assert task["task_id"] == custom_id
    assert task["status"] == "completed"
    assert task["result"] == {"task_id": custom_id}


def test_submit_without_task_id_backward_compatible():
    """不传 task_id 时仍按原逻辑生成。"""
    tm = TaskManager(max_workers=1)
    returned_id = tm.submit("test", lambda tid: None)
    assert returned_id.startswith("test_")
    assert tm.get(returned_id) is not None
