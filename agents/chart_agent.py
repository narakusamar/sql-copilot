"""
Chart Agent: 推荐图表类型 + 生成 Plotly 图表
"""
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.llm import call_llm

SUPPORTED_CHARTS = ["bar", "line", "pie", "scatter", "area", "horizontal_bar"]

ADVISOR_SYSTEM = """你是数据可视化专家。根据查询结果的数据特征（列名、类型、样本），推荐 2-3 种合适的图表类型。

## 图表选择原则
- bar: 柱状图，适合分类对比数值，如"各城市的销售额"
- horizontal_bar: 横向柱状图，适合分类标签较长的情况
- line: 折线图，适合时间序列趋势，如"每月销售额变化"
- pie: 饼图，适合展示占比，分类数不超过 8 个
- scatter: 散点图，适合两个数值字段的相关性分析
- area: 面积图，类似折线图但强调数量累积

## 输出格式
{"charts": [{"type": "bar", "title": "各城市销售额", "x": "City", "y": "Sales", "reason": "柱状图适合对比各城市销售额"}]}"""


def _serialize_data(columns: list[str], rows: list[tuple], max_rows: int = 5) -> str:
    """将数据转为 LLM 友好的文本"""
    lines = [f"列名: {', '.join(columns)}"]
    lines.append(f"总行数: {len(rows)}")
    lines.append("示例数据:")
    for i, row in enumerate(rows[:max_rows]):
        lines.append(f"  {dict(zip(columns, row))}")
    return "\n".join(lines)


def _infer_types(columns: list[str], rows: list[tuple]) -> dict[str, str]:
    """推断每列的数据类型"""
    types = {}
    for i, col in enumerate(columns):
        values = [row[i] for row in rows if row[i] is not None]
        if not values:
            types[col] = "unknown"
        elif all(isinstance(v, (int, float)) for v in values):
            types[col] = "numeric"
        else:
            types[col] = "categorical"
    return types


def recommend_charts(columns: list[str], rows: list[tuple], question: str) -> list[dict]:
    """推荐图表类型，返回图表配置列表"""
    if not rows:
        return []

    data_desc = _serialize_data(columns, rows)
    col_types = _infer_types(columns, rows)
    num_cols = [c for c, t in col_types.items() if t == "numeric"]
    cat_cols = [c for c, t in col_types.items() if t == "categorical"]

    prompt = f"""数据列类型: {col_types}

数据详情:
{data_desc}

用户原始问题: {question}

请推荐合适的图表类型，必选返回合法 JSON:"""

    try:
        response = call_llm(prompt, system=ADVISOR_SYSTEM)
    except Exception:
        return _fallback_charts(columns, rows, num_cols, cat_cols)
    try:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]
        result = json.loads(response)
        charts = result.get("charts", [])
        for chart in charts:
            chart.setdefault("x", cat_cols[0] if cat_cols else columns[0])
            chart.setdefault("y", num_cols[0] if num_cols else columns[-1])
        return charts
    except (json.JSONDecodeError, ValueError, KeyError):
        return _fallback_charts(columns, rows, num_cols, cat_cols)


def _fallback_charts(columns, rows, num_cols, cat_cols) -> list[dict]:
    """LLM 解析失败时的兜底推荐"""
    charts = []
    if cat_cols and num_cols:
        charts.append({
            "type": "bar", "title": f"各{cat_cols[0]}的{num_cols[0]}",
            "x": cat_cols[0], "y": num_cols[0],
            "reason": "柱状图适合分类对比"
        })
    if len(num_cols) >= 2:
        charts.append({
            "type": "scatter", "title": f"{num_cols[0]} vs {num_cols[1]}",
            "x": num_cols[0], "y": num_cols[1],
            "reason": "散点图适合展示两个数值字段的关系"
        })
    return charts


def generate_chart(chart_config: dict, columns: list[str], rows: list[tuple]) -> go.Figure:
    """根据配置生成 Plotly 图表"""
    chart_type = chart_config.get("type", "bar")
    title = chart_config.get("title", "Chart")
    x_col = chart_config.get("x", columns[0] if columns else "x")
    y_col = chart_config.get("y", columns[-1] if len(columns) > 1 else columns[0])

    df = {col: [row[i] for row in rows] for i, col in enumerate(columns)}

    if chart_type == "bar":
        fig = px.bar(df, x=x_col, y=y_col, title=title)
    elif chart_type == "horizontal_bar":
        fig = px.bar(df, x=y_col, y=x_col, title=title, orientation='h')
    elif chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col, title=title, markers=True)
    elif chart_type == "pie":
        fig = px.pie(df, names=x_col, values=y_col, title=title)
    elif chart_type == "scatter":
        fig = px.scatter(df, x=x_col, y=y_col, title=title)
    elif chart_type == "area":
        fig = px.area(df, x=x_col, y=y_col, title=title)
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=title)

    fig.update_layout(template="plotly_white", height=450)
    return fig


def generate_dashboard(charts: list[dict], columns: list[str], rows: list[tuple]) -> go.Figure:
    """多图拼接成大屏"""
    n = len(charts)
    if n == 0:
        return go.Figure()
    if n == 1:
        return generate_chart(charts[0], columns, rows)

    cols = min(2, n)
    row_count = (n + cols - 1) // cols
    specs = [[{"type": "domain"} if c["type"] == "pie" else {"type": "xy"}
              for c in charts[i*cols:(i+1)*cols]]
             for i in range(row_count)]
    # 补齐不足 cols 的行
    for spec_row in specs:
        while len(spec_row) < cols:
            spec_row.append(None)
    fig = make_subplots(rows=row_count, cols=cols,
                        subplot_titles=[c.get("title", "") for c in charts],
                        specs=specs)

    for i, chart in enumerate(charts):
        r = i // cols + 1
        c = i % cols + 1
        sub = generate_chart(chart, columns, rows)
        for trace in sub.data:
            fig.add_trace(trace, row=r, col=c)

    fig.update_layout(template="plotly_white", height=400 * row_count,
                      title_text="数据大屏", showlegend=False)
    return fig
