# backend/services/conversation_store.py

import logging
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class ConversationStore:
    """
    Handles reading and writing conversation history to MongoDB.

    Each conversation = one session.
    Messages are appended as the conversation progresses.
    On logout, status is set to 'closed'.
    On login, last N conversations are returned to show history.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def get_or_create(self, session_id: str, user_id: str) -> dict:
        """
        Get existing conversation for this session or create a new one.
        Called at the start of each chat request.
        """
        existing = await self._db.conversations.find_one(
            {"session_id": session_id}
        )
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        doc = {
            "session_id":  session_id,
            "user_id":     ObjectId(user_id),
            "messages":    [],
            "status":      "active",
            "created_at":  now,
            "last_active": now,
        }
        result = await self._db.conversations.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def append_turn(
        self,
        session_id:    str,
        user_message:  str,
        bot_reply:     str,
        tool_calls:    list = [],
    ) -> None:
        """
        Append one user + assistant message pair to the conversation.
        Called after every successful agent response.
        """
        now = datetime.now(timezone.utc)
        messages_to_add = [
            {
                "role":       "user",
                "content":    user_message,
                "timestamp":  now,
            },
            {
                "role":       "assistant",
                "content":    bot_reply,
                "timestamp":  now,
                "tool_calls": [t.tool_name for t in tool_calls],
            },
        ]

        await self._db.conversations.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": {"$each": messages_to_add}},
                "$set":  {"last_active": now, "status": "active"},
            }
        )

    async def close_session(self, session_id: str) -> None:
        """Mark conversation as closed when user logs out."""
        await self._db.conversations.update_one(
            {"session_id": session_id},
            {"$set": {"status": "closed"}}
        )

    async def get_history(self, user_id: str, limit: int = 5) -> list:
        try:
            uid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        except Exception:
            return []

        cursor = self._db.conversations.find(
            {"user_id": uid},
            {"messages": 1, "created_at": 1, "last_active": 1, "session_id": 1}
        ).sort("last_active", -1).limit(limit)

        conversations = []
        async for conv in cursor:
            conversations.append({
                "session_id":  conv["session_id"],
                "created_at":  conv["created_at"].isoformat(),
                "last_active": conv["last_active"].isoformat(),
                "messages": [
                    {
                        "role":      m["role"],
                        "content":   m["content"],
                        "timestamp": m["timestamp"].isoformat(),
                    }
                    for m in conv.get("messages", [])
                ]
            })

        return conversations