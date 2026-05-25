import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agents.sql_agent import SQLAgent, build_context
from agents.planner_agent import PlannerAgent
from agents.chart_agent import recommend_charts, generate_chart, generate_dashboard
from agents.analyst_agent import analyze, summarize_data
from agents.reviewer_agent import ReviewerAgent
from engine.router import Router
from core.memory import Memory

st.set_page_config(page_title="SQL Copilot", page_icon=":bar_chart:", layout="wide")


def init_session():
    if "memory" not in st.session_state:
        st.session_state.memory = Memory()
    if "sql_agent" not in st.session_state:
        st.session_state.sql_agent = SQLAgent(memory=st.session_state.memory)
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "router" not in st.session_state:
        st.session_state.router = Router()
    if "planner" not in st.session_state:
        st.session_state.planner = PlannerAgent()
    if "reviewer" not in st.session_state:
        st.session_state.reviewer = ReviewerAgent()
    if "history" not in st.session_state:
        st.session_state.history = []


def score_color(score: int) -> str:
    if score >= 80:
        return ":green"
    elif score >= 70:
        return ":orange"
    return ":red"


def run_query(question: str):
    agent = st.session_state.sql_agent
    memory = st.session_state.memory
    router = st.session_state.router
    planner = st.session_state.planner

    msg = {"question": question, "route": "", "tasks": []}
    st.session_state.messages.append(msg)

    try:
        route = router.route(question)
    except Exception as e:
        msg["error"] = f"Router 失败: {e}"
        return
    msg["route"] = route

    if route in ("INSERT", "OTHER"):
        msg["error"] = "该功能尚未实现" if route == "INSERT" else "抱歉，我目前只能回答数据库查询相关的问题。"
        return

    context = build_context(st.session_state.history)

    try:
        tasks = planner.plan(question)
    except Exception as e:
        msg["error"] = f"Planner 失败: {e}"
        return
    if len(tasks) == 1:
        tasks = [question]

    for i, task in enumerate(tasks):
        task_data = {"task": task, "sql": "", "score": None, "issues": [],
                     "regenerated_sql": "", "result": None, "error": None,
                     "columns": [], "attempt": 0}

        from core.config import Config

        try:
            sql = agent.generate_sql(task, context)
            task_data["sql"] = sql

            schema = agent._get_schema(task)
            review = agent.critic.review(sql, task, schema)
            task_data["score"] = review.get("score", 0)
            task_data["issues"] = review.get("issues", [])

            if task_data["score"] < 70:
                suggestion = review.get("suggestion", "")
                sql = agent.regenerate_with_feedback(task, sql, suggestion, context)
                task_data["regenerated_sql"] = sql

            for attempt in range(1, Config.MAX_RETRIES + 1):
                cols, result, error = agent.executor.run_with_columns(sql)
                task_data["attempt"] = attempt
                if error is None:
                    task_data["result"] = result
                    task_data["columns"] = cols
                    task_data["error"] = None
                    try:
                        memory.save(task, sql, success=True)
                    except Exception:
                        pass
                    st.session_state.history.append({
                        "question": task, "sql": sql,
                        "columns": cols, "result": result
                    })
                    break
                task_data["error"] = error
                if attempt < Config.MAX_RETRIES:
                    sql = agent.compiler.fix_sql(sql, error, schema=schema)
                    task_data["sql"] = sql
        except Exception as e:
            task_data["error"] = str(e)

        msg["tasks"].append(task_data)


def save_config(updates: dict):
    """将配置变更写入 config.env"""
    from pathlib import Path
    config_path = Path(__file__).parent / "core" / "config.env"
    if not config_path.exists():
        config_path.write_text("", encoding="utf-8")
    lines = config_path.read_text(encoding="utf-8").split("\n")
    result = []
    written = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            result.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in updates:
                result.append(f"{key}={updates[key]}")
                written.add(key)
                continue
        result.append(line)
    for key, val in updates.items():
        if key not in written:
            result.append(f"{key}={val}")
    config_path.write_text("\n".join(result) + "\n", encoding="utf-8")


# --- UI ---
init_session()

with st.sidebar:
    st.header("SQL Copilot")
    st.caption("自然语言 → SQL → 结果")

    st.divider()

    from core.config import Config
    try:
        executor = st.session_state.sql_agent.executor
        tables = executor.get_tables()
        label = Config.DB_PATH.split("/")[-1] if Config.DB_TYPE == "sqlite" else Config.DB_NAME
        st.metric("数据库", label)
        st.caption(f"类型: {Config.DB_TYPE}  |  表: {len(tables)} 张")
        st.success("已连接")
    except Exception as e:
        st.error(f"连接失败: {e}")

    st.divider()

    # ── 设置面板 ──
    with st.expander("设置", expanded=False):
        with st.form("settings_form"):
            st.caption("API 配置")
            api_key = st.text_input(
                "API Key",
                value=Config.API_KEY, type="password",
                help="LLM API 密钥。DeepSeek: https://platform.deepseek.com/api_keys")
            base_url = st.text_input(
                "Base URL",
                value=Config.BASE_URL,
                help="API 地址。DeepSeek: https://api.deepseek.com/v1 / OpenAI: https://api.openai.com/v1")
            model = st.text_input(
                "Model",
                value=Config.MODEL,
                help="模型名称。如 deepseek-chat / gpt-4o / qwen-plus")
            max_retries = st.number_input(
                "Max Retries", min_value=1, max_value=10,
                value=Config.MAX_RETRIES,
                help="SQL 执行失败时的最大自动修复次数")

            st.caption("数据库配置")
            db_type = st.selectbox(
                "数据库类型",
                options=["sqlite", "mysql", "postgresql"],
                index=["sqlite", "mysql", "postgresql"].index(
                    Config.DB_TYPE) if Config.DB_TYPE in [
                        "sqlite", "mysql", "postgresql"] else 0,
                help="SQLite: 本地文件 / MySQL: 需安装 pymysql / PostgreSQL: 需安装 psycopg2")

            if db_type == "sqlite":
                db_path = st.text_input(
                    "数据库路径",
                    value=Config.DB_PATH,
                    help="SQLite 文件路径，如 superstore.db 或 /data/mydb.sqlite")
            else:
                db_host = st.text_input(
                    "Host", value=Config.DB_HOST,
                    help="数据库服务器地址，如 localhost 或 192.168.1.100")
                db_port = st.number_input(
                    "Port", value=Config.DB_PORT, min_value=1,
                    help="MySQL 默认 3306，PostgreSQL 默认 5432")
                db_user = st.text_input(
                    "User", value=Config.DB_USER,
                    help="数据库用户名")
                db_pwd = st.text_input(
                    "Password", value=Config.DB_PASSWORD,
                    type="password", help="数据库密码（留空表示无密码）")
                db_name = st.text_input(
                    "Database", value=Config.DB_NAME,
                    help="要连接的数据库名")

            st.caption("其他")
            hf_endpoint = st.text_input(
                "HF Endpoint",
                value=Config.HF_ENDPOINT,
                help="HuggingFace 镜像地址。国内用户建议 https://hf-mirror.com")

            if st.form_submit_button("保存配置", type="primary",
                                    use_container_width=True):
                updates = {
                    "API_KEY": api_key, "BASE_URL": base_url,
                    "MODEL": model, "MAX_RETRIES": str(max_retries),
                    "DB_TYPE": db_type, "HF_ENDPOINT": hf_endpoint,
                }
                if db_type == "sqlite":
                    updates["DB_PATH"] = db_path
                else:
                    updates["DB_HOST"] = db_host
                    updates["DB_PORT"] = str(db_port)
                    updates["DB_USER"] = db_user
                    updates["DB_PASSWORD"] = db_pwd
                    updates["DB_NAME"] = db_name
                save_config(updates)
                Config.reload()
                for key in ("sql_agent", "memory"):
                    st.session_state.pop(key, None)
                st.rerun()

    st.divider()

    st.subheader("历史查询")
    try:
        rows = st.session_state.memory.recall_similar("", limit=20)
        if rows:
            for q, _ in rows[-10:]:
                if st.button(q[:50] + ("..." if len(q) > 50 else ""),
                             key=f"hist_{q}"):
                    st.session_state._pending_question = q
                    st.rerun()
    except Exception:
        st.caption("暂无记录")

    st.divider()

    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()


def render_viz_ui(msg: dict):
    """VIZ 消息：勾选图表 → 确认生成 → 显示（生成后锁定选择）"""
    tasks = msg.get("tasks", [])
    if not tasks:
        return

    task = tasks[0]
    result = task.get("result")
    columns = task.get("columns", [])

    if not result:
        st.warning("查询无结果，无法生成图表。")
        return

    charts = recommend_charts(columns, result, msg["question"])
    if not charts:
        st.warning("无法推荐合适的图表类型。")
        return

    chart_key = f"fig_{id(msg)}"
    generated = chart_key in st.session_state

    if st.session_state.get(f"skip_{id(msg)}"):
        return

    if not generated:
        st.subheader("图表推荐")
        st.caption("勾选要生成的图表，可多选")

        selected = []
        for i, chart in enumerate(charts):
            col1, col2 = st.columns([0.05, 0.95])
            with col1:
                checked = st.checkbox(
                    "", key=f"sel_{id(msg)}_{i}",
                    help=chart.get("reason", ""))
            with col2:
                st.markdown(
                    f"**{chart['type']}** — {chart.get('reason', '')}")
            if checked:
                selected.append(chart)

        include_dashboard = st.checkbox(
            "包含大屏报表（多图拼接）", key=f"dash_{id(msg)}")

        col_btn, col_skip = st.columns([1, 3])
        with col_btn:
            if st.button("生成图表", type="primary",
                         use_container_width=True,
                         disabled=not selected and not include_dashboard):
                if include_dashboard and len(charts) >= 1:
                    selected = charts if not selected else selected
                if selected:
                    if len(selected) == 1:
                        fig = generate_chart(selected[0], columns, result)
                    else:
                        fig = generate_dashboard(selected, columns, result)
                    st.session_state[chart_key] = fig
                    st.session_state[f"sel_charts_{id(msg)}"] = selected
                    st.rerun()
        with col_skip:
            if st.button("跳过", key=f"skip_viz_{id(msg)}",
                         use_container_width=True):
                st.session_state[f"skip_{id(msg)}"] = True
                st.rerun()
    else:
        # 已生成，展示图表 + 锁定选择
        sel_charts = st.session_state.get(f"sel_charts_{id(msg)}", charts)
        st.subheader(f"图表 ({len(sel_charts)} 个)")
        fig = st.session_state[chart_key]
        st.plotly_chart(fig, use_container_width=True)

        show_analysis = st.checkbox("数据分析解读",
                                    key=f"analysis_cb_{id(msg)}")
        analysis_text = ""
        if show_analysis:
            cache_key = f"analysis_{id(msg)}"
            if cache_key not in st.session_state:
                with st.spinner("分析中..."):
                    try:
                        st.session_state[cache_key] = analyze(
                            sel_charts, columns, result, msg["question"])
                    except Exception as e:
                        st.session_state[cache_key] = f"分析失败: {e}"
            analysis_text = st.session_state[cache_key]
            st.info(analysis_text)

        # Reviewer 质检
        review_cache_key = f"review_{id(msg)}"
        if review_cache_key not in st.session_state:
            summary = summarize_data(columns, result)
            try:
                st.session_state[review_cache_key] = st.session_state.reviewer.review(
                    msg["question"], sel_charts, summary, analysis_text)
            except Exception as e:
                st.session_state[review_cache_key] = {
                    "score": 0, "issues": [f"质检失败: {e}"], "suggestion": ""}
        review = st.session_state[review_cache_key]
        score = review.get("score", 0)
        if score >= 80:
            st.success(f"质检通过 ({score}/100)")
        else:
            with st.expander(f"质检 {score}/100 — 建议调整"):
                for issue in review.get("issues", []):
                    st.caption(f"- {issue}")
                if review.get("suggestion"):
                    st.caption(f"建议: {review['suggestion']}")


def render_query_ui(msg: dict):
    """渲染 QUERY 类型的结果"""
    tasks = msg.get("tasks", [])
    if not tasks:
        return

    if len(tasks) > 1:
        st.caption(f"Planner 拆解为 {len(tasks)} 个子任务")

    for ti, task in enumerate(tasks):
        label = f"子任务 {ti + 1}: {task['task']}" if len(tasks) > 1 else "SQL 生成"
        with st.expander(label, expanded=(len(tasks) == 1)):
            st.code(task["sql"], language="sql")

            if task["score"] is not None:
                color = score_color(task["score"])
                st.markdown(f"Critic Score: {color}[**{task['score']}/100**]")
                for issue in task.get("issues", []):
                    st.caption(f"  - {issue}")

            if task.get("regenerated_sql"):
                st.caption("根据反馈重新生成:")
                st.code(task["regenerated_sql"], language="sql")

            if task.get("attempt"):
                st.caption(f"执行尝试: {task['attempt']}")

            if task.get("result") is not None:
                rows = task["result"]
                columns = task.get("columns", [])
                if rows:
                    if not columns:
                        columns = [f"col{i}" for i in range(len(rows[0]))]
                    st.dataframe(
                        [dict(zip(columns, row)) for row in rows],
                        use_container_width=True, hide_index=True)

                    # 导出按钮
                    c1, c2, c3 = st.columns([1, 1, 6])
                    from engine.exporter import export_csv, export_excel, default_filename
                    csv_data = export_csv(columns, rows)
                    c1.download_button("CSV", csv_data,
                                       file_name=f"{default_filename()}.csv",
                                       mime="text/csv", use_container_width=True,
                                       key=f"csv_{id(msg)}_{ti}")
                    try:
                        xlsx_data = export_excel(columns, rows)
                        c2.download_button("Excel", xlsx_data,
                                           file_name=f"{default_filename()}.xlsx",
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                           use_container_width=True,
                                           key=f"xlsx_{id(msg)}_{ti}")
                    except ImportError:
                        c2.caption("需安装 openpyxl")

                    c3.caption(f"共 {len(rows)} 条结果")
                else:
                    st.caption("查询无结果")

            if task.get("error"):
                st.error(task["error"])


# Main
st.title("SQL Copilot")

for msg in st.session_state.messages:
    with st.chat_message("user"):
        st.markdown(msg["question"])

    with st.chat_message("assistant"):
        route = msg.get("route", "")
        if route:
            st.caption(f"Router: {route}")

        if msg.get("error"):
            st.warning(msg["error"])
            continue

        if route == "VIZ":
            render_viz_ui(msg)
        else:
            render_query_ui(msg)

# Input
pending = st.session_state.pop("_pending_question", None)
question = st.chat_input("输入问题查询数据库...")

if pending and not question:
    question = pending

if question:
    q = question.strip()
    if not q:
        st.stop()
    if q.lower() in ("/quit", "/exit", "/q"):
        st.stop()
    if q.lower() == "/memory":
        with st.chat_message("assistant"):
            rows = st.session_state.memory.recall_similar("", limit=20)
            if rows:
                for qi, (q_text, sql) in enumerate(rows, 1):
                    st.markdown(f"**{qi}.** {q_text}")
                    st.code(sql, language="sql")
            else:
                st.caption("暂无记忆")
    else:
        with st.spinner("处理中..."):
            run_query(q)
        st.rerun()
