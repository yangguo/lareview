import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


def get_memory_saver() -> BaseCheckpointSaver:
    logger.info("Using MemorySaver as checkpointer")
    return MemorySaver()
