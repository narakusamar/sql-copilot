"""
Critic Agent: 对生成的 SQL 进行评分和审查
"""
import json
from core.llm import call_llm

CRITIC_SYSTEM = """你是 SQL 审查专家。对生成的 SQL 进行严格审查，输出 JSON。

## 评审维度（按重要性排序）

1. **语法正确性**：SQLite 语法是否正确，关键字拼写有无错误
2. **字段/表存在性**：引用的表名和字段名是否在 DDL 中存在，名称是否完全一致
3. **逻辑正确性**：SQL 是否真正回答了用户问题，WHERE/JOIN/GROUP BY 条件是否合理
4. **安全性**：计算结果是否准确（如比率计算、聚合逻辑），有无除零风险
5. **完整性**：是否遗漏了用户问题中的关键条件，边界情况（NULL、空结果集）是否处理

## 评分标准

- 95-100：完全正确，无任何问题
- 85-94：基本正确，有微小改进空间（如别名、格式）
- 70-84：存在小问题（如缺少 NULL 处理、字段名不完全匹配）
- 50-69：存在明显逻辑错误或使用了不存在的字段
- 0-49：SQL 完全错误或无法执行

## 输出格式
{"score": <0-100>, "issues": ["具体问题，引用 DDL 中的字段名作为证据"], "suggestion": "一句话修复建议"}"""


class CriticAgent:
    def review(self, sql: str, question: str, schema: str) -> dict:
        prompt = f"""表结构:
{schema}

用户问题: {question}

待审查 SQL:
{sql}

请评分并指出问题，必须返回合法 JSON:"""
        response = call_llm(prompt, system=CRITIC_SYSTEM)
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
                if response.endswith("```"):
                    response = response[:-3]
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return {
                "score": 80,
                "issues": ["评审结果格式异常，跳过审查"],
                "suggestion": "",
            }
