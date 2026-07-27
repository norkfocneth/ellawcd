# 🧠 Project Ella v1.0 — Master Implementation Plan (Final)

> **Ella = Personal AI Operating System for Windows**
> **Tagline: Your Personal Offline AI Desktop Assistant**

---

## What Changed From Previous Plan

| # | Feedback | Status |
|---|---|---|
| 1 | **Verifier** added to pipeline (Planner → Executor → Verifier) | ✅ Added |
| 2 | **Tool Registry** — dynamic registration, no hardcoded tools | ✅ Added |
| 3 | **Permission System** — Safe / Sensitive / Critical tiers | ✅ Added |
| 4 | **Vision 4-stage** — Screenshot → OCR → UI Detection → Vision Reasoning | ✅ Added |
| 5 | **Playwright** for browser (not Selenium) | ✅ Switched |
| 6 | **Hybrid Memory** — SQLite + Vector-ready interface | ✅ Added |
| 7 | **Event Bus** — all modules communicate via events | ✅ Added |
| 8 | **Task Queue** — FIFO with pause/resume/interrupt | ✅ Added |
| 9 | **Context Window Manager** — resolves "ye", "is", "wo" | ✅ Added |
| 10 | **Profiles** — Default / Developer / Study / Gaming / Research | ✅ Added |
| 11 | **Detailed Logging** — every action timestamped | ✅ Added |
| 12 | **Plugin SDK** — BaseSkill abstract class | ✅ Added |
| 13 | **Gemma4:e4b** with GPU from day 1 (not gemma2:2b) | ✅ Changed |
| 14 | **Wake word "Ella" only** — speaker-verified, ignores other voices | ✅ Changed |
| 15 | **ARCHITECTURE.md** created as engineering blueprint | ✅ Created |
| 16 | **Future Skills ecosystem** — 11+ skill domains | ✅ Added |

---

## Architecture Summary

Full pipeline (see [ARCHITECTURE.md](file:///c:/Users/FOCNETH/OneDrive/Desktop/ELLA.AI/ARCHITECTURE.md) for complete details):

```
User Voice/Text
     │
     ▼
Conversation Manager
     │
     ▼
STT (faster-whisper, GPU)              [Phase 2]
     │
     ▼
Gemma4:e4b Brain (Ollama, GPU)
     │
     ▼
Intent Parser → Context Window Manager
     │
     ▼
Planner Engine
     │
     ▼
Permission System (Safe/Sensitive/Critical)
     │
     ▼
Task Queue (FIFO + interrupt)
     │
     ▼
Executor
     │
     ▼
Tool Registry → Tool Handler
     │
     ▼
Verifier (process/window/screenshot/file check)
     │           │
     ▼           ▼
   Pass        Fail → Retry → Fallback → Report
     │
     ▼
Memory Engine (SQLite + future Vector)
     │
     ▼
Event Bus → Logger (every action logged)
     │
     ▼
TTS (edge-tts, female Indian English voice)
```

---

## 📁 Updated Directory Structure

```
ELLA.AI/
│
├── main.py                    # Entry point — boot sequence + CLI
├── config.py                  # Central config (model, paths, GPU settings)
├── session.py                 # Session lifecycle (active/sleep/wake/exit)
├── conversation.py            # Chat loop + message history
├── context.py                 # Context Window Manager ("ye", "is", "wo")
├── events.py                  # Event Bus (pub/sub)
├── executor.py                # Step executor — runs tools
├── verifier.py                # Verifies each executed step
├── planner.py                 # Multi-step task decomposition
├── task_queue.py              # FIFO task queue with interrupt
├── memory.py                  # Hybrid memory engine (SQLite + Vector-ready)
├── permissions.py             # Three-tier permission system
├── profiles.py                # Profile manager (Default/Dev/Study/etc)
├── logger.py                  # Structured logging (loguru)
├── requirements.txt           # All dependencies
├── setup.py                   # One-click setup + Ollama/GPU check
├── README.md                  # Documentation
├── ARCHITECTURE.md            # Engineering blueprint
│
├── brain/
│   ├── __init__.py
│   ├── gemma.py               # Ollama client — Gemma4:e4b (GPU)
│   ├── prompts.py             # System prompts (personality)
│   └── intent_parser.py       # Intent extraction + tool routing
│
├── voice/
│   ├── __init__.py
│   ├── listener.py            # Mic capture + wake word "Ella" + speaker verification
│   ├── stt.py                 # faster-whisper STT (GPU)
│   ├── tts.py                 # edge-tts / pyttsx3 TTS
│   └── silence_detector.py    # Auto-sleep after 2 min silence
│
├── vision/
│   ├── __init__.py
│   ├── screenshot.py          # Screen capture (mss)
│   ├── ocr.py                 # Text extraction (easyocr)
│   ├── ui_detector.py         # Button/field/element detection
│   └── analyzer.py            # Vision reasoning (LLM-powered)
│
├── tools/
│   ├── __init__.py
│   ├── registry.py            # Dynamic Tool Registry
│   ├── chrome.py              # Chrome control
│   ├── browser.py             # Playwright browser automation
│   ├── files.py               # File operations
│   ├── terminal.py            # Shell command execution
│   ├── vscode.py              # VS Code control
│   ├── spotify.py             # Spotify launcher
│   ├── windows.py             # Shutdown/restart/lock/volume
│   ├── pdf.py                 # PDF reading + Q&A
│   ├── email.py               # Email drafting (future)
│   ├── search.py              # Web search automation
│   └── calculator.py          # Calculator launcher
│
├── automation/
│   ├── __init__.py
│   ├── ui.py                  # High-level UI interaction
│   ├── mouse.py               # Mouse control
│   └── keyboard.py            # Keyboard control + hotkeys
│
├── skills/
│   ├── __init__.py
│   ├── base_skill.py          # Abstract BaseSkill class
│   ├── developer_skill.py     # Dev workflow
│   ├── student_skill.py       # Study workflow
│   ├── music_skill.py         # Music workflow
│   ├── productivity_skill.py  # Productivity workflow
│   ├── social_media_skill.py  # Social media automation
│   ├── research_skill.py      # Research workflow
│   ├── mindfulness_skill.py   # Meditation/focus
│   ├── entertainment_skill.py # Spotify/YouTube/Netflix
│   └── automation_skill.py    # Custom macro workflows
│
└── data/
    ├── memory.db              # SQLite database
    ├── settings.json          # User preferences
    ├── voice_profile.bin      # Speaker voice fingerprint
    └── logs/                  # Runtime logs
```

---

## 🛠️ Technology Stack

| Component | Library | Notes |
|---|---|---|
| **Runtime** | Python 3.10 / 3.11 | |
| **LLM Brain** | Ollama + `gemma4:e4b` | GPU-accelerated from day 1 |
| **STT** | `faster-whisper` | GPU mode, `base` or `small` model |
| **TTS** | `edge-tts` (`en-IN-NeerjaNeural`) | Calm female Indian English |
| **TTS Fallback** | `pyttsx3` | Windows SAPI5 native |
| **Speaker ID** | `resemblyzer` or `speechbrain` | Voice fingerprint verification |
| **Audio Capture** | `sounddevice` + `numpy` | Mic input |
| **Screen Capture** | `mss` | Fast screenshots |
| **OCR** | `easyocr` | Text extraction |
| **Image Processing** | `Pillow`, `opencv-python` | UI element detection |
| **OS Automation** | `pyautogui`, `pywinauto` | Mouse, keyboard, windows |
| **Process Management** | `psutil` | Process detection (verifier) |
| **Browser** | `playwright` | Reliable browser automation |
| **PDF** | `PyMuPDF` (fitz) | PDF reading + extraction |
| **Database** | `sqlite3` | Memory persistence |
| **CLI UI** | `rich` | Beautiful terminal output |
| **HTTP** | `requests` | Ollama API |
| **Logging** | `loguru` | Structured logs |
| **Events** | Custom `EventBus` | Inter-module communication |

---

## 📦 Prerequisites

> [!IMPORTANT]
> User must install before running Ella:
> 1. **Python 3.10 or 3.11** — [python.org](https://www.python.org/downloads/)
> 2. **Ollama** — [ollama.com](https://ollama.com)
> 3. **Pull Gemma4** — `ollama pull gemma4:e4b`
> 4. **NVIDIA GPU + CUDA** — for GPU acceleration (Ollama auto-detects)
> 5. **Working microphone** — for voice (Phase 2+)

---

## 🗓️ 15-Phase Development Roadmap

Each phase is independently testable and builds on the previous.

---

### Phase 1 — Foundation 🏗️

**Goal**: Project skeleton + Event Bus + Gemma4 brain + text chat with Rich CLI

**New Files**:

| File | Purpose |
|---|---|
| `main.py` | Boot sequence with Rich animated loading (Loading Brain... Loading Memory... Ready.) |
| `config.py` | Model name (`gemma4:e4b`), paths, GPU flag, user name |
| `logger.py` | Loguru logger — file + console, timestamped |
| `events.py` | EventBus class — subscribe, emit, unsubscribe |
| `conversation.py` | Text input loop, chat history, sends to Brain |
| `brain/gemma.py` | Ollama HTTP client — POST to localhost:11434, GPU config |
| `brain/prompts.py` | System prompt — Ella personality, Hinglish/English, friendly |
| `data/settings.json` | Default user preferences |
| `requirements.txt` | All pip dependencies |
| `setup.py` | Auto-install + verify Ollama + check GPU |
| `README.md` | Project docs |

**Test**: `python main.py` → boot animation → type "Good morning" → Ella replies naturally via Gemma4.

---

### Phase 2 — Voice 🎤

**Goal**: Hands-free input + spoken output + speaker-verified wake word "Ella"

**New Files**:

| File | Purpose |
|---|---|
| `voice/stt.py` | faster-whisper on GPU — audio → text |
| `voice/tts.py` | edge-tts with `en-IN-NeerjaNeural` — text → spoken audio |
| `voice/listener.py` | Continuous mic → wake word "Ella" detection → speaker verification → STT |
| `data/voice_profile.bin` | Owner's voice fingerprint (captured on first run) |

**Wake Word Logic**:
- Ella listens passively for the word "Ella"
- When detected, runs **speaker verification** against stored voice profile
- If speaker matches → activate listening mode
- If speaker doesn't match → ignore completely
- Random noise / TV / other people → ignored

**Test**: Say "Ella, how are you?" → Ella responds via voice. Someone else says "Ella" → nothing happens.

---

### Phase 3 — Session System ⏱️

**Goal**: Smart lifecycle — sleep/wake/exit, only activates on owner's "Ella"

**New Files**:

| File | Purpose |
|---|---|
| `session.py` | State machine: BOOT → ACTIVE → LISTENING → SLEEPING → EXIT |
| `voice/silence_detector.py` | 2 min silence → trigger sleep |

**State Transitions**:
```
BOOT → ACTIVE (passively listening for "Ella")
     → owner says "Ella" + speaker ✓ → LISTENING (processing commands)
     → 2 min silence → SLEEPING (low power, still listening for "Ella")
     → owner says "Ella" again → LISTENING (resume)
     → "Stop Ella" or "Bye Ella" → EXIT (clean shutdown)
```

**Test**: Chat → go silent 2 min → Ella says "Going to sleep" → say "Ella" → she wakes.

---

### Phase 4 — Tool Calling + Registry 🔧

**Goal**: Dynamic tool registration + intent parsing + desktop app control

**New Files**:

| File | Purpose |
|---|---|
| `brain/intent_parser.py` | Parse LLM JSON response → extract intent, tool, params |
| `tools/registry.py` | ToolRegistry class — register, discover, dispatch |
| `tools/chrome.py` | Chrome launcher (registered tool) |
| `tools/vscode.py` | VS Code launcher (registered tool) |
| `tools/spotify.py` | Spotify launcher (registered tool) |
| `tools/calculator.py` | Calculator launcher (registered tool) |
| `tools/windows.py` | Shutdown/restart/lock (registered, CRITICAL permission) |
| `tools/terminal.py` | Shell command execution (registered, SENSITIVE) |
| `permissions.py` | Three-tier permission checking |

**Intent Parser Output**:
```json
{
  "intent": "open_app",
  "tool": "chrome",
  "params": {"url": "https://youtube.com"},
  "confidence": 0.95
}
```

**Test**: "Chrome kholo" → Chrome opens. "Shutdown karo" → double confirmation asked.

---

### Phase 5 — Execution Pipeline (Executor + Verifier) ✅

**Goal**: Every action is executed AND verified. Retry on failure.

**New Files**:

| File | Purpose |
|---|---|
| `executor.py` | Executes tool steps from Planner |
| `verifier.py` | Verifies each step succeeded (process_check, window_check, etc.) |
| `task_queue.py` | FIFO queue with pause/resume/interrupt |

**Pipeline**: Planner → Queue → Permission Check → Executor → Verifier → Memory Log

**Verification Methods**:
- `process_check` — is chrome.exe running? (psutil)
- `window_check` — does window exist? (pywinauto)
- `file_check` — does file exist? (os.path)
- `output_check` — terminal output correct?

**Test**: "Chrome kholo" → opens → verifier confirms chrome.exe running → "Chrome khol diya". If Chrome fails → retry → fallback → report.

---

### Phase 6 — Windows Automation 🖱️

**Goal**: Low-level mouse + keyboard control

**New Files**:

| File | Purpose |
|---|---|
| `automation/mouse.py` | Click, double-click, right-click, scroll, drag |
| `automation/keyboard.py` | Type text, hotkeys (Ctrl+C, Alt+Tab, Win+D) |
| `automation/ui.py` | High-level: find window → focus → interact |

**Test**: "Alt Tab karo" → window switches. "Ye text type karo: Hello World" → types it.

---

### Phase 7 — Memory + Context 🧠

**Goal**: Long-term memory + context resolution ("ye", "wo")

**New Files**:

| File | Purpose |
|---|---|
| `memory.py` | SQLite backend with vector-ready interface |
| `context.py` | Context Window Manager — tracks last_file, last_screenshot, active_window, etc. |
| `data/memory.db` | Database file |

**Schema**: preferences, facts, conversations, action_log, patterns (see ARCHITECTURE.md)

**Test**: "Remember mera favourite editor VS Code hai" → stored. Restart → "Mera favourite editor kya hai?" → "VS Code". "Ye delete kar do" → resolves "ye" from context.

---

### Phase 8 — Planner Engine 📋

**Goal**: Break complex multi-step requests into executable sub-task plans

**New Files**:

| File | Purpose |
|---|---|
| `planner.py` | LLM-powered decomposition → ordered TaskStep list |

**Example**:
```
User: "YouTube pe lo-fi music search karo aur chala do"

Plan:
  Step 1: Open Chrome         [tool: chrome]
  Step 2: Navigate YouTube     [tool: browser, url: youtube.com]
  Step 3: Search "lo-fi music" [tool: browser, action: search]
  Step 4: Click first result   [tool: automation, action: click]
  
Each step: Execute → Verify → Next
```

**Test**: "Python download karo" → multi-step plan generated → executes step by step.

---

### Phase 9 — Vision (Screen Intelligence) 👁️

**Goal**: 4-stage vision pipeline — see and understand the screen

**New Files**:

| File | Purpose |
|---|---|
| `vision/screenshot.py` | Full screen / active window capture (mss) |
| `vision/ocr.py` | Text extraction (easyocr) |
| `vision/ui_detector.py` | Button/field/element detection + coordinates (cv2) |
| `vision/analyzer.py` | Vision reasoning — describe screen state using LLM |

**Pipeline**: Screenshot → OCR → UI Detection → Vision Reasoning

**Test**: "Meri screen dekh" → "Chrome me YouTube khula hai, search bar me 'python tutorial' likha hai." "Ye error kya hai?" → reads and explains error popup.

---

### Phase 10 — Smart Vision Actions 🎯

**Goal**: Vision-guided clicking, form filling, waiting for UI changes

**Modified Files**:

| File | Changes |
|---|---|
| `vision/ui_detector.py` | Add coordinate extraction for detected elements |
| `automation/ui.py` | Add vision-guided click/type at detected coordinates |

**Example Flow**:
```
"Login button pe click karo"
  → Screenshot → OCR → Find "Login" → Get coordinates → Click
  → Verify: is login form gone / new page loaded?
```

**Test**: "Is button pe click karo" → Ella finds it visually, clicks, verifies result.

---

### Phase 11 — Browser Intelligence 🌐

**Goal**: Playwright-powered web interaction — read, fill, navigate, summarize

**New/Modified Files**:

| File | Purpose |
|---|---|
| `tools/browser.py` | Playwright: navigate, read content, fill forms, manage tabs |
| `tools/search.py` | Google search automation + result extraction |

**Capabilities**: YouTube, Instagram, Amazon, page summaries, form filling, tab management.

**Test**: "YouTube pe lo-fi search karo" → opens YouTube, searches, plays music.

---

### Phase 12 — File & Document Intelligence 📄

**Goal**: File management + PDF Q&A + document reading

**New/Modified Files**:

| File | Purpose |
|---|---|
| `tools/files.py` | Search, rename, delete, move, organize, duplicate detection |
| `tools/pdf.py` | PyMuPDF: read, summarize, Q&A, keyword search |

**Test**: "Resume.pdf dhoondo" → locates file. "Is PDF ka summary do" → reads and summarizes.

---

### Phase 13 — Developer Mode 💻

**Goal**: Terminal, Git, project management, error log analysis

**Modified Files**:

| File | Changes |
|---|---|
| `tools/terminal.py` | Safe command execution with output capture + explanation |
| `tools/vscode.py` | Project-aware: open project, run tasks |

**Test**: "Git pull karo" → runs git pull, shows output. "Error explain karo" → reads and explains.

---

### Phase 14 — Learning Engine + Profiles 🎓

**Goal**: Observe user patterns → automate routines. Profile switching.

**New/Modified Files**:

| File | Changes |
|---|---|
| `memory.py` | Add pattern tracking + detection |
| `planner.py` | Add routine auto-execution from learned patterns |
| `profiles.py` | Profile switching (Default/Developer/Study/Gaming/Research) |

**Example**: After 5 coding sessions opening VS Code + Chrome + Spotify → "Coding shuru" auto-opens all three.

**Test**: "Developer mode" → switches profile, changes active tools and prompts.

---

### Phase 15 — Skills + Personality ✨

**Goal**: Plugin skill system + natural Hinglish personality polish

**New Files**:

| File | Purpose |
|---|---|
| `skills/base_skill.py` | Abstract BaseSkill class |
| `skills/developer_skill.py` | Dev workflow automation |
| `skills/student_skill.py` | Study/research workflow |
| `skills/music_skill.py` | Music control workflow |
| `skills/productivity_skill.py` | Calendar, notes, todos |
| `skills/social_media_skill.py` | WhatsApp, Instagram, Discord |
| `skills/research_skill.py` | Multi-source research |
| `skills/mindfulness_skill.py` | Focus sessions, breaks |
| `skills/entertainment_skill.py` | Spotify, YouTube, Netflix |
| `skills/automation_skill.py` | Custom macro workflows |
| `brain/prompts.py` | Enhanced personality — Hinglish, context-aware, adaptive tone |
| `voice/tts.py` | Natural pauses, emphasis, pacing |

**Future Skill Domains**:

| Skill | Capabilities |
|---|---|
| 🎓 Student | Notes summary, PDF Q&A, assignment help, timetable |
| 💻 Developer | VS Code, Git, Terminal, debugging, code explain |
| 🧘 Mindfulness | Meditation timer, focus sessions, breathing, break reminders |
| 📱 Social Media | WhatsApp, Instagram, X, LinkedIn, Discord, Telegram |
| 🎵 Entertainment | Spotify, YouTube, Netflix, playlists |
| 📂 Productivity | Calendar, notes, to-do, reminders, email |
| 🔬 Research | Multi-source search, compare, summarize, save references |
| 🤖 Automation | Multi-step workflows, scheduled tasks, custom macros |
| 🏠 Smart Home (v2) | Lights, fan, AC, IoT devices |

---

## 🔗 Phase Dependencies

```
Phase 1  (Foundation + Event Bus + Gemma4)
  ├── Phase 2  (Voice + Speaker Verification)
  │    └── Phase 3  (Session + Wake Word "Ella")
  ├── Phase 4  (Tool Registry + Intent Parser + Permissions)
  │    └── Phase 5  (Executor + Verifier + Task Queue)
  │         ├── Phase 6  (Windows Automation)
  │         ├── Phase 11 (Browser Intelligence — Playwright)
  │         ├── Phase 12 (File & PDF Intelligence)
  │         └── Phase 13 (Developer Mode)
  ├── Phase 7  (Memory + Context Window Manager)
  │    └── Phase 14 (Learning Engine + Profiles)
  ├── Phase 8  (Planner Engine)
  ├── Phase 9  (Vision — 4-stage pipeline)
  │    └── Phase 10 (Smart Vision Actions)
  └── Phase 15 (Skills Plugin System + Personality)
```

---

## 🎯 Definition of Done (v1.0)

User speaks:

> *"Ella, meri screen dekh. WhatsApp me Rahul ko bolo ki main 15 minute me call karunga. Uske baad Chrome me YouTube kholo aur lo-fi music chala do. Fir VS Code kholkar mera Stella project open kar do."*

**Ella automatically**:
1. Captures screenshot → analyzes UI state (Vision)
2. Locates WhatsApp Web → selects Rahul's chat (Browser + Vision)
3. Drafts message → asks confirmation (Permission: SENSITIVE)
4. Opens Chrome → navigates YouTube → searches "lo-fi music" → plays (Browser)
5. Launches VS Code → opens STELLA.PRE project (Tool)
6. Each step: **Execute → Verify → Next** (Executor + Verifier)
7. All actions logged with timestamps (Logger)
8. Context updated throughout (Context Manager)
9. Speaks: **"Done. Aur kuch?"** (TTS)

---

## 🧪 Verification Plan

### Per-Phase Tests

| Phase | Test | Pass Criteria |
|---|---|---|
| 1 | `python main.py` | Boot screen + Gemma4 chat works |
| 2 | Speak "Ella, hello" | Voice response heard |
| 2 | Another person says "Ella" | Nothing happens (speaker locked) |
| 3 | Stay silent 2 min | Ella sleeps, wakes on "Ella" |
| 4 | "Chrome kholo" | Chrome opens |
| 4 | "Shutdown karo" | Double confirmation asked |
| 5 | "Chrome kholo" (Chrome fails) | Retry → fallback → report |
| 6 | "Alt Tab karo" | Window switches |
| 7 | "Remember X" → restart → "X kya tha?" | Memory persists |
| 7 | "Ye delete karo" (after opening file) | Resolves "ye" correctly |
| 8 | "Python download karo" | Multi-step plan generated |
| 9 | "Meri screen dekh" | Screen described in natural language |
| 10 | "Login button pe click karo" | Button found and clicked |
| 11 | "YouTube pe search karo" | Playwright opens and searches |
| 12 | "Resume.pdf dhoondo" | File located |
| 13 | "Git status dikhao" | Output shown + explained |
| 14 | "Coding shuru" (after learning) | Learned apps auto-open |
| 15 | Natural Hinglish conversation | Contextual, friendly replies |

### End-to-End Acceptance

Full multi-step command → all actions execute → all verified → "Done. Aur kuch?"

---

## 🚀 Execution Strategy

> [!IMPORTANT]
> Phase 1 starts immediately on your approval. Each phase will be built, tested, and approved before the next begins. The [ARCHITECTURE.md](file:///c:/Users/FOCNETH/OneDrive/Desktop/ELLA.AI/ARCHITECTURE.md) serves as the engineering blueprint throughout development.

**Approve to begin Phase 1 (Foundation).**
