from langchain_openai import ChatOpenAI

from app.settings import settings

# 事実の言い換えと構造化しかさせないので, ばらつきは不要
TEMPERATURE = 0.2

# 壁打ちの応答性を壊さない上限
TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

gpt_4_1_mini = ChatOpenAI(
    model="gpt-4.1-mini",
    api_key=settings.OPENAI_API_KEY,
    temperature=TEMPERATURE,
    timeout=TIMEOUT_SECONDS,
    max_retries=MAX_RETRIES,
)

gpt_4o_mini = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
    temperature=TEMPERATURE,
    timeout=TIMEOUT_SECONDS,
    max_retries=MAX_RETRIES,
)

chatgpt = gpt_4_1_mini.with_fallbacks([gpt_4o_mini])
