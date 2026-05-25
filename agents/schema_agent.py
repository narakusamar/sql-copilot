"""
Schema Agent: 从数据库中检索与用户问题相关的表和字段
"""
from core.llm import call_llm


class SchemaAgent:
    def retrieve_relevant_schema(self, question: str, full_schema: str) -> str:
        """用 LLM 从全量 schema 中筛选与问题相关的部分，减少 token 消耗"""
        prompt = f"""以下是数据库的全部表结构:

{full_schema}

用户问题: {question}

## 筛选原则
1. 保留与问题关键词直接相关的表和字段（包括用于 JOIN 的外键）
2. 保留用于排序、分组的字段
3. 去掉与问题完全无关的表
4. 如果只有一个表，保留该表的所有字段即可
5. 输出完整的相关表 DDL（CREATE TABLE 语句），不要输出其他内容"""

        return call_llm(prompt, system="你是数据库专家。根据用户问题从全量 schema 中筛选相关表和字段，只输出相关 DDL。")
