# ──────────────────────────────────────────────
# Project Ella v1.0 — Persistent Memory Engine
# SQLite-backed memory that never forgets
# Ella will know you better than you know yourself
# ──────────────────────────────────────────────

import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path

from config import MEMORY_DB, USER_NAME
from logger import get_logger
from events import event_bus, Event

log = get_logger("memory")


class Memory:
    """
    Ella's persistent memory — powered by SQLite.
    
    Stores:
    - Every conversation (user message + Ella response)
    - Personal facts about the user (likes, habits, style, projects)
    - Session summaries
    
    Ella will recall everything — even after restart.
    
    Usage:
        mem = Memory()
        mem.save_conversation("I love biryani", "Nice! Biryani lover ho tum!")
        mem.save_fact("food_preference", "Loves biryani")
        
        # Later...
        facts = mem.get_all_facts()
        recent = mem.get_recent_conversations(limit=10)
        context = mem.build_memory_context()  # Inject into brain prompt
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(MEMORY_DB)
        self.conn = None
        self._connect()
        self._create_tables()
        log.info(f"Memory initialized — {self.db_path}")

    def _connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent performance
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def _create_tables(self):
        """Create memory tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # ── Conversations Table ────────────────────
        # Every single message exchange is stored here
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_message TEXT NOT NULL,
                ella_response TEXT NOT NULL,
                session_id TEXT,
                tokens_used INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0
            )
        """)
        
        # ── Facts Table ────────────────────────────
        # Personal facts extracted from conversations
        # Example: ("food", "Loves biryani and chai")
        # Example: ("project", "Working on Stella — a Python AI")
        # Example: ("style", "Prefers Hinglish, casual tone")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                fact TEXT NOT NULL,
                source TEXT DEFAULT 'conversation',
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # ── Sessions Table ─────────────────────────
        # Track each session (when Ella was started/stopped)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                message_count INTEGER DEFAULT 0,
                summary TEXT
            )
        """)
        
        self.conn.commit()

    # ═══════════════════════════════════════════
    # CONVERSATION STORAGE
    # ═══════════════════════════════════════════

    def save_conversation(self, user_message: str, ella_response: str, 
                          session_id: str = None, tokens_used: int = 0,
                          latency_ms: int = 0) -> int:
        """
        Save a conversation exchange to memory.
        
        Args:
            user_message:  What the user said
            ella_response: What Ella replied
            session_id:    Current session identifier
            tokens_used:   Tokens consumed by the response
            latency_ms:    Response latency in milliseconds
            
        Returns:
            Row ID of the saved conversation
        """
        timestamp = datetime.now().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (timestamp, user_message, ella_response, 
                                       session_id, tokens_used, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, user_message, ella_response, session_id, tokens_used, latency_ms))
        
        self.conn.commit()
        row_id = cursor.lastrowid
        
        log.debug(f"Conversation saved — id:{row_id}")
        
        # Emit event
        event_bus.emit(Event(
            name="MemoryUpdated",
            source="memory",
            data={"type": "conversation", "id": row_id}
        ))
        
        return row_id

    def get_recent_conversations(self, limit: int = 20) -> list[dict]:
        """Get recent conversations, newest first."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, user_message, ella_response 
            FROM conversations 
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in reversed(rows)]  # Return in chronological order

    def get_conversation_count(self) -> int:
        """Get total number of stored conversations."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        return cursor.fetchone()[0]

    def search_conversations(self, query: str, limit: int = 10) -> list[dict]:
        """Search conversations by keyword."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, user_message, ella_response 
            FROM conversations 
            WHERE user_message LIKE ? OR ella_response LIKE ?
            ORDER BY id DESC 
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
        
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════
    # FACTS STORAGE (Personal Knowledge)
    # ═══════════════════════════════════════════

    def save_fact(self, category: str, fact: str, source: str = "conversation",
                  confidence: float = 1.0) -> int:
        """
        Save a personal fact about the user.
        
        Categories: name, food, music, project, habit, style, mood, 
                    preference, relationship, work, hobby, goal, etc.
        
        If a fact in the same category with similar content exists,
        it updates instead of duplicating.
        """
        now = datetime.now().isoformat()
        
        # Check if similar fact exists
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM facts 
            WHERE category = ? AND fact = ?
        """, (category, fact))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing fact
            cursor.execute("""
                UPDATE facts SET updated_at = ?, confidence = ? WHERE id = ?
            """, (now, confidence, existing["id"]))
            self.conn.commit()
            return existing["id"]
        
        # Insert new fact
        cursor.execute("""
            INSERT INTO facts (category, fact, source, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (category, fact, source, confidence, now, now))
        
        self.conn.commit()
        row_id = cursor.lastrowid
        
        log.debug(f"Fact saved — [{category}] {fact}")
        
        return row_id

    def get_all_facts(self) -> list[dict]:
        """Get all stored facts about the user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT category, fact, confidence, updated_at 
            FROM facts 
            ORDER BY category, updated_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_facts_by_category(self, category: str) -> list[dict]:
        """Get facts in a specific category."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT fact, confidence, updated_at 
            FROM facts 
            WHERE category = ?
            ORDER BY updated_at DESC
        """, (category,))
        return [dict(row) for row in cursor.fetchall()]

    def get_fact_count(self) -> int:
        """Get total number of stored facts."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM facts")
        return cursor.fetchone()[0]

    # ═══════════════════════════════════════════
    # SESSION TRACKING
    # ═══════════════════════════════════════════

    def start_session(self, session_id: str) -> None:
        """Record a new session start."""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO sessions (session_id, started_at) 
            VALUES (?, ?)
        """, (session_id, now))
        self.conn.commit()
        log.debug(f"Session started — {session_id}")

    def end_session(self, session_id: str, message_count: int = 0, 
                    summary: str = None) -> None:
        """Record session end with stats."""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sessions 
            SET ended_at = ?, message_count = ?, summary = ?
            WHERE session_id = ?
        """, (now, message_count, summary, session_id))
        self.conn.commit()

    # ═══════════════════════════════════════════
    # MEMORY CONTEXT (Inject into Brain Prompt)
    # ═══════════════════════════════════════════

    def build_memory_context(self, max_facts: int = 30, max_recent: int = 10) -> str:
        """
        Build a memory context string to inject into the brain's system prompt.
        
        This gives Ella awareness of:
        - Who the user is (all stored facts)
        - Recent conversation history
        
        Returns:
            A formatted string to append to the system prompt
        """
        parts = []
        
        # ── Personal Facts ─────────────────────
        facts = self.get_all_facts()
        if facts:
            parts.append("## What I Know About You")
            current_category = None
            for f in facts[:max_facts]:
                cat = f["category"].title()
                if cat != current_category:
                    current_category = cat
                    parts.append(f"\n### {cat}")
                parts.append(f"- {f['fact']}")
        
        # ── Recent Conversations ───────────────
        recent = self.get_recent_conversations(limit=max_recent)
        if recent:
            parts.append("\n## Recent Conversation History")
            for conv in recent:
                parts.append(f"User: {conv['user_message']}")
                parts.append(f"Ella: {conv['ella_response'][:200]}")
                parts.append("")
        
        # ── Stats ──────────────────────────────
        conv_count = self.get_conversation_count()
        fact_count = self.get_fact_count()
        if conv_count > 0:
            parts.append(f"\n[Memory Stats: {conv_count} conversations, {fact_count} facts stored]")
        
        return "\n".join(parts)

    # ═══════════════════════════════════════════
    # FACT EXTRACTION (Auto-learn from conversation)
    # ═══════════════════════════════════════════

    def extract_facts_prompt(self) -> str:
        """Disabled for now as requested — pure text conversation."""
        return ""

    def parse_and_save_facts(self, response: str) -> tuple[str, bool]:
        """Strip any stray json/memory blocks if present."""
        import re
        pattern = r'```(?:ella_memory|json)?\s*\n(.*?)\n```'
        clean_response = re.sub(pattern, '', response, flags=re.DOTALL).strip()
        return clean_response, False



    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            log.debug("Memory database closed")
