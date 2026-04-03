# backend/policies/file_store.py

import json
import logging
from pathlib import Path

from backend.core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()


class FilePolicyStore:
    """
    Keyword-filtered policy file loader.

    On init:
        - Reads manifest.json
        - Loads always_load files immediately (they're in every prompt)

    On build_context(user_message):
        - Scores on_topic files against user message keywords
        - Returns top 3 matches + always_load as one combined string
    """

    def __init__(self):
        self._base     = Path(settings.knowledge_base_dir)
        self._manifest = self._load_manifest()
        self._always   = self._load_always_files()
        logger.info(
            f"FilePolicyStore ready — "
            f"{len(self._always)} always-load files, "
            f"{len(self._manifest.get('on_topic', []))} on-topic files"
        )

    # ── Public ─────────────────────────────────────────────────────────────────

    def build_context(self, user_message: str) -> str:
        """
        Build the full knowledge context string for this user message.
        Called once per request in the agent to build the system prompt.
        """
        on_topic = self._score_and_select(user_message)
        sections = self._always + on_topic

        context = "\n\n---\n\n".join(sections)
        logger.debug(
            f"Policy context built — "
            f"{len(self._always)} always + {len(on_topic)} on-topic files"
        )
        return context

    # ── Private ────────────────────────────────────────────────────────────────

    def _load_manifest(self) -> dict:
        manifest_path = Path(settings.knowledge_manifest_path)
        if not manifest_path.exists():
            logger.warning(f"Manifest not found at {manifest_path} — using empty config")
            return {"always_load": [], "on_topic": []}
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_always_files(self) -> list[str]:
        """Load all always_load files at startup — cached in memory."""
        contents = []
        for entry in self._manifest.get("always_load", []):
            content = self._read_file(entry["file"])
            if content:
                contents.append(content)
        return contents

    def _score_and_select(self, user_message: str, top_n: int = 3) -> list[str]:
        """
        Score each on_topic file against the user message.
        Score = number of keywords from the file's keyword list
                that appear in the lowercased user message.
        Returns content of top_n files with score > 0,
        ordered by (score desc, priority asc).
        Falls back to fallback files if nothing matches.
        """
        message_lower = user_message.lower()
        scored        = []

        for entry in self._manifest.get("on_topic", []):
            keywords = [kw.lower() for kw in entry.get("keywords", [])]
            score    = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                scored.append((score, entry.get("priority", 99), entry))

        # Sort: highest score first, then lowest priority number first
        scored.sort(key=lambda x: (-x[0], x[1]))
        top = [entry for _, _, entry in scored[:top_n]]

        # Fallback if nothing matched
        if not top:
            top = self._get_fallback_entries()

        return [c for c in (self._read_file(e["file"]) for e in top) if c]

    def _get_fallback_entries(self) -> list[dict]:
        fallback_files = self._manifest.get("fallback_if_no_topic_match", [])
        on_topic_map   = {
            e["file"]: e
            for e in self._manifest.get("on_topic", [])
        }
        return [on_topic_map[f] for f in fallback_files if f in on_topic_map]

    def _read_file(self, relative_path: str) -> str | None:
        full_path = self._base / relative_path
        if not full_path.exists():
            logger.warning(f"Knowledge file not found: {full_path}")
            return None
        try:
            content = full_path.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning(f"Knowledge file is empty: {full_path}")
                return None
            return content
        except Exception as e:
            logger.error(f"Failed to read {full_path}: {e}")
            return None