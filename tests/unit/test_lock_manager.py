import threading
import time
import pytest
from core.max_infra.lock_manager import LockManager, LockTimeoutError

def test_sorted_order_acquisition_and_release():
    lm = LockManager(default_ttl=10.0)
    resources = ["file:z_auth.py", "file:a_config.py", "port:8000"]
    
    # Must sort canonically: file:a_config.py, file:z_auth.py, port:8000
    with lm.acquire(resources, task_id="task-01"):
        assert lm.is_locked("file:a_config.py") is True
        assert lm.is_locked("file:z_auth.py") is True
        assert lm.is_locked("port:8000") is True

    # All locks must be released
    assert lm.is_locked("file:a_config.py") is False
    assert lm.is_locked("file:z_auth.py") is False
    assert lm.is_locked("port:8000") is False

def test_lock_timeout_conflict():
    lm = LockManager(default_ttl=10.0)
    
    def holder():
        with lm.acquire(["resource_shared"], task_id="holder_task"):
            time.sleep(1.0)

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.05)

    # Contender should fail with short timeout
    with pytest.raises(LockTimeoutError):
        with lm.acquire(["resource_shared"], task_id="contender_task", timeout=0.05):
            pass

    t.join()
