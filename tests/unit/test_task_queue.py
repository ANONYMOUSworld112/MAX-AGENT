import time
import pytest
from core.max_infra.task_queue import TaskQueue, TaskItem, QueueBackpressureError

def test_task_queue_priority_ordering():
    queue = TaskQueue(max_capacity=10)
    
    # Enqueue in reverse order: Band 3 first, then Band 1, then Band 0
    queue.enqueue(TaskItem(task_id="t-3", priority_band=3, payload={"name": "bg"}))
    queue.enqueue(TaskItem(task_id="t-1", priority_band=1, payload={"name": "interactive"}))
    queue.enqueue(TaskItem(task_id="t-0", priority_band=0, payload={"name": "critical"}))

    # Dequeue must return Band 0, then Band 1, then Band 3
    first = queue.dequeue()
    assert first.task_id == "t-0"
    second = queue.dequeue()
    assert second.task_id == "t-1"
    third = queue.dequeue()
    assert third.task_id == "t-3"

def test_task_queue_backpressure():
    queue = TaskQueue(max_capacity=2)
    queue.enqueue(TaskItem(task_id="1", priority_band=2))
    queue.enqueue(TaskItem(task_id="2", priority_band=2))

    with pytest.raises(QueueBackpressureError):
        queue.enqueue(TaskItem(task_id="3", priority_band=2))

def test_starvation_aging():
    queue = TaskQueue(aging_threshold_seconds=0.1) # short threshold for test
    # Enqueue a low priority task with artificial back-dated timestamp
    item_old = TaskItem(task_id="old-bg", priority_band=3, created_at=time.time() - 0.5)
    item_new = TaskItem(task_id="new-active", priority_band=2, created_at=time.time())

    queue.enqueue(item_old)
    queue.enqueue(item_new)

    # Because old-bg has aged, its effective priority becomes 3 - (0.5 // 0.1) -> 0!
    popped = queue.dequeue()
    assert popped.task_id == "old-bg"
