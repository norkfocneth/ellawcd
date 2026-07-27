# ──────────────────────────────────────────────
# Project Ella v1.0 — Gemma Brain
# Ollama HTTP client for Gemma4:e4b (GPU-first)
# ──────────────────────────────────────────────

import requests
import time
import json
from typing import Generator

from config import OLLAMA_BASE_URL, MODEL_NAME, GENERATION_CONFIG, KEEP_ALIVE
from logger import get_logger
from events import event_bus, Event


log = get_logger("brain.gemma")


class GemmaBrain:
    """
    Ella's brain — powered by Gemma via Ollama.
    
    Communicates with the local Ollama server over HTTP.
    All inference runs on GPU (num_gpu = -1 in config).
    
    Usage:
        brain = GemmaBrain()
        
        if brain.is_available():
            response = brain.chat("Hello, how are you?")
            print(response)
    """

    def __init__(self, system_prompt: str = None):
        """
        Initialize the Gemma brain.
        
        Args:
            system_prompt: The system prompt defining Ella's personality.
                          If None, uses default from prompts.py
        """
        self.base_url = OLLAMA_BASE_URL
        self.model = MODEL_NAME
        self.generation_config = GENERATION_CONFIG.copy()
        
        # Import system prompt
        if system_prompt is None:
            from brain.prompts import SYSTEM_PROMPT
            self.system_prompt = SYSTEM_PROMPT
        else:
            self.system_prompt = system_prompt
        
        # Conversation history for context
        self.messages: list[dict] = []
        
        # Add system prompt as first message
        self._init_conversation()
        
        log.info(f"GemmaBrain initialized — model: {self.model}")

    def _init_conversation(self) -> None:
        """Initialize conversation with system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    def is_available(self) -> bool:
        """
        Check if Ollama server is running and model is available.
        
        Returns:
            True if Ollama is reachable and model is loaded
        """
        try:
            # Check Ollama server
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                log.error(f"Ollama server returned status {response.status_code}")
                return False
            
            # Check if our model is available
            data = response.json()
            available_models = [m["name"] for m in data.get("models", [])]
            
            # Check for exact match or partial match (e.g., "gemma3:4b" matches "gemma3:4b")
            model_found = any(
                self.model in model_name or model_name.startswith(self.model.split(":")[0])
                for model_name in available_models
            )
            
            if not model_found:
                log.warning(f"Model '{self.model}' not found. Available: {available_models}")
                log.warning(f"Run: ollama pull {self.model}")
                return False
            
            log.info(f"Ollama connected — model '{self.model}' available")
            return True
            
        except requests.ConnectionError:
            log.error("Ollama server not running. Start with: ollama serve")
            return False
        except Exception as e:
            log.error(f"Error checking Ollama: {e}")
            return False

    def warmup(self) -> bool:
        """
        Pre-load model into GPU VRAM during boot sequence.
        
        This prevents any first-prompt latency delay by forcing
        Ollama to lock all model weights in VRAM before user chat starts.
        """
        try:
            log.info("Warming up Gemma GPU VRAM pipeline...")
            requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": self.generation_config,
                },
                timeout=30,
            )
            log.info("Gemma GPU VRAM pre-loaded and pinned successfully!")
            return True
        except Exception as e:
            log.warning(f"Warmup warning: {e}")
            return False

    def chat(self, user_message: str) -> str:

        """
        Send a message and get a response from Gemma.
        
        This maintains conversation context — previous messages
        are included for multi-turn chat.
        
        Args:
            user_message: The user's text input
            
        Returns:
            Ella's response text
        """
        start_time = time.time()
        
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})
        
        try:
            # Call Ollama chat API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": self.generation_config,
                },
                timeout=120,
            )

            response.raise_for_status()
            
            data = response.json()
            assistant_message = data.get("message", {}).get("content", "").strip()
            
            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": assistant_message})
            
            # Calculate metrics
            elapsed_ms = (time.time() - start_time) * 1000
            tokens_used = data.get("eval_count", 0)
            
            log.info(f"Response — {tokens_used} tokens, {elapsed_ms:.0f}ms")
            
            # Emit event
            event_bus.emit(Event(
                name="BrainResponseReady",
                source="brain.gemma",
                data={
                    "response": assistant_message,
                    "tokens_used": tokens_used,
                    "latency_ms": round(elapsed_ms),
                    "model": self.model,
                }
            ))
            
            return assistant_message
            
        except requests.ConnectionError:
            error_msg = "Ollama server se connect nahi ho paya. Kya Ollama chal raha hai?"
            log.error(error_msg)
            event_bus.emit(Event(
                name="ErrorOccurred",
                source="brain.gemma",
                data={"error": "ConnectionError", "message": error_msg}
            ))
            return error_msg
            
        except requests.Timeout:
            error_msg = "Response me bahut time lag raha hai. Model too large ho sakta hai."
            log.error(error_msg)
            return error_msg
            
        except Exception as e:
            error_msg = f"Brain error: {str(e)}"
            log.error(error_msg)
            event_bus.emit(Event(
                name="ErrorOccurred",
                source="brain.gemma",
                data={"error": type(e).__name__, "message": str(e)}
            ))
            return f"Sorry, kuch gadbad ho gayi: {str(e)}"

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Stream response from Gemma token by token.
        
        Yields each chunk of text as it arrives.
        Useful for real-time display in terminal.
        
        Args:
            user_message: The user's text input
            
        Yields:
            Text chunks as they arrive from the model
        """
        start_time = time.time()
        
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})
        
        full_response = ""
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "stream": True,
                    "keep_alive": KEEP_ALIVE,
                    "options": self.generation_config,
                },
                stream=True,
                timeout=120,
            )

            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    chunk_data = json.loads(line)
                    
                    if chunk_data.get("done", False):
                        # Final chunk — contains metadata
                        tokens_used = chunk_data.get("eval_count", 0)
                        elapsed_ms = (time.time() - start_time) * 1000
                        log.info(f"Stream complete — {tokens_used} tokens, {elapsed_ms:.0f}ms")
                        break
                    
                    # Extract text chunk
                    chunk_text = chunk_data.get("message", {}).get("content", "")
                    if chunk_text:
                        full_response += chunk_text
                        yield chunk_text
            
            # Add full response to history
            self.messages.append({"role": "assistant", "content": full_response})
            
            # Emit event
            event_bus.emit(Event(
                name="BrainResponseReady",
                source="brain.gemma",
                data={
                    "response": full_response,
                    "streamed": True,
                    "model": self.model,
                }
            ))
            
        except Exception as e:
            log.error(f"Stream error: {e}")
            yield f"\n[Error: {str(e)}]"

    def reset_conversation(self) -> None:
        """Clear conversation history and start fresh."""
        self._init_conversation()
        log.info("Conversation history cleared")

    def get_conversation_length(self) -> int:
        """Get number of messages in current conversation (excluding system prompt)."""
        return len(self.messages) - 1  # Exclude system prompt

    def trim_conversation(self, keep_last: int = 20) -> None:
        """
        Trim conversation history to keep it within context window.
        Keeps the system prompt + last N messages.
        
        Args:
            keep_last: Number of recent messages to keep
        """
        if len(self.messages) > keep_last + 1:
            system_msg = self.messages[0]
            recent_msgs = self.messages[-(keep_last):]
            self.messages = [system_msg] + recent_msgs
            log.info(f"Conversation trimmed to {keep_last} messages")
