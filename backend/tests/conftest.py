import os

# app.llm.openai_gpt が import 時に ChatOpenAI を構築するため, キーが無いと収集段階で落ちる
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@127.0.0.1:1/test")
