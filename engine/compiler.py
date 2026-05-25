from core.llm import call_llm
from core.utils import strip_markdown


class SQLCompiler:
    def fix_sql(self, sql: str, error: str, schema: str = "") -> str:
        schema_section = f"\n数据库结构:\n{schema}" if schema else ""
        prompt = f"""你是 SQLite SQL 修复专家。根据报错信息修复 SQL 语句。

{schema_section}

原始 SQL:
{sql}

报错信息:
{error}

## 修复规则
1. 只返回修复后的 SQL，不要任何解释和 markdown 标记
2. 字段名必须与数据库结构中的完全一致
3. 常见错误：[表名不存在/字段名拼写错误/缺少引号/语法错误/类型不匹配]
4. 如果错误无法修复，返回原始 SQL
"""
        return strip_markdown(call_llm(prompt))
