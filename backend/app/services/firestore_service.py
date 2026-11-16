"""Firestore integration for persistent session logs, alerts, and challenges."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings

log = logging.getLogger("voiceguard.firestore")

_client = None
_initialized = False
_in_memory_sessions: List[Dict[str, Any]] = []
_in_memory_alerts: List[Dict[str, Any]] = []


def get_db():
    """Get or initialize Firestore client singleton."""
    global _client, _initialized
    if _initialized:
        return _client

    settings = get_settings()
    cred_path = Path(settings.firebase_credentials)
    if not cred_path.is_absolute():
        backend_dir = Path(__file__).resolve().parents[2]
        cred_path = backend_dir / cred_path

    if cred_path.is_file():
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
            _client = firestore.client()
            _initialized = True
            log.info("Firestore connected successfully to project: %s", _client.project)
            return _client
        except Exception as e:
            log.warning("Failed to initialize Firestore with key (%s): %s. Falling back to memory.", cred_path, e)
    else:
        log.info("No serviceAccountKey found at %s. Using in-memory fallback.", cred_path)

    _initialized = True
    return None


def save_session(session_data: Dict[str, Any]) -> str:
    """Save a call session record to Firestore sessions collection."""
    db = get_db()
    data = {
        **session_data,
        "timestamp": session_data.get("timestamp", int(time.time() * 1000)),
        "created_at_epoch": time.time(),
    }
    if db is not None:
        try:
            doc_ref = db.collection("sessions").document(session_data.get("session_id", str(time.time())))
            doc_ref.set(data, merge=True)
            return doc_ref.id
        except Exception as e:
            log.error("Firestore write session error: %s", e)

    # In-memory fallback
    _in_memory_sessions.insert(0, data)
    if len(_in_memory_sessions) > 100:
        _in_memory_sessions.pop()
    return session_data.get("session_id", "local")


def get_recent_sessions(limit_count: int = 25) -> List[Dict[str, Any]]:
    """Retrieve recent session records."""
    db = get_db()
    if db is not None:
        try:
            from google.cloud import firestore
            docs = (
                db.collection("sessions")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit_count)
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            log.error("Firestore read sessions error: %s", e)

    return _in_memory_sessions[:limit_count]


def save_alert(alert_data: Dict[str, Any]) -> str:
    """Save an alert event to Firestore alerts collection."""
    db = get_db()
    data = {
        **alert_data,
        "timestamp": alert_data.get("timestamp", int(time.time() * 1000)),
    }
    if db is not None:
        try:
            doc_ref = db.collection("alerts").document()
            doc_ref.set(data)
            return doc_ref.id
        except Exception as e:
            log.error("Firestore write alert error: %s", e)

    _in_memory_alerts.insert(0, data)
    if len(_in_memory_alerts) > 100:
        _in_memory_alerts.pop()
    return "local"


def get_recent_alerts(limit_count: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent alerts."""
    db = get_db()
    if db is not None:
        try:
            from google.cloud import firestore
            docs = (
                db.collection("alerts")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit_count)
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            log.error("Firestore read alerts error: %s", e)

    return _in_memory_alerts[:limit_count]
