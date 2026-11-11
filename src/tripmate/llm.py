"""Provider-agnostic chat model factory. `fake` needs no key and is deterministic (tests, load bench)."""

from collections.abc import Sequence
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from tripmate.config import settings


class EchoChatModel(BaseChatModel):
    """Deterministic stand-in for an LLM: replies with the last human message."""

    @property
    def _llm_type(self) -> str:
        return "echo"

    def _generate(
        self,
        messages: Sequence[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        text = f"echo: {last_human.text}" if last_human else "echo: (nothing)"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def get_model(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    provider = provider or settings.llm_provider
    model = model or settings.llm_model
    if provider == "fake":
        return EchoChatModel()
    return init_chat_model(model, model_provider=provider, temperature=0)
