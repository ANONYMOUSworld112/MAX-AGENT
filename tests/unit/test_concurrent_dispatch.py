"""
Unit tests for TaskGraphDispatcher Concurrent Execution & Resource Leases
==========================================================================

Covers:
- Independent tasks executing in parallel ("Build project and play music")
- Dependent tasks serializing in topological order
- Resource conflicts serializing without deadlock (two tasks needing desktop-input)
- Failure branch execution (ON_SUCCESS skipped, ON_FAILURE executed)
"""

import threading
import time
import pytest

from core.contracts import ActionResult, TaskIntent, Task
from core.max_infra.lock_manager import (
    LockManager,
    RESOURCE_AUDIO_OUT,
    RESOURCE_DESKTOP_INPUT,
    canonical_project_resource,
)
from core.scheduler import TaskGraphDispatcher
from core.task_graph import EdgeCondition, NodeStatus, TaskGraph, TaskNode


def test_independent_tasks_run_in_parallel():
    lm = LockManager(default_ttl=5.0)
    dispatcher = TaskGraphDispatcher(lock_manager=lm, max_workers=4)

    graph = TaskGraph(graph_id="g_parallel")
    t1_res = canonical_project_resource("f:/max-agent")
    t2_res = RESOURCE_AUDIO_OUT

    intent1 = TaskIntent(action="build_project", parameters={"resources": [t1_res]})
    node1 = TaskNode(node_id="n_build", intent=intent1)

    intent2 = TaskIntent(action="play_music", parameters={"resources": [t2_res]})
    node2 = TaskNode(node_id="n_music", intent=intent2)

    graph.add_node(node1)
    graph.add_node(node2)

    timings = {}
    lock = threading.Lock()

    def mock_worker(node: TaskNode) -> ActionResult:
        t_start = time.time()
        time.sleep(0.1)  # Simulate workload
        t_end = time.time()
        with lock:
            timings[node.node_id] = (t_start, t_end)
        return ActionResult(task_id=node.node_id, success=True)

    results = dispatcher.dispatch(graph, mock_worker, timeout=5.0)

    assert graph.is_complete()
    assert results["n_build"].success is True
    assert results["n_music"].success is True

    # Verify execution intervals overlapped
    s1, e1 = timings["n_build"]
    s2, e2 = timings["n_music"]
    overlap = max(s1, s2) < min(e1, e2)
    assert overlap, f"Expected parallel overlap between ({s1}, {e1}) and ({s2}, {e2})"


def test_dependent_tasks_serialize_in_order():
    lm = LockManager(default_ttl=5.0)
    dispatcher = TaskGraphDispatcher(lock_manager=lm, max_workers=4)

    graph = TaskGraph(graph_id="g_seq")
    node_a = TaskNode(node_id="step_a", intent=TaskIntent(action="compile"))
    node_b = TaskNode(node_id="step_b", intent=TaskIntent(action="package"))

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_edge("step_a", "step_b", condition=EdgeCondition.ON_SUCCESS)

    timings = {}
    lock = threading.Lock()

    def mock_worker(node: TaskNode) -> ActionResult:
        t_start = time.time()
        time.sleep(0.05)
        t_end = time.time()
        with lock:
            timings[node.node_id] = (t_start, t_end)
        return ActionResult(task_id=node.node_id, success=True)

    results = dispatcher.dispatch(graph, mock_worker, timeout=5.0)

    assert graph.is_complete()
    assert results["step_a"].success is True
    assert results["step_b"].success is True

    # step_b must start at or after step_a finishes
    _, end_a = timings["step_a"]
    start_b, _ = timings["step_b"]
    assert start_b >= end_a - 0.01  # Allow tiny clock granularity margin


def test_resource_conflict_serializes_execution():
    lm = LockManager(default_ttl=5.0)
    dispatcher = TaskGraphDispatcher(lock_manager=lm, max_workers=4)

    graph = TaskGraph(graph_id="g_conflict")

    # Both independent tasks require exclusive desktop-input
    node1 = TaskNode(
        node_id="task_gui_1",
        intent=TaskIntent(action="click_button", parameters={"resources": [RESOURCE_DESKTOP_INPUT]}),
    )
    node2 = TaskNode(
        node_id="task_gui_2",
        intent=TaskIntent(action="type_text", parameters={"resources": [RESOURCE_DESKTOP_INPUT]}),
    )

    graph.add_node(node1)
    graph.add_node(node2)

    timings = {}
    lock = threading.Lock()

    def mock_worker(node: TaskNode) -> ActionResult:
        t_start = time.time()
        time.sleep(0.08)
        t_end = time.time()
        with lock:
            timings[node.node_id] = (t_start, t_end)
        return ActionResult(task_id=node.node_id, success=True)

    results = dispatcher.dispatch(graph, mock_worker, timeout=5.0)

    assert graph.is_complete()
    assert results["task_gui_1"].success is True
    assert results["task_gui_2"].success is True

    # Intervals must NOT overlap due to exclusive lock
    s1, e1 = timings["task_gui_1"]
    s2, e2 = timings["task_gui_2"]
    no_overlap = (e1 <= s2) or (e2 <= s1)
    assert no_overlap, f"Conflicting tasks overlapped! ({s1}, {e1}) vs ({s2}, {e2})"


def test_failure_condition_branching():
    lm = LockManager(default_ttl=5.0)
    dispatcher = TaskGraphDispatcher(lock_manager=lm, max_workers=4)

    graph = TaskGraph(graph_id="g_failure")

    node_main = TaskNode(node_id="main_task", intent=TaskIntent(action="run_tests"))
    node_success = TaskNode(node_id="deploy_task", intent=TaskIntent(action="deploy"))
    node_handler = TaskNode(node_id="notify_failure", intent=TaskIntent(action="notify"))

    graph.add_node(node_main)
    graph.add_node(node_success)
    graph.add_node(node_handler)

    graph.add_edge("main_task", "deploy_task", condition=EdgeCondition.ON_SUCCESS)
    graph.add_edge("main_task", "notify_failure", condition=EdgeCondition.ON_FAILURE)

    def mock_worker(node: TaskNode) -> ActionResult:
        if node.node_id == "main_task":
            # Simulate failure
            return ActionResult(task_id=node.node_id, success=False, error_message="Tests failed")
        return ActionResult(task_id=node.node_id, success=True)

    results = dispatcher.dispatch(graph, mock_worker, timeout=5.0)

    assert graph.is_complete()
    assert results["main_task"].success is False
    assert results["notify_failure"].success is True
    # deploy_task should be SKIPPED
    assert graph.nodes["deploy_task"].status == NodeStatus.SKIPPED
