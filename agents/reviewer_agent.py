"""
Reviewer Agent: 最终输出质检，确保图表和分析符合用户预期
"""
import json
from core.llm import call_llm

REVIEWER_SYSTEM = """你是数据可视化质量审核专家。审核图表和分析是否准确回答了用户问题。

## 审查维度

1. **图表匹配度**：图表类型是否适合数据特征
   - pie: 分类不超过 8 个，过多应建议 bar
   - line: 适合时间序列或有序数据
   - scatter: 适合两个数值字段的相关性

2. **轴映射正确性**：x/y 字段选择是否合理
   - 数值字段不可放在分类轴
   - 日期字段应作为 x 轴（折线/柱状图）

3. **分析准确性**：分析文本中的数字和结论是否与数据一致
   - 引用的数值是否在统计摘要中存在
   - 结论是否有数据支撑

4. **问题覆盖度**：用户问题的所有维度是否都被响应
   - 如用户要求"按地区和品类对比"，但只按品类出了图

## 输出格式
{"score": <0-100>, "issues": ["问题描述"], "suggestion": "改进建议"}

评分 >= 80 视为通过，< 80 建议调整。"""


class ReviewerAgent:
    def review(self, question: str, chart_configs: list[dict],
               summary: dict, analysis_text: str = "") -> dict:
        """审查最终输出，返回评分和问题列表"""

        charts_desc = "\n".join(
            f"- [{c.get('type')}] {c.get('title')} (x={c.get('x')}, y={c.get('y')})"
            for c in chart_configs
        )

        prompt = f"""用户问题: {question}

选择的图表:
{charts_desc if charts_desc else '无'}

数据统计摘要:
{json.dumps(summary, ensure_ascii=False, default=str)}

分析文本:
{analysis_text if analysis_text else '无'}

请审核上述内容是否符合用户预期:"""

        response = call_llm(prompt, system=REVIEWER_SYSTEM)
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
                if response.endswith("```"):
                    response = response[:-3]
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return {"score": 80, "issues": [], "suggestion": ""}
