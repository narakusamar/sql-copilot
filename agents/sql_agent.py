from pathlib import Path
from core.llm import call_llm
from core.config import Config
from core.utils import strip_markdown
from engine.executor import SQLExecutor
from engine.compiler import SQLCompiler
from agents.schema_agent import SchemaAgent
from agents.critic_agent import CriticAgent

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_CRITIC_THRESHOLD = 70


def build_context(history: list[dict], max_turns: int = 3) -> str:
    """将对话历史转为 LLM 可理解的上下文文本"""
    if not history:
        return "（暂无对话上下文）"
    parts = []
    for i, turn in enumerate(history[-max_turns:]):
        q = turn.get("question", "")
        sql = turn.get("sql", "")
        cols = turn.get("columns", [])
        rows = turn.get("result", [])
        parts.append(f"第{i+1}轮:\n  问题: {q}\n  SQL: {sql}")
        if cols and rows:
            sample = ", ".join(
                str(dict(zip(cols, row))) for row in rows[:3])
            parts.append(f"  结果示例: {sample}")
    return "\n".join(parts)


class SQLAgent:
    def __init__(self, memory=None):
        self.executor = SQLExecutor()
        self.compiler = SQLCompiler()
        self.schema_agent = SchemaAgent()
        self.critic = CriticAgent()
        self.memory = memory

    def _get_schema(self, question: str) -> str:
        full_schema = self.executor.get_schema()
        if len(full_schema) < 600:
            return full_schema
        return self.schema_agent.retrieve_relevant_schema(question, full_schema)

    def _get_examples(self, question: str) -> str:
        if self.memory is None:
            return "（暂无历史记录）"
        rows = self.memory.recall_similar(question, limit=3)
        if not rows:
            return "（暂无相似历史记录）"
        return "\n\n".join(f"问题: {q}\nSQL: {sql}" for q, sql in rows)

    def generate_sql(self, question: str, context: str = "") -> str:
        template = (_PROMPT_DIR / "sql_prompt.txt").read_text(encoding="utf-8")
        template = template.replace("{schema}", self._get_schema(question))
        template = template.replace("{examples}", self._get_examples(question))
        template = template.replace("{context}", context)
        template = template.replace("{question}", question)
        return strip_markdown(call_llm(template))

    def regenerate_with_feedback(self, question: str, old_sql: str,
                                  feedback: str, context: str = "") -> str:
        prompt = f"""你是 SQLite SQL 专家。根据审查反馈修复以下 SQL。

原始问题: {question}

原始 SQL:
{old_sql}

审查反馈:
{feedback}

对话上下文:
{context}

数据库结构:
{self._get_schema(question)}

历史参考:
{self._get_examples(question)}

只输出修复后的 SQL，不要任何解释和 markdown 标记。"""
        return strip_markdown(call_llm(prompt))

    def run(self, question: str, context: str = ""):
        # 1. 生成 SQL
        sql = self.generate_sql(question, context)
        print("\nGenerated SQL:")
        print(sql)

        # 2. Critic 审查
        schema = self._get_schema(question)
        review = self.critic.review(sql, question, schema)
        score = review.get("score", 0)
        issues = review.get("issues", [])
        print(f"\nCritic Score: {score}/100")
        if issues:
            for issue in issues:
                print(f"  - {issue}")

        # 3. 分数低则用反馈重生成
        if score < _CRITIC_THRESHOLD:
            suggestion = review.get("suggestion", "")
            print(f"\nScore < {_CRITIC_THRESHOLD}, 根据反馈重新生成...")
            sql = self.regenerate_with_feedback(question, sql, suggestion, context)
            print(f"\nRegenerated SQL:\n{sql}")

        # 4. 执行 + 自动修复
        for attempt in range(1, Config.MAX_RETRIES + 1):
            result, error = self.executor.run(sql)
            if error is None:
                print(f"\nOK (attempt {attempt})")
                return sql, result

            print(f"\nExecution failed (attempt {attempt}/{Config.MAX_RETRIES}): {error}")
            if attempt < Config.MAX_RETRIES:
                sql = self.compiler.fix_sql(sql, error, schema=self._get_schema(question))
                print(f"Fixed SQL:\n{sql}")

        return sql, result
