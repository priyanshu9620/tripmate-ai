import os

os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("DATABASE_URL", "postgresql://tm:tm@127.0.0.1:1/tripmate")  # unreachable on purpose
