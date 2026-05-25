import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.sql_agent import SQLAgent, build_context
from agents.planner_agent import PlannerAgent
from agents.chart_agent import recommend_charts, generate_chart, generate_dashboard
from agents.analyst_agent import analyze
from engine.router import Router
from core.memory import Memory


def print_divider(char="=", width=60):
    print(char * width)


def print_section(title: str, char="─", width=50):
    print(f"\n{char * 5} {title} {char * 5}")


def handle_query(question: str, sql_agent: SQLAgent, memory: Memory,
                 context: str, history: list, planner: PlannerAgent):
    tasks = planner.plan(question)
    if len(tasks) == 1:
        sql, result = sql_agent.run(question, context)
        if result is not None:
            print_divider()
            print(f"共 {len(result)} 条结果:")
            for row in result[:20]:
                print(row)
            if len(result) > 20:
                print(f"... 以及 {len(result) - 20} 条")
            memory.save(question, sql, success=True)
            cols, _, _ = sql_agent.executor.run_with_columns(sql)
            history.append({"question": question, "sql": sql,
                           "columns": cols, "result": result})
        else:
            print("查询失败，请重试。")
            memory.save(question, sql, success=False)
    else:
        print(f"\nPlanner 拆解为 {len(tasks)} 个子任务:")
        for i, task in enumerate(tasks, 1):
            print(f"  {i}. {task}")
        print()
        for i, task in enumerate(tasks, 1):
            print_section(f"子任务 {i}/{len(tasks)}: {task}")
            sql, result = sql_agent.run(task, context)
            if result is not None:
                print(f"共 {len(result)} 条结果")
                for row in result[:10]:
                    print(row)
                memory.save(task, sql, success=True)
            else:
                print(f"子任务 {i} 查询失败")
                memory.save(task, sql, success=False)


def handle_viz(question: str, sql_agent: SQLAgent, memory: Memory,
               context: str, history: list):
    sql, result = sql_agent.run(question, context)
    if result is None or len(result) == 0:
        print("查询无结果，无法生成图表。")
        return

    columns, _, _ = sql_agent.executor.run_with_columns(sql)
    if not columns:
        print("无法获取列名。")
        return

    memory.save(question, sql, success=True)
    history.append({"question": question, "sql": sql,
                   "columns": columns, "result": result})

    charts = recommend_charts(columns, result, question)
    if not charts:
        print("无法推荐合适的图表类型。")
        return

    print_divider()
    print("推荐以下图表类型:\n")
    for i, c in enumerate(charts, 1):
        print(f"  [{i}] {c['type']}: {c.get('reason', '')}")
    print(f"  [0] 全部（大屏报表）")
    print(f"  [q] 跳过")

    choice = input("\n选择图表编号: ").strip()
    if choice.lower() == 'q':
        return

    selected = []
    if choice == '0':
        selected = charts
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(charts):
                selected = [charts[idx]]
        except ValueError:
            print("无效选择，跳过。")
            return

    if not selected:
        return

    output_dir = Path(__file__).parent / "charts"
    output_dir.mkdir(exist_ok=True)

    if len(selected) == 1:
        chart = selected[0]
        fig = generate_chart(chart, columns, result)
        path = output_dir / f"chart_{chart['type']}.html"
        fig.write_html(str(path))
        print(f"\n图表已保存: {path}")
    else:
        fig = generate_dashboard(selected, columns, result)
        path = output_dir / "dashboard.html"
        fig.write_html(str(path))
        print(f"\n大屏已保存: {path}")

    print()
    if input("需要数据分析解读吗? (y/n): ").strip().lower() == 'y':
        print("\n生成分析...")
        try:
            text = analyze(selected, columns, result, question)
            print_divider()
            print(text)
        except Exception as e:
            print(f"分析失败: {e}")


if __name__ == "__main__":
    memory = Memory()
    sql_agent = SQLAgent(memory=memory)
    planner = PlannerAgent()
    history: list[dict] = []

    print("\n SQL Copilot")
    print("输入问题查询数据库，输入 /quit 退出，输入 /memory 查看历史\n")

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question:
            continue
        if question.lower() in ("/quit", "/exit", "/q"):
            print("Bye!")
            break
        if question.lower() == "/memory":
            rows = memory.recall_similar("")
            if rows:
                for i, (q, s) in enumerate(rows, 1):
                    print(f"{i}. Q: {q}\n   SQL: {s}")
            else:
                print("暂无记忆")
            continue

        try:
            route = Router().route(question)
            print(f"[Router: {route}]")
        except Exception as e:
            print(f"Router 失败: {e}")
            continue

        context = build_context(history)

        try:
            if route == "QUERY":
                handle_query(question, sql_agent, memory, context, history, planner)

            elif route == "VIZ":
                handle_viz(question, sql_agent, memory, context, history)

            elif route == "INSERT":
                print("该功能尚未实现，请先手动操作数据库。")

            else:
                print("抱歉，我目前只能回答数据库查询相关的问题。")
        except Exception as e:
            print(f"处理失败: {e}")
