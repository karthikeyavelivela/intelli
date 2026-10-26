"""Checks that your OpenAI or Gemini key works with TARA.  Run from the project folder AFTER you have set the key in .env:

    python scripts/verify_ai_key.py

It sends one tiny request (a few tokens, costs a fraction of a paisa) and prints PASS or what went wrong.
Nothing is saved: the usage row it creates is rolled back.  With no key set it simply says TARA is in offline mode."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Workspace  # noqa: E402
from app.services.ai import AIUnavailable, ai_status, generate_json  # noqa: E402


def main() -> int:
    with SessionLocal() as db:
        ws = db.query(Workspace).first()
        status = ai_status(ws)
        print(f"Configured provider : {settings.AI_PROVIDER}")
        print(f"TARA mode           : {status['label']}")
        if not status["enabled"]:
            print("\nNo usable key found. Set AI_PROVIDER=openai and OPENAI_API_KEY=... (or gemini and GEMINI_API_KEY=...) in .env,")
            print("then run this again. (python -m app.seed must have been run once so a workspace exists.)")
            return 0 if ws else 1
        try:
            out = generate_json(db, ws, 'Reply with JSON only: {"ok": true, "word": "<any single word>"}', "Say hello.", "key-check")
        except AIUnavailable as e:
            print(f"\nFAIL: {e}")
            print("Common causes: wrong or expired key, no credit left on the provider account, model name not available to your key, no internet.")
            return 1
        finally:
            db.rollback()
        print(f"\nPASS: {status['provider']} ({status['model']}) answered: {out}")
        print("Restart the back end, open Ask TARA, and the label will read 'TARA · " + status["provider"] + "'.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
