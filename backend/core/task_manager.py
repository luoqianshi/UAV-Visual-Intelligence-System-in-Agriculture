"""异步任务管理：ThreadPoolExecutor(max_workers=1) + 内存任务表。"""
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

class TaskManager:
    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict = {}

    def submit(self, task_type: str, func, *args, **kwargs) -> str:
        task_id = f"{task_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self._tasks[task_id] = {"task_id": task_id, "task_type": task_type, "status": "pending",
            "progress": 0.0, "result": None, "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(), "completed_at": None}

        def _run():
            self._tasks[task_id]["status"] = "processing"
            try:
                self._tasks[task_id]["result"] = func(task_id, *args, **kwargs)
                self._tasks[task_id]["progress"] = 1.0
                self._tasks[task_id]["status"] = "completed"
            except Exception as e:
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["status"] = "failed"
            finally:
                self._tasks[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

        self._executor.submit(_run)
        return task_id

    def get(self, task_id: str) -> dict:
        return self._tasks.get(task_id, {"error": "任务不存在"})

    def update(self, task_id: str, **fields) -> None:
        if task_id in self._tasks:
            self._tasks[task_id].update(fields)

    def list(self, task_type=None, status=None) -> list:
        tasks = list(self._tasks.values())
        if task_type: tasks = [t for t in tasks if t["task_type"] == task_type]
        if status: tasks = [t for t in tasks if t["status"] == status]
        return sorted(tasks, key=lambda t: t["created_at"], reverse=True)
