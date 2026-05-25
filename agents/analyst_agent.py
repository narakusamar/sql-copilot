"""
Analyst Agent: 对查询结果和图表进行文字分析
"""
import statistics
from core.llm import call_llm

ANALYST_SYSTEM = """你是数据分析师。根据统计摘要和图表信息，用中文给出简洁的数据洞察。

## 要求
1. 2-4 句话，点出最关键的趋势、异常值或对比结论
2. 引用具体数值
3. 不要复述数据，要给出解读
4. 使用中文"""


def summarize_data(columns: list[str], rows: list[tuple]) -> dict:
    """计算统计摘要"""
    if not rows:
        return {}
    summary = {"row_count": len(rows)}
    for i, col in enumerate(columns):
        values = [row[i] for row in rows if row[i] is not None]
        if not values:
            continue
        if all(isinstance(v, (int, float)) for v in values):
            summary[col] = {
                "max": round(max(values), 2),
                "min": round(min(values), 2),
                "avg": round(statistics.mean(values), 2),
                "sum": round(sum(values), 2),
            }
        else:
            unique = list(dict.fromkeys(values))
            summary[col] = {
                "unique_count": len(unique),
                "top3": unique[:3],
            }
    return summary


def analyze(chart_configs: list[dict], columns: list[str],
            rows: list[tuple], question: str) -> str:
    """生成数据分析文字"""
    if not rows:
        return "数据为空，无法分析。"

    summary = summarize_data(columns, rows)

    prompt = f"""用户问题: {question}

图表信息: {[c.get('title', '') + ' (' + c.get('type', '') + ')' for c in chart_configs]}

统计摘要: {summary}

请给出数据分析洞察:"""

    return call_llm(prompt, system=ANALYST_SYSTEM)
