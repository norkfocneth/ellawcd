# 🏛️ ARCHITECTURE.md — Project Ella v1.0

> **Ella = Personal AI Operating System for Windows**
> This document is the engineering blueprint. Every module, interface, communication pattern, and design decision is defined here.

---

## 1. Core Design Principles

| Principle | Description |
|---|---|
| **Offline-First** | Everything runs locally. No cloud dependency. No data leaves the machine. |
| **GPU-First** | Gemma4:e4b runs on GPU from day 1. CPU is fallback only. |
| **Event-Driven** | Every action emits events. Modules communicate via an Event Bus. |
| **Plugin-Ready** | Tools and Skills are registered dynamically. Adding new ones requires zero core changes. |
| **Verify Everything** | Every executed action is verified before proceeding. Retry or fallback on failure. |
| **Permission-Gated** | Dangerous operations require explicit user confirmation. |
| **Context-Aware** | Ella understands "ye", "is", "wo" by maintaining a rolling context window. |
| **Speaker-Locked** | Ella wakes ONLY on the owner's voice saying "Ella". Other voices/sounds are ignored. |

---

## 2. Module Responsibility Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        ELLA CORE                                │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Conversation │  │   Session    │  │   Context Window      │  │
│  │   Manager    │  │   Manager    │  │     Manager           │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                      │              │
│  ┌──────▼─────────────────▼──────────────────────▼───────────┐  │
│  │                    EVENT BUS                              │  │
│  └──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┘  │
│         │      │      │      │      │      │      │             │
│  ┌──────▼──┐ ┌─▼────┐ │  ┌───▼──┐ ┌─▼────┐ │  ┌──▼───────┐    │
│  │  Brain  │ │ STT  │ │  │Planner│ │Memory│ │  │Permission│    │
│  │ (Gemma) │ │Engine│ │  │Engine│ │Engine│ │  │ System   │    │
│  └─────────┘ └──────┘ │  └──────┘ └──────┘ │  └──────────┘    │
│                   ┌────▼────┐          ┌────▼────┐              │
│                   │  TTS    │          │ Vision  │              │
│                   │ Engine  │          │ Engine  │              │
│                   └─────────┘          └─────────┘              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   TOOL REGISTRY                          │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │Chrome  │ │Files   │ │VSCode  │ │Windows │ │Terminal│ │   │
│  │  │Browser │ │PDF     │ │Git     │ │Spotify │ │Search  │ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   SKILLS ENGINE                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐ │   │
│  │  │Developer │ │Student   │ │Productivity│ │Entertainment││   │
│  │  │Skill     │ │Skill     │ │Skill      │ │Skill       ││   │
│  │  └──────────┘ └──────────┘ └───────────┘ └────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               AUTOMATION LAYER                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │PyAutoGUI │ │PyWinAuto │ │Playwright│ │  Mouse/KB  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

| Module | File | Responsibility |
|---|---|---|
| **Conversation Manager** | `conversation.py` | Manages chat loop, message history, routes user input to Brain |
| **Session Manager** | `session.py` | Controls lifecycle: boot → active → sleep → wake → exit. Only wakes on owner voice + "Ella" |
| **Context Window Manager** | `context.py` | Resolves pronouns ("ye", "is", "wo") by tracking last file, screenshot, folder, window |
| **Event Bus** | `events.py` | Central pub/sub system. All modules emit and listen to events |
| **Brain (Gemma)** | `brain/gemma.py` | LLM inference via Ollama. GPU-accelerated Gemma4:e4b |
| **Intent Parser** | `brain/intent_parser.py` | Extracts structured intent + tool + params from LLM output |
| **Planner Engine** | `planner.py` | Decomposes complex requests into ordered sub-tasks |
| **Executor** | `executor.py` | Runs each planned step via Tool Dispatcher |
| **Verifier** | `verifier.py` | Confirms each step succeeded. Triggers retry/fallback if not |
| **Memory Engine** | `memory.py` | Hybrid storage: SQLite now, Vector-ready interface for future |
| **Permission System** | `permissions.py` | Gates actions by Safe/Sensitive/Critical levels |
| **Tool Registry** | `tools/registry.py` | Dynamic tool registration, discovery, and dispatch |
| **Vision Engine** | `vision/` | Screenshot → OCR → UI Detection → Vision Reasoning pipeline |
| **STT Engine** | `voice/stt.py` | faster-whisper speech recognition (GPU) |
| **TTS Engine** | `voice/tts.py` | edge-tts / pyttsx3 spoken output |
| **Task Queue** | `task_queue.py` | FIFO task queue with pause/resume/interrupt support |
| **Logger** | `logger.py` | Every action logged with timestamp, module, status |
| **Profile Manager** | `profiles.py` | Switch between Default/Developer/Study/Gaming/Research modes |

---

## 3. Event Bus — Inter-Module Communication

All modules communicate through a central **Event Bus**. No module directly calls another module. This ensures loose coupling and makes debugging trivial.

### Event Flow Example: "Chrome kholo"

```
1.  SpeechReceived      → voice/listener.py emits
2.  TranscriptionReady  → voice/stt.py emits (text: "Chrome kholo")
3.  BrainResponseReady  → brain/gemma.py emits (intent JSON)
4.  IntentParsed        → brain/intent_parser.py emits
5.  TaskCreated         → planner.py emits (task: open_chrome)
6.  TaskQueued          → task_queue.py emits
7.  PermissionChecked   → permissions.py emits (level: SAFE, approved: true)
8.  ToolStarted         → executor.py emits (tool: chrome)
9.  ToolFinished        → executor.py emits (result: success)
10. VerificationDone    → verifier.py emits (verified: true)
11. MemoryUpdated       → memory.py emits (logged action)
12. VoiceReply          → voice/tts.py emits ("Chrome khol diya")
```

### Event Interface

```python
# events.py

class Event:
    name: str           # "ToolFinished"
    source: str         # "executor"
    data: dict          # {"tool": "chrome", "success": True}
    timestamp: float    # time.time()

class EventBus:
    def subscribe(self, event_name: str, callback: Callable) -> None
    def emit(self, event: Event) -> None
    def unsubscribe(self, event_name: str, callback: Callable) -> None
```

### Core Events

| Event Name | Emitter | Data |
|---|---|---|
| `SpeechReceived` | listener.py | `{audio_data, duration}` |
| `WakeWordDetected` | listener.py | `{speaker_verified: bool}` |
| `TranscriptionReady` | stt.py | `{text, confidence, language}` |
| `BrainResponseReady` | gemma.py | `{response, tokens_used}` |
| `IntentParsed` | intent_parser.py | `{intent, tool, params, confidence}` |
| `TaskCreated` | planner.py | `{task_id, steps: []}` |
| `TaskQueued` | task_queue.py | `{task_id, position}` |
| `PermissionChecked` | permissions.py | `{level, approved, reason}` |
| `ToolStarted` | executor.py | `{tool_name, params}` |
| `ToolFinished` | executor.py | `{tool_name, success, result, error}` |
| `VerificationDone` | verifier.py | `{verified, retry_count, fallback_used}` |
| `MemoryUpdated` | memory.py | `{type, key, value}` |
| `VoiceReply` | tts.py | `{text, audio_file}` |
| `SessionStateChanged` | session.py | `{old_state, new_state}` |
| `ContextUpdated` | context.py | `{context_type, reference}` |
| `ErrorOccurred` | any module | `{module, error, traceback}` |

---

## 4. Execution Pipeline: Planner → Executor → Verifier

This is the **most critical** pipeline in Ella. Every action flows through it.

```
User Command
     │
     ▼
┌──────────────────┐
│  Conversation    │
│    Manager       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Gemma Brain    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Intent Parser   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    Planner       │ ── Decomposes into steps
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────┐
│    Executor      │────▶│   Verifier   │
└────────┬─────────┘     └──────┬───────┘
         │                      │
         │               ┌──────▼───────┐
         │               │  Verified?   │
         │               └──────┬───────┘
         │                      │
         │         ┌────────────┼────────────┐
         │         ▼            ▼            ▼
         │       YES           NO        MAX RETRIES
         │         │            │            │
         │    Next Step      Retry       Fallback
         │         │            │        or Report
         │         ▼            ▼            ▼
         │       Done      Re-execute   User notified
         │
         ▼
┌──────────────────┐
│     Memory       │ ── Log everything
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    TTS Reply     │
└──────────────────┘
```

### Planner Interface

```python
class TaskPlan:
    task_id: str
    original_command: str
    steps: list[TaskStep]
    status: str  # "pending" | "executing" | "completed" | "failed"

class TaskStep:
    step_id: int
    tool_name: str
    action: str
    params: dict
    verification: VerificationRule
    status: str  # "pending" | "running" | "success" | "failed" | "skipped"
```

### Executor Interface

```python
class Executor:
    def execute_step(self, step: TaskStep) -> ExecutionResult
    def execute_plan(self, plan: TaskPlan) -> PlanResult

class ExecutionResult:
    success: bool
    result: any
    error: str | None
    duration_ms: float
```

### Verifier Interface

```python
class VerificationRule:
    method: str          # "process_check" | "window_check" | "screenshot_check" | "file_check"
    expected: dict       # {"process_name": "chrome.exe"}
    max_retries: int     # default 2
    retry_delay: float   # seconds

class Verifier:
    def verify(self, step: TaskStep, result: ExecutionResult) -> VerificationResult
    def retry(self, step: TaskStep) -> ExecutionResult
    def fallback(self, step: TaskStep) -> ExecutionResult
```

### Verification Methods

| Method | How It Verifies | Use Case |
|---|---|---|
| `process_check` | `psutil` — is process running? | App launch |
| `window_check` | `pywinauto` — does window exist? | Window focus |
| `screenshot_check` | Vision — does screen show expected state? | UI changes |
| `file_check` | `os.path.exists()` | File operations |
| `url_check` | Playwright — is current URL correct? | Browser navigation |
| `output_check` | Terminal stdout contains expected text? | Command execution |

---

## 5. Tool Registry — Dynamic Tool System

Tools are **not hardcoded**. They register themselves at startup.

```python
# tools/registry.py

class ToolDefinition:
    name: str                    # "chrome"
    description: str             # "Open and control Google Chrome"
    category: str                # "browser" | "system" | "files" | "dev" | "media"
    permission_level: str        # "safe" | "sensitive" | "critical"
    requires_confirmation: bool
    capabilities: list[str]      # ["open", "navigate", "close"]
    parameters: dict             # JSON schema

class ToolRegistry:
    def register(self, tool: ToolDefinition, handler: Callable) -> None
    def unregister(self, name: str) -> None
    def get_tool(self, name: str) -> ToolDefinition | None
    def list_tools(self) -> list[ToolDefinition]
    def find_by_capability(self, capability: str) -> list[ToolDefinition]
    def get_all_descriptions(self) -> str  # For LLM context injection
```

### Tool Implementation Pattern

```python
# tools/chrome.py

def register(registry: ToolRegistry):
    registry.register(
        tool=ToolDefinition(
            name="chrome",
            description="Open and control Google Chrome browser",
            category="browser",
            permission_level="safe",
            requires_confirmation=False,
            capabilities=["open", "navigate", "close", "new_tab", "search"],
        ),
        handler=ChromeTool()
    )

class ChromeTool:
    def execute(self, action: str, params: dict) -> dict: ...
    def verify(self) -> bool: ...
```

---

## 6. Permission System — Three-Tier Security

```
┌──────────────────────────────────────────────┐
│              PERMISSION LEVELS               │
├──────────┬───────────────┬───────────────────┤
│  🟢 SAFE │ 🟡 SENSITIVE  │   🔴 CRITICAL     │
├──────────┼───────────────┼───────────────────┤
│ Open app │ Delete file   │ Shutdown          │
│ Search   │ Rename folder │ Registry edit     │
│ Navigate │ Move files    │ System32 access   │
│ Read file│ Install pkg   │ Admin PowerShell  │
│ OCR/Read │ Git push      │ Disk format       │
│ Music    │ Send message  │ Uninstall app     │
├──────────┼───────────────┼───────────────────┤
│ Execute  │ Single        │ Double            │
│ instantly│ confirmation  │ confirmation      │
│          │ "Kya ye karu?"│ "Are you SURE?"   │
│          │               │ + repeat command  │
└──────────┴───────────────┴───────────────────┘
```

---

## 7. Memory API — Hybrid Architecture

SQLite is the **current** backend. Interface designed for future vector DB swap.

```python
class MemoryEngine:
    # Preferences
    def set_preference(self, key: str, value: str) -> None
    def get_preference(self, key: str) -> str | None
    
    # Facts
    def remember(self, fact: str, source: str = "user") -> None
    def recall(self, query: str, limit: int = 5) -> list[str]
    
    # Conversations
    def save_message(self, role: str, content: str) -> None
    def get_recent_messages(self, count: int = 20) -> list[dict]
    
    # Patterns (Learning Engine)
    def log_action(self, action: str, context: dict) -> None
    def detect_patterns(self) -> list[Pattern]
    
    # Backend info
    def get_backend(self) -> str  # "sqlite" | "vector" | "hybrid"
```

### SQLite Schema

```sql
CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP);

CREATE TABLE facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL,
    source TEXT DEFAULT 'user',
    embedding BLOB,           -- Reserved for future vector embeddings
    created_at TIMESTAMP
);

CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT, role TEXT, content TEXT,
    intent TEXT, timestamp TIMESTAMP
);

CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT, tool TEXT, params TEXT, result TEXT,
    success BOOLEAN, context TEXT, timestamp TIMESTAMP
);

CREATE TABLE patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT, actions TEXT, confidence REAL,
    last_used TIMESTAMP, created_at TIMESTAMP
);
```

---

## 8. Context Window Manager

```python
class ContextWindowManager:
    def update(self, context_type: str, reference: Any) -> None
    def resolve(self, pronoun: str) -> Any
    def get_current_context(self) -> dict
```

| User Says | Checks | Resolution |
|---|---|---|
| "Ye delete kar do" | `last_file` → `last_folder` | Most recent file reference |
| "Ispe click karo" | `last_screenshot` → UI detection | Identified UI element |
| "Ye error kya hai" | `last_error` → `last_screenshot` | Most recent error |
| "Wo wala file" | `conversation_history[-2]` | Previous reference |

---

## 9. Task Queue

```python
class TaskQueue:
    def enqueue(self, task: TaskPlan) -> str
    def dequeue(self) -> TaskPlan | None
    def pause(self) -> None       # "Stop"
    def resume(self) -> None      # "Continue"
    def cancel_current(self) -> None
    def clear(self) -> None       # "Sab cancel karo"
    def interrupt(self, priority_task: TaskPlan) -> None
```

---

## 10. Vision Pipeline — 4-Stage

```
Screenshot (mss) → OCR (easyocr) → UI Detection (cv2/pywin) → Vision Reasoning (Gemma)
     ↓                  ↓                   ↓                        ↓
  Raw Image        Text Blocks       Button/Field Coords     Natural Language
```

---

## 11. Session — Wake Word + Speaker Verification

```
BOOT → ACTIVE (listening for "Ella") → LISTENING (processing)
                                            ↓
                                    2 min silence → SLEEPING
                                            ↓
                                    "Ella" + speaker ✓ → LISTENING
                                            ↓
                                    "Stop Ella" → EXIT
```

- Speaker verification via `resemblyzer` or `speechbrain`
- Voice fingerprint captured on first run

---

## 12. Browser: Playwright (Not Selenium)

| Feature | Playwright | Selenium |
|---|---|---|
| Auto-wait | ✅ Built-in | ❌ Manual |
| Speed | ✅ Faster | ❌ Slower |
| Reliability | ✅ Better | ❌ Flaky |
| Modern Web | ✅ Shadow DOM | ⚠️ Limited |

---

## 13. Error Handling

```
EllaError (base)
├── BrainError        — Ollama/Gemma down
├── ToolError         — Tool execution failed
├── VerificationError — Action couldn't be verified
├── PermissionError   — User denied
├── VoiceError        — STT/TTS failure
├── VisionError       — Screenshot/OCR failure
├── MemoryError       — Database failure
└── QueueError        — Queue overflow
```

Strategy: **Retry → Fallback → Report to User**

---

## 14. Logging Standard

```
[2026-07-27 11:40:23] [INFO] [voice.listener] SpeechReceived — 2.3s
[2026-07-27 11:40:24] [INFO] [voice.stt] Transcribed — "Chrome kholo" (0.97)
[2026-07-27 11:40:24] [INFO] [brain.gemma] Response — 45 tokens, 320ms
[2026-07-27 11:40:24] [INFO] [permissions] SAFE — approved
[2026-07-27 11:40:24] [INFO] [executor] chrome.open() — started
[2026-07-27 11:40:25] [INFO] [executor] chrome.open() — success (890ms)
[2026-07-27 11:40:26] [INFO] [verifier] process_check — chrome.exe running ✓
[2026-07-27 11:40:26] [INFO] [voice.tts] "Chrome khol diya"
```

---

## 15. Profile System

```python
PROFILES = {
    "default":   Profile(tools=["all"], skills=["all"]),
    "developer": Profile(tools=["vscode","terminal","git","chrome"], skills=["developer"]),
    "study":     Profile(tools=["chrome","pdf","files"], skills=["student"]),
    "gaming":    Profile(tools=["windows","spotify"], skills=["entertainment"]),
    "research":  Profile(tools=["chrome","pdf","files","search"], skills=["research"]),
}
```

---

## 16. Plugin SDK

```python
class BaseSkill(ABC):
    name: str
    description: str
    triggers: list[str]
    required_tools: list[str]
    
    @abstractmethod
    def can_handle(self, intent: str, params: dict) -> bool: ...
    
    @abstractmethod
    def execute(self, intent: str, params: dict, context: dict) -> SkillResult: ...
```
