"""Thin provider-agnostic JSON client for OpenAI / Gemini. Keys come only from backend env."""
from __future__ import annotations

import json
import logging
import re
import time

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ApiUsage, Workspace

log = logging.getLogger("app.ai")


class AIUnavailable(Exception):
    """AI disabled, misconfigured, timed out, or returned unusable output."""


def effective_provider(ws: Workspace | None = None) -> str | None:
    p = (ws.settings or {}).get("ai_provider") if ws else None
    p = (p or settings.AI_PROVIDER or "none").lower()
    if p == "openai" and settings.OPENAI_API_KEY:
        return "openai"
    if p == "gemini" and settings.GEMINI_API_KEY:
        return "gemini"
    return None


def ai_status(ws: Workspace | None = None) -> dict:
    prov = effective_provider(ws)
    return {
        "enabled": prov is not None,
        "provider": prov,
        "configured_provider": ((ws.settings or {}).get("ai_provider") if ws else None) or settings.AI_PROVIDER,
        "model": (settings.OPENAI_MODEL if prov == "openai" else settings.GEMINI_MODEL) if prov else None,
        "mode": "ai" if prov else "offline",
        "label": f"TARA · {prov}" if prov else "TARA · offline deterministic mode (no AI key configured)",
    }


def _parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if not m:
            raise AIUnavailable("TARA returned output that is not valid JSON")
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            raise AIUnavailable("TARA returned malformed JSON")
    if not isinstance(data, dict):
        raise AIUnavailable("TARA returned JSON that is not an object")
    return data


def generate_json(db: Session, ws: Workspace, system: str, user: str, kind: str) -> dict:
    prov = effective_provider(ws)
    if not prov:
        raise AIUnavailable("No AI provider configured")
    start = time.perf_counter()
    ok = False
    try:
        with httpx.Client(timeout=settings.AI_TIMEOUT_SECONDS) as client:
            if prov == "openai":
                r = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={
                        "model": settings.OPENAI_MODEL,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
            else:
                r = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
                    headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                    },
                )
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = _parse_json(text)
        ok = True
        return data
    except httpx.TimeoutException:
        raise AIUnavailable(f"TARA timed out after {settings.AI_TIMEOUT_SECONDS}s")
    except httpx.HTTPStatusError as e:
        raise AIUnavailable(f"AI provider returned HTTP {e.response.status_code}")
    except httpx.HTTPError as e:
        raise AIUnavailable(f"Could not reach AI provider: {type(e).__name__}")
    except (KeyError, IndexError, TypeError):
        raise AIUnavailable("Unexpected response shape from AI provider")
    finally:
        ms = (time.perf_counter() - start) * 1000
        db.add(ApiUsage(workspace_id=ws.id, provider=prov, kind=kind, tokens_est=(len(system) + len(user)) // 4, latency_ms=round(ms, 1), ok=ok))
        db.flush()
