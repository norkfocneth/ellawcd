# ──────────────────────────────────────────────
# Project Ella v1.0 — Text-To-Speech (TTS)
# Powered by edge-tts (Natural Indian English female voice)
# ──────────────────────────────────────────────

import asyncio
import subprocess
import os
import sys
import tempfile
from pathlib import Path

from config import TTS_VOICE, DATA_DIR
from logger import get_logger
from events import event_bus, Event

log = get_logger("voice.tts")


class TextToSpeech:
    """
    Ella's voice output engine using edge-tts.
    
    Generates natural-sounding speech from text using Microsoft Edge's
    neural TTS engine (free, high-quality).
    
    Default Voice: en-IN-NeerjaNeural (Indian English female)
    
    Usage:
        tts = TextToSpeech()
        tts.speak("Hi Arnav! Main Ella. Ready hoon.")
    """

    def __init__(self, voice: str = None):
        self.voice = voice or TTS_VOICE
        self.temp_dir = DATA_DIR / "cache"
        self.temp_dir.mkdir(exist_ok=True)
        self.enabled = True
        log.info(f"TextToSpeech initialized — voice: {self.voice}")

    def speak(self, text: str, block: bool = True) -> bool:
        """
        Convert text to speech and play it out loud.
        
        Args:
            text:  The text string for Ella to speak
            block: If True, waits until speech completes before returning
            
        Returns:
            True if audio generated & played successfully
        """
        if not self.enabled or not text.strip():
            return False
            
        # Clean text for speech (strip markdown, emojis, code blocks)
        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            return False
            
        log.info(f"Speaking: '{clean_text[:60]}{'...' if len(clean_text) > 60 else ''}'")
        
        # Audio file path
        audio_file = str(self.temp_dir / "ella_reply.mp3")
        
        try:
            # Generate MP3 using edge-tts CLI or async API
            success = self._generate_audio(clean_text, audio_file)
            
            if success and os.path.exists(audio_file):
                # Emit event
                event_bus.emit(Event(
                    name="VoiceReply",
                    source="voice.tts",
                    data={"text": clean_text, "voice": self.voice}
                ))
                
                # Play the generated audio file
                self._play_audio(audio_file, block=block)
                return True
            return False
            
        except Exception as e:
            log.error(f"TTS Error: {e}")
            return False

    def _generate_audio(self, text: str, output_file: str) -> bool:
        """Generate MP3 audio file from text using edge-tts."""
        try:
            # Run edge-tts via python -m edge_tts CLI for maximum reliability
            cmd = [
                sys.executable, "-m", "edge_tts",
                "--voice", self.voice,
                "--text", text,
                "--write-media", output_file
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            
            if result.returncode == 0 and os.path.exists(output_file):
                return True
            else:
                log.error(f"edge-tts error: {result.stderr}")
                return False
                
        except Exception as e:
            log.error(f"Failed to generate audio: {e}")
            return False

    def _play_audio(self, audio_file: str, block: bool = True) -> None:
        """
        Play an MP3 file on Windows using PowerShell MediaPlayer (no extra dependencies).
        """
        abs_path = os.path.abspath(audio_file).replace("\\", "/")
        
        # PowerShell script using System.Windows.Media.MediaPlayer
        ps_script = f"""
        Add-Type -AssemblyName presentationCore
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open([Uri]"{abs_path}")
        $player.Play()
        Start-Sleep -Milliseconds 300
        while ($player.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}
        $duration = $player.NaturalDuration.TimeSpan.TotalSeconds
        Start-Sleep -Seconds $duration
        $player.Close()
        """
        
        try:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]
            
            if block:
                subprocess.run(cmd, capture_output=True, timeout=30)
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        except Exception as e:
            log.error(f"Error playing audio: {e}")

    def _clean_text_for_speech(self, text: str) -> str:
        """
        Clean markdown formatting, code blocks, emojis, and symbols
        so TTS speaks natural sentences.
        """
        import re
        
        # Remove code blocks ```...```
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove inline code `...`
        text = re.sub(r'`.*?`', '', text)
        # Remove markdown headers #, ##, etc.
        text = re.sub(r'#+\s*', '', text)
        # Remove markdown bold/italic *, _
        text = re.sub(r'[*_]{1,3}', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove JSON memory blocks if any left
        text = re.sub(r'```ella_memory.*?```', '', text, flags=re.DOTALL)
        
        # Keep letters, numbers, common punctuation, Hinglish words
        return text.strip()
