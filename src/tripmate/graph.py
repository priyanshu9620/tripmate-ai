"""Phase 0 graph: a single assistant node. Later phases replace this with the supervisor + 4 agents."""

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph


def build_graph(model: BaseChatModel, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    def assistant(state: MessagesState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("assistant", assistant)
    g.add_edge(START, "assistant")
    g.add_edge("assistant", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
