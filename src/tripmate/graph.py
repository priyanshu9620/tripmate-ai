"""Supervisor graph: intake → researcher → planner → budgeter → approval (interrupt) → booker.

Every node sets `phase`; the supervisor (`route`) is a pure function of the state, so routing is unit-testable
without an LLM. A new human message always enters through `intake`, which merges it into the constraints."""

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from tripmate.agents.nodes import Nodes, route
from tripmate.agents.state import TripState


def build_graph(
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
    prefs_loader=None,
    prefs_saver=None,
) -> CompiledStateGraph:
    n = Nodes(model, prefs_loader, prefs_saver)
    g = StateGraph(TripState)
    g.add_node("intake", n.intake)
    g.add_node("researcher", n.researcher)
    g.add_node("planner", n.planner)
    g.add_node("budgeter", n.budgeter)
    g.add_node("approval", n.approval)
    g.add_node("booker", n.booker)
    g.add_edge(START, "intake")
    for node in ("intake", "researcher", "planner", "budgeter", "approval"):
        g.add_conditional_edges(node, route)
    g.add_edge("booker", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


AGENTS = ("intake", "researcher", "planner", "budgeter", "approval", "booker")
