import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.tools.mongo_tools import get_all_tools
from backend.tools.pg_tools import get_all_pg_tools
from backend.services.groq_service import GroqService
from backend.policies.file_store import FilePolicyStore
from backend.services.conversation_store import ConversationStore
from backend.database_pg import SessionLocal
import backend.database_pg as pg_db
from backend.core.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()
class Container:
    def __init__(self, db):
        logger.info("Initialising container...")

        if settings.db_tool_mode == "mongo":
            tools = get_all_tools(db)
            self.conversations = ConversationStore(db=db)
            logger.info(f"Mongo tools loaded: {len(tools)}")
        elif settings.db_tool_mode == "postgres":
            tools = get_all_pg_tools(pg_db.SessionLocal)
            self.conversations = ConversationStore(db=None, session_factory=pg_db.SessionLocal)
        else:
            tools = []
            self.conversations = ConversationStore(db=None)
            logger.warning(f"Unknown DB_TOOL_MODE: {settings.db_tool_mode} — no tools loaded.")

        self.groq   = GroqService(tools)
        self.policy = FilePolicyStore()

        logger.info(f"Container ready — {len(tools)} tools loaded")


_container = None


def init_container(db: AsyncIOMotorDatabase) -> None:
    global _container
    _container = Container(db)
    logger.info("Container initialised.")


def get_container():
    if _container is None:
        raise RuntimeError("Container not initialised.")
    return _container