def strip_markdown(text: str) -> str:
    """去掉 LLM 可能包裹的 ```sql ... ``` 标记"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) == 1:
            # ```SELECT 3 — 无换行，直接去掉开头的 ```
            text = text[3:].strip()
        else:
            # ```\n...\n``` 或 ```sql\n...\n```
            lines = lines[1:]  # 去掉 ``` 或 ```sql 行
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
    return text
