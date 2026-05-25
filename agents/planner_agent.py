"""
Intent Planner: 分析复杂问题，拆解为可执行的 SQL 子任务
"""
from core.llm import call_llm

PLANNER_SYSTEM = """你是任务规划专家。将用户对数据库的问题拆解为具体的查询子任务。

## 规则
- 简单问题（单步查询即可完成）只输出一行子任务，不要硬拆
- 对比/排名/趋势/分组对比类问题，拆解为多个独立的查询步骤
- 每行一个子任务，用自然语言描述需要查询什么数据
- 不要输出 SQL，只描述查询目标和条件

## 示例
用户: 查询销售额最高的5个城市
输出: 1. 按城市汇总销售额，降序排列取前5

用户: 对比家具类和技术类的利润率差异
输出:
1. 查询家具类产品的总利润和总收入，计算利润率
2. 查询技术类产品的总利润和总收入，计算利润率

## 输出格式
1. [子任务1描述]
2. [子任务2描述]"""


class PlannerAgent:
    def plan(self, question: str) -> list[str]:
        response = call_llm(
            f"用户问题: {question}\n请拆解为子任务:",
            system=PLANNER_SYSTEM,
        )
        tasks = []
        for line in response.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("- ")):
                task = line.lstrip("0123456789. )- 、，").strip()
                if task:
                    tasks.append(task)
        if not tasks:
            return [question]
        return tasks
