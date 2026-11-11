"""Bounded tool-calling loop: model ↔ tools until the model stops calling tools or max_steps is hit."""

from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool


@dataclass
class LoopResult:
    final: AIMessage
    tool_results: list[dict] = field(default_factory=list)  # {"name", "args", "result"}
    steps: int = 0
    usage: dict = field(default_factory=lambda: {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0})
    transcript: list[BaseMessage] = field(default_factory=list)


def _usage_of(msg: AIMessage) -> dict:
    u = msg.usage_metadata or {}
    return {
        "llm_calls": 1,
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
    }


def run_tool_loop(
    model: BaseChatModel, tools: list[BaseTool], system: str, history: list[BaseMessage], max_steps: int = 6
) -> LoopResult:
    by_name = {t.name: t for t in tools}
    bound = model.bind_tools(tools)
    if not history:
        # some providers (Gemini) reject a request whose only content is the system prompt
        history = [HumanMessage(content="Go.")]
    msgs: list[BaseMessage] = [SystemMessage(content=system), *history]
    res = LoopResult(final=AIMessage(content=""))
    for step in range(max_steps):
        ai: AIMessage = bound.invoke(msgs)
        for k, v in _usage_of(ai).items():
            res.usage[k] += v
        msgs.append(ai)
        res.transcript.append(ai)
        res.steps = step + 1
        if not ai.tool_calls:
            res.final = ai
            return res
        for call in ai.tool_calls:
            tool = by_name.get(call["name"])
            if tool is None:
                out = {"ok": False, "error": f"unknown tool {call['name']}"}
            else:
                out = tool.invoke(call["args"])
            res.tool_results.append({"name": call["name"], "args": call["args"], "result": out})
            tm = ToolMessage(content=_dumps(out), tool_call_id=call["id"], name=call["name"])
            msgs.append(tm)
            res.transcript.append(tm)
    res.final = AIMessage(content="(tool loop hit the step limit)")
    return res


def _dumps(obj: object) -> str:
    import json

    return json.dumps(obj, default=str)
