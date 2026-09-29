import pytest
from core.max_infra.task_lifecycle import TaskLifecycleFSM, TaskState, InvalidStateTransitionError

def test_valid_lifecycle_transitions():
    fsm = TaskLifecycleFSM()
    state = TaskState.CREATED
    
    state = fsm.transition(state, TaskState.QUEUED)
    assert state == TaskState.QUEUED

    state = fsm.transition(state, TaskState.LOCK_WAIT)
    assert state == TaskState.LOCK_WAIT

    state = fsm.transition(state, TaskState.RUNNING)
    assert state == TaskState.RUNNING

    state = fsm.transition(state, TaskState.RECONCILING)
    assert state == TaskState.RECONCILING

    state = fsm.transition(state, TaskState.DONE)
    assert state == TaskState.DONE

def test_invalid_lifecycle_transition():
    fsm = TaskLifecycleFSM()
    with pytest.raises(InvalidStateTransitionError):
        # Cannot jump from CREATED directly to DONE
        fsm.transition(TaskState.CREATED, TaskState.DONE)

def test_kill_switch_cancellation_from_any_active_state():
    fsm = TaskLifecycleFSM()
    for active_state in [TaskState.CREATED, TaskState.QUEUED, TaskState.LOCK_WAIT, TaskState.RUNNING]:
        assert fsm.transition(active_state, TaskState.CANCELLED) == TaskState.CANCELLED
