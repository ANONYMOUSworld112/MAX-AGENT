"""
MAX OS — Universal LLM Computer-Use Engine (Section 9 & NeuralAgent / Ace Integration).
Multi-provider Vision-Language Model (VLM) & reasoning client.
Supports:
  - Google Gemini (gemini-2.0-flash, gemini-1.5-pro)
  - OpenAI (gpt-4o, gpt-4o-mini with vision & computer use)
  - Anthropic (claude-3-5-sonnet, claude-3-7-sonnet computer-use)
  - Local Ollama (llama3.2-vision, qwen2-vl)
  - Deterministic high-speed fallback synthesis
"""

from __future__ import annotations

import base64
import enum
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.command_model import ActionObject, TaskPlan
from core.data_boundary import sanitize_payload
from core.kill_switch import get_kill_switch, require_armed
from core.security.security_gate import RiskTier, SecurityGate


class LLMProvider(str, enum.Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AUTO = "auto"
    MOCK = "mock"


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.AUTO
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Automatically discovers active LLM provider from environment variables."""
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return cls(
                provider=LLMProvider.GEMINI,
                api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
                model_name=os.environ.get("MAX_LLM_MODEL", "gemini-2.0-flash"),
            )
        elif os.environ.get("OPENAI_API_KEY"):
            return cls(
                provider=LLMProvider.OPENAI,
                api_key=os.environ.get("OPENAI_API_KEY"),
                model_name=os.environ.get("MAX_LLM_MODEL", "gpt-4o"),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
        elif os.environ.get("ANTHROPIC_API_KEY"):
            return cls(
                provider=LLMProvider.ANTHROPIC,
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                model_name=os.environ.get("MAX_LLM_MODEL", "claude-3-7-sonnet-20250219"),
            )
        elif os.environ.get("OLLAMA_BASE_URL") or os.environ.get("USE_OLLAMA") == "1":
            return cls(
                provider=LLMProvider.OLLAMA,
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                model_name=os.environ.get("MAX_LLM_MODEL", "llama3.2-vision"),
            )
        return cls(provider=LLMProvider.AUTO)


@dataclass
class ComputerUseObservation:
    active_window: str = ""
    visible_windows: List[str] = field(default_factory=list)
    uia_elements: List[Dict[str, Any]] = field(default_factory=list)
    screenshot_b64: Optional[str] = None
    screen_width: int = 1920
    screen_height: int = 1080
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LLMPlanProposal:
    thought: str
    actions: List[ActionObject]
    confidence: float = 1.0
    referential_entities: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    provider_used: str = ""
    model_used: str = ""


SYSTEM_COMPUTER_USE_PROMPT = """You are MAX OS (J.A.R.V.I.S.) Computer Use Operator.
Your job is to analyze user goals and current screen observations, then output an ordered list of semantic UI actions to execute.

You must reply with ONLY a valid JSON object matching this schema:
{
  "thought": "brief explanation of reasoning and what you observe on screen",
  "confidence": 0.95,
  "entities": {"entity_name": "extracted_value"},
  "actions": [
    {
      "type": "open_application | navigate | click | type_text | keypress | scroll | observe | speak | wait",
      "target": "target identifier or app name",
      "value": "text to type or parameter value",
      "semantic_target": "human name of element e.g. 'Search Button'",
      "expected_result": {"description": "what should appear after action"}
    }
  ]
}

Rules:
1. Output semantic actions, not hardcoded pixel coordinates.
2. If computing or calculating, include typing the formula and observing the result.
3. For destructive actions (delete, send, pay, format), state clear expectations.
"""


class LLMComputerUseEngine:
    """
    Multi-Provider LLM Computer-Use Planning and Reasoning Engine.
    Converts goals and visual UI state into structured semantic ActionObjects.
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        security_gate: Optional[SecurityGate] = None,
        custom_caller: Optional[Callable[[str, ComputerUseObservation], str]] = None,
    ):
        self.config = config or LLMConfig.from_env()
        self.security_gate = security_gate or SecurityGate()
        self.custom_caller = custom_caller

    def set_api_key(self, api_key: str, provider: LLMProvider = LLMProvider.AUTO, model_name: Optional[str] = None) -> None:
        """Configures or updates the active LLM API key."""
        self.config.api_key = api_key
        if provider != LLMProvider.AUTO:
            self.config.provider = provider
        if model_name:
            self.config.model_name = model_name

    def get_active_provider(self) -> LLMProvider:
        """Determines the active provider based on configuration and available keys."""
        if self.config.provider != LLMProvider.AUTO:
            return self.config.provider

        if self.config.api_key:
            if self.config.api_key.startswith("AIza"):
                return LLMProvider.GEMINI
            elif self.config.api_key.startswith("sk-ant-"):
                return LLMProvider.ANTHROPIC
            elif self.config.api_key.startswith("sk-"):
                return LLMProvider.OPENAI

        env_cfg = LLMConfig.from_env()
        if env_cfg.provider != LLMProvider.AUTO:
            return env_cfg.provider

        return LLMProvider.MOCK

    def propose_actions_for_goal(
        self,
        goal: str,
        observation: ComputerUseObservation,
        working_memory: Optional[Dict[str, Any]] = None,
    ) -> LLMPlanProposal:
        """
        Queries the configured LLM with current screen observation and produces a structured LLMPlanProposal.
        """
        require_armed(get_kill_switch())
        provider = self.get_active_provider()
        memory = working_memory or {}

        # If custom caller provided (e.g. for unit testing or custom pipeline)
        if self.custom_caller:
            raw = self.custom_caller(goal, observation)
            return self._parse_llm_json_response(raw, goal, str(provider.value), "custom")

        # 1. Google Gemini
        if provider == LLMProvider.GEMINI and self.config.api_key:
            try:
                raw = self._call_gemini(goal, observation, memory)
                return self._parse_llm_json_response(raw, goal, "gemini", self.config.model_name or "gemini-2.0-flash")
            except Exception as e:
                # Fall back gracefully to structured synthesis
                pass

        # 2. OpenAI
        elif provider == LLMProvider.OPENAI and self.config.api_key:
            try:
                raw = self._call_openai(goal, observation, memory)
                return self._parse_llm_json_response(raw, goal, "openai", self.config.model_name or "gpt-4o")
            except Exception as e:
                pass

        # 3. Anthropic
        elif provider == LLMProvider.ANTHROPIC and self.config.api_key:
            try:
                raw = self._call_anthropic(goal, observation, memory)
                return self._parse_llm_json_response(raw, goal, "anthropic", self.config.model_name or "claude-3-7-sonnet")
            except Exception as e:
                pass

        # 4. Ollama
        elif provider == LLMProvider.OLLAMA:
            try:
                raw = self._call_ollama(goal, observation, memory)
                return self._parse_llm_json_response(raw, goal, "ollama", self.config.model_name or "llama3.2-vision")
            except Exception as e:
                pass

        # 5. Deterministic fallback synthesis
        return self._synthesize_fallback_proposal(goal, observation, memory)

    def _call_gemini(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> str:
        """Invokes Google Gemini REST API."""
        model = self.config.model_name or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.config.api_key}"
        
        prompt_text = self._build_prompt(goal, obs, memory)
        sanitized_prompt = sanitize_payload({"prompt": prompt_text})["prompt"]

        contents = [{"parts": [{"text": sanitized_prompt}]}]
        if obs.screenshot_b64:
            contents[0]["parts"].append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": obs.screenshot_b64
                }
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "responseMimeType": "application/json",
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> str:
        """Invokes OpenAI Chat Completions API."""
        model = self.config.model_name or "gpt-4o"
        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"

        prompt_text = self._build_prompt(goal, obs, memory)
        sanitized_prompt = sanitize_payload({"prompt": prompt_text})["prompt"]

        messages = [
            {"role": "system", "content": SYSTEM_COMPUTER_USE_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": sanitized_prompt}]}
        ]

        if obs.screenshot_b64:
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{obs.screenshot_b64}"}
            })

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> str:
        """Invokes Anthropic Messages API."""
        model = self.config.model_name or "claude-3-7-sonnet-20250219"
        url = "https://api.anthropic.com/v1/messages"

        prompt_text = self._build_prompt(goal, obs, memory)
        sanitized_prompt = sanitize_payload({"prompt": prompt_text})["prompt"]

        content: List[Dict[str, Any]] = [{"type": "text", "text": sanitized_prompt}]
        if obs.screenshot_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": obs.screenshot_b64
                }
            })

        payload = {
            "model": model,
            "system": SYSTEM_COMPUTER_USE_PROMPT,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.config.api_key or "",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    def _call_ollama(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> str:
        """Invokes local Ollama VLM instance."""
        model = self.config.model_name or "llama3.2-vision"
        base_url = self.config.base_url or "http://localhost:11434"
        url = f"{base_url.rstrip('/')}/api/generate"

        prompt_text = self._build_prompt(goal, obs, memory)
        sanitized_prompt = sanitize_payload({"prompt": prompt_text})["prompt"]

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": f"{SYSTEM_COMPUTER_USE_PROMPT}\n\n{sanitized_prompt}",
            "stream": False,
            "format": "json",
            "options": {"temperature": self.config.temperature},
        }
        if obs.screenshot_b64:
            payload["images"] = [obs.screenshot_b64]

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")

    def _build_prompt(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> str:
        """Constructs rich contextual prompt with active window and UI accessibility tree."""
        elements_summary = []
        for el in obs.uia_elements[:25]:
            name = el.get("name") or el.get("text") or el.get("automation_id", "")
            role = el.get("role") or el.get("control_type", "")
            if name or role:
                elements_summary.append(f"- [{role}] '{name}'")

        elements_block = "\n".join(elements_summary) if elements_summary else "No accessibility elements detected."

        return f"""User Goal: {goal}

Current Screen State:
- Active Window: {obs.active_window or 'Unknown'}
- Visible Windows: {', '.join(obs.visible_windows) if obs.visible_windows else 'None'}
- Screen Size: {obs.screen_width}x{obs.screen_height}
- Working Memory / Referents: {json.dumps(memory)}

Visible UI Elements:
{elements_block}

Recent Actions Taken:
{json.dumps(obs.recent_actions[-3:]) if obs.recent_actions else 'None'}

Propose the optimal next sequence of semantic actions to fulfill the user's goal.
"""

    def _parse_llm_json_response(self, raw_text: str, goal: str, provider: str, model: str) -> LLMPlanProposal:
        """Parses and validates LLM JSON response into ActionObjects."""
        try:
            clean = raw_text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean)
            thought = parsed.get("thought", "LLM computer use plan synthesized.")
            confidence = float(parsed.get("confidence", 0.9))
            entities = parsed.get("entities", {})

            actions: List[ActionObject] = []
            for item in parsed.get("actions", []):
                act_type = str(item.get("type", "observe")).lower()
                target = str(item.get("target", ""))
                value = item.get("value")
                semantic_target = item.get("semantic_target")
                expected = item.get("expected_result", {})

                eval_res = self.security_gate.classify_action_risk(act_type, target, {"value": value})
                actions.append(
                    ActionObject(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        type=act_type,
                        target=target,
                        value=str(value) if value is not None else None,
                        semantic_target=str(semantic_target) if semantic_target else None,
                        risk_tier=eval_res.risk_tier,
                        expected_result=expected,
                        payload={"value": value},
                    )
                )

            if not actions:
                actions.append(
                    ActionObject(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        type="observe",
                        target="screen",
                        risk_tier=RiskTier.TIER_0,
                        expected_result={"verification": "screen_state"},
                    )
                )

            return LLMPlanProposal(
                thought=thought,
                actions=actions,
                confidence=confidence,
                referential_entities=entities,
                raw_response=raw_text,
                provider_used=provider,
                model_used=model,
            )
        except Exception:
            return self._synthesize_fallback_proposal(goal, ComputerUseObservation(), {})

    def _synthesize_fallback_proposal(self, goal: str, obs: ComputerUseObservation, memory: Dict[str, Any]) -> LLMPlanProposal:
        """High-speed deterministic plan synthesis when LLM is offline or unconfigured."""
        goal_lower = goal.lower().strip()
        actions: List[ActionObject] = []
        thought = f"Synthesizing high-speed deterministic plan for: '{goal}'"

        # Math / Calculator
        if any(w in goal_lower for w in ("calculate", "compute", "calculator", "times", "*", "+", "-", "/")):
            math_match = re.search(r"(\d+\s*[\*\+\-\/x]\s*\d+)", goal_lower.replace("times", "*").replace("plus", "+").replace("minus", "-").replace("divided by", "/"))
            if math_match:
                expr = math_match.group(1).replace("x", "*")
                try:
                    res = eval(expr, {"__builtins__": None}, {})
                    res_str = f"{res:,}"
                except Exception:
                    res_str = "result"

                actions.extend([
                    ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="open_application", target="calculator", expected_result={"window_title": "Calculator"}),
                    ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="observe", target="active_window", expected_result={"window_title": "Calculator"}),
                    ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="type_text", target="calculator", value=f"{expr.replace(' ', '')}=", expected_result={"text": res_str}),
                    ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="observe", target="active_window", expected_result={"verification_required": "calculator_result"}),
                    ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="speak", target="tts", value=f"The result is {res_str}, Sir.", expected_result={}),
                ])
                return LLMPlanProposal(thought=thought, actions=actions, confidence=0.98, provider_used="deterministic", model_used="builtin")

        # Application Launch
        if any(goal_lower.startswith(w) for w in ("open", "launch", "start", "run")):
            match = re.search(r"(?:open|launch|start|run)\s+([a-zA-Z0-9_\-\.]+)", goal_lower)
            app = match.group(1) if match else "notepad"
            actions.extend([
                ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="open_application", target=app, expected_result={"window_title": app}),
                ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="observe", target="active_window", expected_result={"window_title": app}),
            ])
            return LLMPlanProposal(thought=thought, actions=actions, confidence=0.95, provider_used="deterministic", model_used="builtin")

        # Web search / Airbnb / Booking / Research flow (like the Ace demo)
        if any(w in goal_lower for w in ("airbnb", "hotel", "flight", "search", "browse", "find")):
            actions.extend([
                ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="open_application", target="msedge.exe", expected_result={"window_title": "Edge"}),
                ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="navigate", target=f"https://www.google.com/search?q={urllib.parse.quote_plus(goal)}", expected_result={"url": "google.com"}),
                ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="observe", target="active_window", expected_result={"verification_required": "search_results"}),
            ])
            return LLMPlanProposal(thought=thought, actions=actions, confidence=0.90, provider_used="deterministic", model_used="builtin")

        # Default observe and execute
        actions.append(ActionObject(action_id=f"act_{uuid.uuid4().hex[:6]}", type="observe", target="active_window", expected_result={}))
        return LLMPlanProposal(thought=thought, actions=actions, confidence=0.80, provider_used="deterministic", model_used="builtin")
