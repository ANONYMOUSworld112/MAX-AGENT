"""Laya Local System 1 Reflex Engine.

Provides sub-50ms non-autoregressive decision making:
- Lane routing (Lane A fast voice stream vs Lane B background queue)
- Risk scoring & guardrailing (Is input dangerous/destructive?)
- Priority band assignment (Bands 0 to 4)
- Agent cluster and specialist selection

Uses laya.Router when checkpoints are present, with deterministic fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("max.reflex.laya_engine")


class LayaReflexEngine:
    def __init__(self, fallback_mode: bool = False) -> None:
        self.fallback_mode = fallback_mode
        self._router = None

        if not fallback_mode:
            # Fast deterministic reflex by default; enable LAYA_ONLINE=1 to connect to neural weights
            if os.environ.get("LAYA_ONLINE", "0") != "1":
                self.fallback_mode = True
            else:
                try:
                    try:
                        import laya  # type: ignore[import-not-found]
                    except ImportError:
                        import sys
                        from pathlib import Path
                        _temp_laya = Path(__file__).resolve().parent.parent.parent / "temp_laya"
                        if _temp_laya.exists() and str(_temp_laya) not in sys.path:
                            sys.path.insert(0, str(_temp_laya))
                        import laya  # type: ignore[import-not-found]

                    # Initialize Router without blocking full preloads immediately
                    self._router = laya.Router(preload=False)
                    logger.info("Laya Router initialized successfully.")
                except Exception as exc:
                    logger.warning("Could not initialize native Laya Router (%s), using fallback mode.", exc)
                    self.fallback_mode = True

    def decide(self, state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates arbitrary typed questions against state string."""
        if not self.fallback_mode and self._router is not None:
            try:
                res = self._router.predict(state, questions)
                return res.get("answers", {})
            except Exception as exc:
                logger.warning("Laya router prediction failed, falling back: %s", exc)

        # Deterministic fallback implementation
        answers: Dict[str, Any] = {}
        for q_name, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            if q_type == "choice":
                opts = list(q_spec.get("criteria", {}).keys())
                # Keyword matching heuristic
                chosen = opts[0] if opts else "default"
                state_lower = state.lower()
                for opt in opts:
                    if opt.lower() in state_lower:
                        chosen = opt
                        break
                answers[q_name] = {"choice": chosen, "confidence": 0.85}
            elif q_type == "score":
                crit = q_spec.get("criteria", ["low", "medium", "high"])
                chosen = crit[-1] if ("urgent" in state.lower() or "critical" in state.lower()) else crit[0]
                answers[q_name] = {"score": chosen, "confidence": 0.88}
            elif q_type in ("noul", "bool"):
                is_flagged = any(k in state.lower() for k in ["rm -rf", "delete", "format", "kill", "drop table", "shutdown"])
                answers[q_name] = {"noul": 0.95 if is_flagged else 0.05, "confidence": 0.90}
        return answers

    def classify_choice(
        self,
        state: str,
        question: str,
        options: Dict[str, str],
    ) -> Tuple[str, float]:
        """Typed choice decision between key/description pairs."""
        questions = {
            "decision": {
                "type": "choice",
                "instructions": question,
                "criteria": options,
            }
        }
        res = self.decide(state, questions)
        ans = res.get("decision", {})
        return ans.get("choice", list(options.keys())[0]), float(ans.get("confidence", 0.75))

    def score_urgency(
        self,
        state: str,
        criteria: List[str],
    ) -> Tuple[str, float]:
        """Typed score decision across an ordered scale."""
        questions = {
            "urgency": {
                "type": "score",
                "instructions": "Determine priority/urgency",
                "criteria": criteria,
            }
        }
        res = self.decide(state, questions)
        ans = res.get("urgency", {})
        return ans.get("score", criteria[0]), float(ans.get("confidence", 0.75))

    def evaluate_bool(self, state: str, instruction: str) -> float:
        """Returns calibrated probability (0.0 to 1.0) for a yes/no statement."""
        questions = {
            "check": {
                "type": "noul",
                "instructions": instruction,
            }
        }
        res = self.decide(state, questions)
        ans = res.get("check", {})
        return float(ans.get("noul", 0.0))
