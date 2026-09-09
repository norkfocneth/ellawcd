# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — Qwen Brain (Multimodal LLM)
# Ollama client supporting Qwen3-VL (text + vision)
# ──────────────────────────────────────────────

import json
import base64
import requests
import time
from typing import Generator, Optional, List, Dict, Any
from pathlib import Path

from config import OLLAMA_BASE_URL, MODEL_NAME, GENERATION_CONFIG, KEEP_ALIVE
from logger import get_logger

log = get_logger("brain.qwen")

# Priority list of models to try
MODEL_PREFERENCES = [
    "qwen2.5vl:7b",
    "qwen3-vl:8b-instruct",
    "qwen3-vl:8b",
    "qwen2.5-vl:7b",
    "qwen2.5vl:3b",
]


class QwenBrain:
    """
    ELLA-WCD Brain powered by Qwen3-VL via Ollama.
    Supports natural language planning, structured tool calling,
    and multimodal vision reasoning.
    """

    def __init__(self, system_prompt: Optional[str] = None):
        self.base_url = OLLAMA_BASE_URL
        self.preferred_model = MODEL_NAME
        self.active_model = self._select_available_model()
        self.generation_config = GENERATION_CONFIG.copy()

        if system_prompt is None:
            from brain.prompts import SYSTEM_PROMPT
            self.system_prompt = SYSTEM_PROMPT
        else:
            self.system_prompt = system_prompt

        self.messages: List[Dict[str, Any]] = []
        self._init_conversation()
        log.info(f"QwenBrain initialized with active model: {self.active_model}")

    def _select_available_model(self) -> str:
        """Query Ollama and select the best available model."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=4)
            if res.status_code == 200:
                available = [m["name"] for m in res.json().get("models", [])]
                log.info(f"Available Ollama models: {available}")

                # 1. Exact match on configured model
                for m in available:
                    if m == self.preferred_model or m.startswith(self.preferred_model):
                        return m

                # 2. Preference order fallback
                for pref in MODEL_PREFERENCES:
                    for m in available:
                        if m == pref or m.startswith(pref.split(":")[0]):
                            log.warning(f"Preferred model '{self.preferred_model}' not found, falling back to '{m}'")
                            return m

                # 3. Any available model
                if available:
                    log.warning(f"Using first available model: {available[0]}")
                    return available[0]
        except Exception as e:
            log.warning(f"Failed to query Ollama models: {e}")

        return self.preferred_model

    def _init_conversation(self) -> None:
        """Initialize or reset conversation history with system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    def reset(self) -> None:
        """Reset conversation context."""
        self._init_conversation()
        log.info("Conversation reset.")

    def is_available(self) -> bool:
        """Check if Ollama server is up and responding."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def chat(self, prompt: str, image_bytes: Optional[bytes] = None) -> str:
        """
        Send user message (with optional image) and get complete response.
        """
        user_msg: Dict[str, Any] = {"role": "user", "content": prompt}
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            user_msg["images"] = [b64_img]

        self.messages.append(user_msg)

        payload = {
            "model": self.active_model,
            "messages": self.messages,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": self.generation_config,
        }

        try:
            log.debug(f"Calling Ollama chat with model {self.active_model}")
            res = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
            if res.status_code != 200:
                log.error(f"Ollama chat error {res.status_code}: {res.text}")
                return f"Brain error: HTTP {res.status_code}"

            data = res.json()
            assistant_reply = data.get("message", {}).get("content", "").strip()
            self.messages.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply

        except requests.Timeout:
            log.error("Ollama request timed out.")
            return "Error: Brain response timed out."
        except Exception as e:
            log.error(f"Ollama call failed: {e}")
            return f"Error: {e}"

    def plan_workflow(self, task_goal: str) -> Dict[str, Any]:
        """
        Decompose a user request into a structured browser workflow.
        Returns a parsed JSON workflow plan.
        """
        planner_prompt = f"""You are the Planning Engine of ELLA-WCD, an autonomous browser agent.
Decompose the following user task into a structured, step-by-step browser plan.

User Task: "{task_goal}"

Respond ONLY with a valid JSON object matching this schema:
{{
  "understanding": "1 sentence summarizing the goal",
  "starting_url": "https://...",
  "steps": [
    {{
      "step_id": 1,
      "action": "navigate | search | click | fill | extract",
      "description": "What this step does",
      "target": "URL, search input, or button",
      "value": "Optional text to search or type"
    }}
  ],
  "verification_criteria": "How to verify success (e.g. 5 non-empty results extracted)",
  "learned_pattern_name": "Short identifier for site memory, e.g. 'arxiv_paper_search'"
}}

Do NOT include any markdown formatting around the JSON if possible, just the raw JSON object.
"""
        payload = {
            "model": self.active_model,
            "messages": [
                {"role": "system", "content": "You are a specialized browser automation planner. Always output valid JSON only."},
                {"role": "user", "content": planner_prompt}
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024}
        }

        try:
            res = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=90)
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content", "").strip()
                if "```" in content:
                    content = content.split("```json")[-1].split("```")[0].strip()
                return json.loads(content)
        except Exception as e:
            log.warning(f"Workflow planner JSON parsing failed: {e}")

        # Rule-based fallback plan if LLM parsing fails
        clean_val = task_goal
        for prefix in ["open 3 ecommerce website and search for ", "open 3 websites and search for ", "search for ", "find "]:
            if clean_val.lower().startswith(prefix):
                clean_val = clean_val[len(prefix):]
        return {
            "understanding": task_goal,
            "starting_url": "https://duckduckgo.com",
            "steps": [
                {"step_id": 1, "action": "search", "description": "Search for query", "target": "input[name='q']", "value": clean_val.strip()},
                {"step_id": 2, "action": "extract", "description": "Extract top results", "target": "article, .result", "value": ""}
            ],
            "verification_criteria": "Extract at least 3 relevant items",
            "learned_pattern_name": "web_search_flow"
        }

    def vision_localize(self, query: str, image_bytes: bytes) -> Dict[str, Any]:
        """
        Multimodal visual element localization when DOM selectors fail.
        Qwen3-VL inspects the screenshot and identifies element coordinates or selector cues.
        """
        prompt = f"""Inspect this screenshot. Locate the following UI element: "{query}".
Return a JSON object with:
{{
  "found": true/false,
  "description": "where it is located on screen",
  "coordinates": {{"x": 100, "y": 200}} (normalized or estimated pixels),
  "suggested_selector": "CSS selector or text hint"
}}
Output JSON only.
"""
        user_msg = {
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(image_bytes).decode("utf-8")]
        }

        payload = {
            "model": self.active_model,
            "messages": [user_msg],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 256}
        }

        try:
            res = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=40)
            if res.status_code == 200:
                text = res.json().get("message", {}).get("content", "").strip()
                if "```" in text:
                    text = text.split("```json")[-1].split("```")[0].strip()
                return json.loads(text)
        except Exception as e:
            log.error(f"Vision localization error: {e}")

        return {"found": False, "error": "Visual localization unavailable"}
