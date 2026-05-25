"""
Router: 判断用户问题类型，路由到不同处理流程
"""
from core.llm import call_llm

ROUTER_SYSTEM = """你是路由决策专家。判断用户输入的类型，只输出一个单词。

## 类型判定规则
- QUERY: 查询数据、统计汇总、排名、筛选、对比分析、计算
- INSERT: 插入、添加、新增、录入数据
- VIZ: 明确要求画图、图表、可视化、柱状图、折线图、饼图
- OTHER: 闲聊、问候、纯 SQL 语法问题、与数据库无关的问题

## 边界示例
"帮我查一下上个月的销售额" → QUERY
"对比一下各品类的利润率" → QUERY
"给我画一个销售趋势图" → VIZ
"新增一条客户记录" → INSERT
"你好" → OTHER
"SQL里JOIN和LEFT JOIN有什么区别" → OTHER"""


class Router:
    def route(self, question: str) -> str:
        response = call_llm(question, system=ROUTER_SYSTEM)
        import re
        result = response.strip().upper()
        # 提取第一个有效路由词，去除标点和多余内容
        for word in result.split():
            word = re.sub(r"[^A-Z]", "", word)
            if word in ("QUERY", "INSERT", "VIZ", "OTHER"):
                return word
        return "QUERY"  # 默认走查询流程
