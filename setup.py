#!/usr/bin/env python3
# ──────────────────────────────────────────────
# Project Ella v1.0 — Setup Script
# One-click environment setup + verification
# ──────────────────────────────────────────────

import subprocess
import sys
import os
import json
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



def print_header():
    """Print setup header."""
    print()
    print("=" * 55)
    print("   🧠 Project Ella v1.0 — Setup")
    print("   Your Personal Offline AI Desktop Assistant")
    print("=" * 55)
    print()


def check_python_version():
    """Verify Python version is 3.10 or 3.11."""
    version = sys.version_info
    print(f"[1/5] Python version: {version.major}.{version.minor}.{version.micro}", end="")
    
    if version.major == 3 and version.minor in (10, 11, 12, 13):
        print(" ✅")
        return True
    else:
        print(" ❌")
        print(f"      Python 3.10+ required. You have {version.major}.{version.minor}")
        return False


def install_dependencies():
    """Install Python dependencies from requirements.txt."""
    print("[2/5] Installing Python dependencies...", end="")
    
    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    if not os.path.exists(req_file):
        print(" ❌ requirements.txt not found")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_file, "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0:
            print(" ✅")
            return True
        else:
            print(" ❌")
            print(f"      Error: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(" ❌ Timeout")
        return False
    except Exception as e:
        print(f" ❌ {e}")
        return False


def check_ollama():
    """Check if Ollama is installed and running."""
    print("[3/5] Checking Ollama...", end="")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            print(" ✅ (server running)")
            return True
        else:
            print(f" ❌ (status {response.status_code})")
            return False
            
    except Exception:
        print(" ❌ (not running)")
        print("      → Install Ollama: https://ollama.com")
        print("      → Then run: ollama serve")
        return False


def check_model():
    """Check if the configured model is available in Ollama."""
    print("[4/5] Checking Gemma model...", end="")
    
    try:
        # Read model name from settings
        settings_file = os.path.join(os.path.dirname(__file__), "data", "settings.json")
        model_name = "gemma3:4b"  # default
        
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                settings = json.load(f)
                model_name = settings.get("model", model_name)
        
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        data = response.json()
        available = [m["name"] for m in data.get("models", [])]
        
        # Check for model
        model_found = any(
            model_name in name or name.startswith(model_name.split(":")[0])
            for name in available
        )
        
        if model_found:
            print(f" ✅ ({model_name})")
            return True
        else:
            print(f" ❌ ({model_name} not found)")
            print(f"      → Run: ollama pull {model_name}")
            if available:
                print(f"      → Available models: {', '.join(available)}")
            return False
            
    except Exception:
        print(" ❌ (could not check)")
        return False


def check_gpu():
    """Check if GPU is available for Ollama."""
    print("[5/5] Checking GPU...", end="")
    
    try:
        # Check NVIDIA GPU via nvidia-smi
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            gpu_info = result.stdout.strip().split(",")
            gpu_name = gpu_info[0].strip()
            gpu_mem = gpu_info[1].strip() if len(gpu_info) > 1 else "?"
            print(f" ✅ ({gpu_name}, {gpu_mem} MB)")
            return True
        else:
            print(" ⚠️  (no NVIDIA GPU detected — will use CPU)")
            print("      → Ella will work but responses will be slower")
            return True  # Not a blocker
            
    except FileNotFoundError:
        print(" ⚠️  (nvidia-smi not found — GPU status unknown)")
        print("      → If you have NVIDIA GPU, install latest drivers")
        return True  # Not a blocker
    except Exception:
        print(" ⚠️  (could not check GPU)")
        return True  # Not a blocker


def create_directories():
    """Ensure all required directories exist."""
    dirs = [
        os.path.join(os.path.dirname(__file__), "data"),
        os.path.join(os.path.dirname(__file__), "data", "logs"),
        os.path.join(os.path.dirname(__file__), "brain"),
        os.path.join(os.path.dirname(__file__), "voice"),
        os.path.join(os.path.dirname(__file__), "vision"),
        os.path.join(os.path.dirname(__file__), "tools"),
        os.path.join(os.path.dirname(__file__), "automation"),
        os.path.join(os.path.dirname(__file__), "skills"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def main():
    """Run the complete setup."""
    print_header()
    
    # Create directories
    create_directories()
    
    # Run checks
    results = []
    results.append(("Python", check_python_version()))
    results.append(("Dependencies", install_dependencies()))
    results.append(("Ollama", check_ollama()))
    results.append(("Model", check_model()))
    results.append(("GPU", check_gpu()))
    
    # Summary
    print()
    print("-" * 55)
    
    all_passed = all(r[1] for r in results)
    critical_passed = results[0][1] and results[1][1]  # Python + deps
    
    if all_passed:
        print()
        print("  ✅ All checks passed! Ella is ready.")
        print()
        print("  Run Ella:")
        print("    python main.py")
        print()
    elif critical_passed:
        print()
        print("  ⚠️  Some checks failed, but core is ready.")
        print("  Fix the issues above, then run:")
        print("    python main.py")
        print()
    else:
        print()
        print("  ❌ Critical checks failed. Fix the issues above.")
        print()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
