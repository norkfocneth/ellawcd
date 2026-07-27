# Project Ella v1.0
# Your Personal Offline AI Desktop Assistant

## Quick Start

### Prerequisites
1. **Python 3.10+** — [Download](https://www.python.org/downloads/)
2. **Ollama** — [Download](https://ollama.com)

### Setup

```bash
# 1. Pull the AI model
ollama pull gemma3:4b

# 2. Start Ollama server (keep this running)
ollama serve

# 3. Install dependencies
pip install -r requirements.txt

# 4. Or run auto-setup
python setup.py

# 5. Launch Ella
python main.py
```

### Usage

Just type naturally:
```
You:  Good morning
Ella: Good morning, Arnav! ☀️ Ready hoon. Aaj kya karna hai?

You:  Explain Python decorators
Ella: Decorators basically ek function ko wrap karte hain...

You:  Motivate me
Ella: Arnav, tu kar sakta hai! Bas consistent reh...

You:  bye
Ella: Bye Arnav! Take care. 👋
```

### Commands
- **Chat naturally** — Just type anything
- **exit / bye / quit** — Exit Ella
- **python main.py --test** — Run self-check
- **python main.py --help** — Show help

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full engineering blueprint.

## Project Structure

```
ELLA.AI/
├── main.py           # Entry point
├── config.py         # Configuration
├── conversation.py   # Chat manager
├── events.py         # Event Bus
├── logger.py         # Logging
├── brain/
│   ├── gemma.py      # LLM client
│   └── prompts.py    # Personality
└── data/
    ├── settings.json  # User settings
    └── logs/          # Runtime logs
```

## Roadmap

- [x] Phase 1: Foundation (text chat + Gemma brain)
- [ ] Phase 2: Voice (STT + TTS)
- [ ] Phase 3: Session System (sleep/wake)
- [ ] Phase 4: Tool Calling (app control)
- [ ] Phase 5-15: See implementation plan

## License

Personal project by Arnav.
