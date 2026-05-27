"""
LA Review Agent — access-rights reconciliation via LLM-driven tools.
"""
import json
import os
from typing import Annotated

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from src.storage.memory_saver import get_memory_saver
from src.tools.ingest_files import ingest_files
from src.tools.classify_tables import classify_tables
from src.tools.analyze_access import analyze_access_reconciliation

LLM_CONFIG = "config/agent_llm_config.json"

MAX_MESSAGES = 40


def _windowed_messages(old, new):
    """Sliding window: keep only the most recent MAX_MESSAGES messages."""
    return add_messages(old, new)[-MAX_MESSAGES:]


class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]


def build_agent():
    """Build the LA Review agent with tools for access reconciliation."""

    config_path = os.path.join(os.getcwd(), LLM_CONFIG)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", cfg["config"].get("model", "gpt-4o"))

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=cfg["config"].get("temperature", 0.3),
        streaming=True,
        timeout=cfg["config"].get("timeout", 600),
    )

    tools_list = [
        ingest_files,
        classify_tables,
        analyze_access_reconciliation,
    ]

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=tools_list,
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )
