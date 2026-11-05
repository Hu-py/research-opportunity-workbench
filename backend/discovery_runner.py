"""Compatibility entrypoint: all discovery decisions are delegated to the LLM pipeline."""
from backend.llm_discovery import execute_llm_discovery


def execute_discovery(factory, run_id, client=None):
    """Run LLM query planning, scholarly retrieval, and semantic screening."""
    return execute_llm_discovery(factory, run_id, client=client)
