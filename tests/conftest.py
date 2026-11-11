import os

os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ["LANGSMITH_TRACING"] = "false"  # never burn the trace quota on unit tests
