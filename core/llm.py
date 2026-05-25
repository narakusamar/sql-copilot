from openai import OpenAI
from core.config import Config


def _get_client() -> OpenAI:
    """延迟创建 client，确保始终使用最新配置"""
    return OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL, timeout=30.0)


def call_llm(
    prompt: str,
    system: str = "You are a SQL expert.",
    temperature: float = 0,
    model: str | None = None,
) -> str:
    """统一 LLM 调用入口，每个 Agent 可独立指定 model"""
    use_model = model or Config.MODEL
    client = _get_client()

    def _request(sys: str, usr: str) -> str:
        response = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": usr},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content

    try:
        return _request(system, prompt)
    except UnicodeEncodeError:
        safe_system = system.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
        safe_prompt = prompt.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
        return _request(safe_system, safe_prompt)
