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
        Returns a parsed JSON workflow plan with multi-site awareness.
        """
        planner_prompt = f"""You are the Planning Engine of ELLA-WCD, an autonomous browser agent.
Decompose the following user task into a structured, step-by-step browser plan.
- If the user asks to search or compare across multiple ecommerce sites (Amazon, Flipkart, Croma), set is_multi_site to true and category to "ecommerce".
- If the user asks to search, find, or compare across quick commerce / 10-minute grocery brands (e.g. Blinkit/Zomato, Zepto, Swiggy Instamart, Amazon Fresh, Flipkart Minutes) or find cheapest vegetables/groceries like tomatoes, set is_multi_site to true, category to "quick_commerce", and configure the 3 target quick commerce sites (Blinkit, Zepto, Amazon Fresh).
- If the user asks to search, find, or compare clothing, apparel, fashion items or clothes (e.g. hoodie, t-shirt, shirt, jeans, jacket, shoes, dress, saree, kurta, kapde, samaan), set is_multi_site to true, category to "clothing", and configure the 3 target fashion platforms: Flipkart, Amazon, and Myntra.

User Task: "{task_goal}"

Respond ONLY with a valid JSON object matching this schema:
{{
  "understanding": "1 sentence summarizing the goal",
  "is_multi_site": true/false,
  "category": "clothing | quick_commerce | ecommerce | research | general",
  "sites": [
    {{
      "name": "Site name (e.g. Blinkit, Zepto, Swiggy Instamart or Amazon)",
      "url": "https://...",
      "query": "search query"
    }}
  ],
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
  "verification_criteria": "How to verify success (e.g. valid products & prices extracted across sites)",
  "learned_pattern_name": "Short identifier for site memory, e.g. 'qcommerce_tomato_comparison'"
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
                parsed = json.loads(content)
                lower_goal = task_goal.lower()

                # Check if Quick Commerce intent is detected
                qcom_kws = [
                    "quick commerce", "q-commerce", "quick eccoece", "quick ecommerce",
                    "blinkit", "zepto", "instamart", "swiggy", "zomato", "amazon fresh",
                    "bigbasket", "bbnow", "flipkart quick", "flipkart minutes",
                    "tomato", "tomatoes", "onion", "vegetable", "vegetables", "grocery", "groceries", "milk", "sasta"
                ]
                if any(k in lower_goal for k in qcom_kws):
                    parsed["is_multi_site"] = True
                    parsed["category"] = "quick_commerce"
                    if not parsed.get("sites") or len(parsed.get("sites", [])) < 3:
                        t3 = {"name": "Swiggy Instamart", "url": "https://www.swiggy.com/instamart", "query": task_goal} if ("swiggy" in lower_goal or "instamart" in lower_goal) else {"name": "Amazon Fresh", "url": "https://www.amazon.in", "query": task_goal}
                        parsed["sites"] = [
                            {"name": "Blinkit", "url": "https://blinkit.com", "query": task_goal},
                            {"name": "Zepto", "url": "https://www.zeptonow.com", "query": task_goal},
                            t3
                        ]

                # Check Clothing & Fashion intent
                clothing_kws = [
                    "clothing", "clothes", "fashion", "apparel", "kapde", "kapda", "samaan",
                    "tshirt", "t-shirt", "shirt", "shirts", "jeans", "hoodie", "hoodies", "jacket", "jackets",
                    "sweatshirt", "sweatshirts", "kurta", "kurti", "saree", "dress", "dresses",
                    "shoes", "sneakers", "myntra", "zara", "h&m", "trousers", "pants", "trackpants"
                ]
                if any(k in lower_goal for k in clothing_kws) or parsed.get("category") == "clothing":
                    parsed["is_multi_site"] = True
                    parsed["category"] = "clothing"
                    if not parsed.get("sites") or len(parsed.get("sites", [])) < 3:
                        parsed["sites"] = [
                            {"name": "Flipkart", "url": "https://www.flipkart.com", "query": task_goal},
                            {"name": "Amazon", "url": "https://www.amazon.in", "query": task_goal},
                            {"name": "Myntra", "url": "https://www.myntra.com", "query": task_goal}
                        ]

                # Check standard multi-site intent
                elif any(k in lower_goal for k in ["3 ecommerce", "three ecommerce", "across", "compare", "amazon and flipkart", "amazon, flipkart"]):
                    parsed["is_multi_site"] = True
                    if not parsed.get("sites"):
                        parsed["sites"] = [
                            {"name": "Amazon", "url": "https://www.amazon.in", "query": task_goal},
                            {"name": "Flipkart", "url": "https://www.flipkart.com", "query": task_goal},
                            {"name": "Croma", "url": "https://www.croma.com", "query": task_goal}
                        ]
                return parsed
        except Exception as e:
            log.warning(f"Workflow planner JSON parsing failed: {e}")

        # Rule-based fallback plan if LLM parsing fails
        lower_goal = task_goal.lower()
        clothing_kws = [
            "clothing", "clothes", "fashion", "apparel", "kapde", "kapda", "samaan",
            "tshirt", "t-shirt", "shirt", "shirts", "jeans", "hoodie", "hoodies", "jacket", "jackets",
            "sweatshirt", "sweatshirts", "kurta", "kurti", "saree", "dress", "dresses",
            "shoes", "sneakers", "myntra", "zara", "h&m", "trousers", "pants", "trackpants"
        ]
        is_clothing = any(k in lower_goal for k in clothing_kws)

        qcom_kws = [
            "quick commerce", "q-commerce", "quick eccoece", "quick ecommerce",
            "blinkit", "zepto", "instamart", "swiggy", "zomato", "amazon fresh",
            "bigbasket", "bbnow", "flipkart quick", "flipkart minutes",
            "tomato", "tomatoes", "onion", "vegetable", "vegetables", "grocery", "groceries", "milk", "sasta"
        ]
        is_qcom = any(k in lower_goal for k in qcom_kws)
        is_multi = is_clothing or is_qcom or any(k in lower_goal for k in ["3 ecommerce", "three ecommerce", "across", "compare", "ecommerce"])
        
        clean_val = task_goal
        for prefix in [
            "open broswer and find ", "open browser and find ", "open 3 ecommerce website and search for ",
            "open 3 websites and search for ", "find best ", "search for ", "find "
        ]:
            if clean_val.lower().startswith(prefix):
                clean_val = clean_val[len(prefix):]

        sites = []
        category = "general"
        if is_clothing:
            category = "clothing"
            sites = [
                {"name": "Flipkart", "url": "https://www.flipkart.com", "query": clean_val.strip()},
                {"name": "Amazon", "url": "https://www.amazon.in", "query": clean_val.strip()},
                {"name": "Myntra", "url": "https://www.myntra.com", "query": clean_val.strip()}
            ]
            pattern_name = "clothing_fashion_comparison"
            start_url = "https://www.flipkart.com"
        elif is_qcom:
            category = "quick_commerce"
            t3 = {"name": "Swiggy Instamart", "url": "https://www.swiggy.com/instamart", "query": clean_val.strip()} if ("swiggy" in lower_goal or "instamart" in lower_goal) else {"name": "Amazon Fresh", "url": "https://www.amazon.in", "query": clean_val.strip()}
            sites = [
                {"name": "Blinkit", "url": "https://blinkit.com", "query": clean_val.strip()},
                {"name": "Zepto", "url": "https://www.zeptonow.com", "query": clean_val.strip()},
                t3
            ]
            pattern_name = "qcommerce_grocery_comparison"
            start_url = "https://blinkit.com"
        elif is_multi:
            category = "ecommerce"
            sites = [
                {"name": "Amazon", "url": "https://www.amazon.in", "query": clean_val.strip()},
                {"name": "Flipkart", "url": "https://www.flipkart.com", "query": clean_val.strip()},
                {"name": "Croma", "url": "https://www.croma.com", "query": clean_val.strip()}
            ]
            pattern_name = "ecommerce_multi_search"
            start_url = "https://www.amazon.in"
        else:
            pattern_name = "web_search_flow"
            start_url = "https://www.google.com"

        return {
            "understanding": task_goal,
            "is_multi_site": is_multi,
            "category": category,
            "sites": sites,
            "starting_url": start_url,
            "steps": [
                {"step_id": 1, "action": "search", "description": "Search for query across target platforms", "target": "input", "value": clean_val.strip()},
                {"step_id": 2, "action": "extract", "description": "Extract product cards, prices, and pack weights", "target": "product card", "value": ""}
            ],
            "verification_criteria": "Extract at least 3 relevant items and identify cheapest option",
            "learned_pattern_name": pattern_name
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

    def diagnose_and_recover(self, query: str, image_bytes: bytes, domain: str = "") -> Dict[str, Any]:
        """
        Multimodal Obstacle Diagnostician & Recovery Surgeon (Qwen2.5-VL / Qwen3-VL).
        Inspects the screenshot of a blocked browser tab, determines if an obstacle
        (modal dialog, cookie banner, login gate, cloudflare/bot check, or missing search input)
        is preventing interaction/extraction, and provides exact actionable recovery instructions.
        """
        prompt = f"""You are the Emergency Recovery Surgeon of ELLA-WCD, an autonomous browser agent.
The browser was attempting to search/extract information for: "{query}" on domain: "{domain or 'web page'}".
However, the fast code was blocked or extracted 0 results.

Inspect the provided screenshot carefully and diagnose what is blocking the page.
Detect if there is:
- A modal popup, newsletter overlay, or promo banner
- A cookie consent / privacy banner
- A login prompt or sign-in gate
- A bot verification or captcha screen
- An empty search result or incorrect page state
- Obscured or unfocused search bar

Output ONLY a JSON object with this exact schema:
{{
  "has_obstacle": true/false,
  "obstacle_type": "modal_popup | cookie_banner | login_gate | bot_check | empty_results | none",
  "description": "Short explanation of what is on screen blocking progress",
  "recommended_action": "click | dismiss | press_key | reload | wait | none",
  "coordinates": {{"x": 800, "y": 200}},
  "selector": "button.close, [aria-label='Close'], etc.",
  "key": "Escape",
  "confidence": 0.95
}}
If no obstacle is visible and the page simply has no products, set "has_obstacle": false and "recommended_action": "none".
Output JSON only with no markdown formatting.
"""
        user_msg = {
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(image_bytes).decode("utf-8")]
        }

        payload = {
            "model": self.active_model,
            "messages": [
                {"role": "system", "content": "You are a precise multimodal browser automation diagnostic engine. Always output valid JSON."},
                user_msg
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 300}
        }

        try:
            res = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=45)
            if res.status_code == 200:
                text = res.json().get("message", {}).get("content", "").strip()
                if "```" in text:
                    text = text.split("```json")[-1].split("```")[0].strip()
                parsed = json.loads(text)
                return parsed
        except Exception as e:
            log.error(f"Visual obstacle diagnosis error: {e}")

        # Safe fallback
        return {
            "has_obstacle": False,
            "obstacle_type": "unknown",
            "description": "Automated vision inspection completed without high confidence obstacle",
            "recommended_action": "press_key",
            "key": "Escape",
            "confidence": 0.5
        }
