# backend/core/container.py

import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.tools.mongo_tools import get_all_tools
from backend.services.groq_service import GroqService
from backend.policies.file_store import FilePolicyStore
from backend.services.conversation_store import ConversationStore

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, db: AsyncIOMotorDatabase):
        logger.info("Initialising container...")

        tools             = get_all_tools(db)
        self.groq         = GroqService(tools)
        self.policy       = FilePolicyStore()
        self.conversations = ConversationStore(db)

        logger.info(
            f"Container ready — "
            f"{len(tools)} tools loaded, "
            f"policy store: {self.policy.__class__.__name__}"
        )


_container = None


def init_container(db: AsyncIOMotorDatabase) -> None:
    global _container
    _container = Container(db)
    logger.info("Container initialised.")


def get_container():
    if _container is None:
        raise RuntimeError("Container not initialised.")
    return _container