from langchain_core.messages import HumanMessage

from tripmate.graph import build_graph
from tripmate.llm import EchoChatModel


def test_one_node_graph_replies_and_keeps_thread_history():
    g = build_graph(EchoChatModel())
    cfg = {"configurable": {"thread_id": "t1"}}
    g.invoke({"messages": [HumanMessage(content="hello")]}, config=cfg)
    out = g.invoke({"messages": [HumanMessage(content="again")]}, config=cfg)
    assert out["messages"][-1].text == "echo: again"
    assert len(out["messages"]) == 4  # 2 human + 2 ai, persisted per thread


def test_threads_are_isolated():
    g = build_graph(EchoChatModel())
    g.invoke({"messages": [HumanMessage(content="a")]}, config={"configurable": {"thread_id": "x"}})
    out = g.invoke({"messages": [HumanMessage(content="b")]}, config={"configurable": {"thread_id": "y"}})
    assert len(out["messages"]) == 2
