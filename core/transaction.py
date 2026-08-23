"""
MAX OS — Transaction & Atomic Rollback Engine (Section 14).
Wraps all Tier 2 destructive/sensitive operations in an atomic transaction lifecycle:
  START TRANSACTION -> SNAPSHOT -> CONFIRM -> EXECUTE -> VERIFY -> COMMIT (or ROLLBACK).
Guarantees clean restore to pre-action state on failure, refusal, or kill switch trigger.
"""

from __future__ import annotations

import contextlib
import enum
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

from core.kill_switch import get_kill_switch, require_armed
from core.reconciliation import ReconciliationChecker, ReconciliationResult
from core.security.security_gate import RiskTier, SecurityGate, SecurityGateBlockedError
from core.snapshot import Snapshot, SnapshotManager
from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationResult

T = TypeVar("T")


class TransactionState(str, enum.Enum):
    INITIALIZED = "initialized"
    SNAPSHOT_TAKEN = "snapshot_taken"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VERIFIED = "verified"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionRecord:
    transaction_id: str
    action_type: str
    target: str
    state: TransactionState
    started_at: float
    completed_at: Optional[float] = None
    snapshot: Optional[Snapshot] = None
    verification: Optional[VerificationResult] = None
    error_message: Optional[str] = None


class TransactionManager:
    """
    Manages atomic transaction lifecycles for destructive and sensitive computer-use actions.
    Integrates SnapshotManager, SecurityGate, and VerificationEngine.
    """

    def __init__(
        self,
        snapshot_manager: Optional[SnapshotManager] = None,
        security_gate: Optional[SecurityGate] = None,
        verification_engine: Optional[VerificationEngine] = None,
        reconciliation_checker: Optional[ReconciliationChecker] = None,
    ):
        self.snapshot_mgr = snapshot_manager or SnapshotManager()
        self.security_gate = security_gate or SecurityGate()
        self.verifier = verification_engine or VerificationEngine()
        self.reconciliation = reconciliation_checker or ReconciliationChecker()
        self._active_transactions: Dict[str, TransactionRecord] = {}

    def execute_transactional_action(
        self,
        action_type: str,
        target: str,
        task_id: str,
        workspace_root: Path | str,
        action_fn: Callable[[], T],
        expected_result: Dict[str, Any],
        approval_token: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[TransactionRecord, Optional[T]]:
        """
        Executes a Tier 2 action wrapped in an atomic rollback transaction.
        """
        require_armed(get_kill_switch())
        tx_id = f"tx_{uuid.uuid4().hex[:8]}"
        tx = TransactionRecord(
            transaction_id=tx_id,
            action_type=action_type,
            target=target,
            state=TransactionState.INITIALIZED,
            started_at=time.time(),
        )
        self._active_transactions[tx_id] = tx

        # 1. Take Pre-execution Snapshot
        root_path = Path(workspace_root).resolve()
        snapshot = self.snapshot_mgr.take_snapshot(root_path, task_id=tx_id)
        tx.snapshot = snapshot
        tx.state = TransactionState.SNAPSHOT_TAKEN

        # 2. Authorize with SecurityGate (checks Tier 2 single-use token)
        try:
            self.security_gate.authorize_action(
                action_type=action_type,
                target=target,
                task_id=task_id,
                action_id=tx_id,
                approval_token=approval_token,
                action_payload=action_payload,
            )
            tx.state = TransactionState.AUTHORIZED
        except Exception as auth_err:
            # Clean up snapshot and record rollback
            self.snapshot_mgr.cleanup(snapshot)
            tx.state = TransactionState.ROLLED_BACK
            tx.error_message = f"Security authorization failed: {auth_err}"
            tx.completed_at = time.time()
            raise

        # 3. Execute Action
        result = None
        try:
            tx.state = TransactionState.EXECUTING
            result = action_fn()
        except Exception as exec_err:
            # Critical failure during execution -> ROLLBACK immediately
            self.snapshot_mgr.rollback(snapshot)
            tx.state = TransactionState.ROLLED_BACK
            tx.error_message = f"Execution failed, rolled back to snapshot: {exec_err}"
            tx.completed_at = time.time()
            raise

        # 4. Verify Outcome
        # Verify file expectations
        verif_res = self.verifier.verify_file_operation(
            expected=expected_result,
            before_state=None,
            after_state=None,  # Handled directly by file verifier
        )
        tx.verification = verif_res

        if verif_res.outcome == VerificationOutcome.FAILURE:
            # Verification failed -> Rollback
            self.snapshot_mgr.rollback(snapshot)
            tx.state = TransactionState.ROLLED_BACK
            tx.error_message = f"Verification failed ({verif_res.evidence}), rolled back."
            tx.completed_at = time.time()
            return tx, None

        # 5. COMMIT
        self.snapshot_mgr.cleanup(snapshot)
        tx.state = TransactionState.COMMITTED
        tx.completed_at = time.time()
        return tx, result
