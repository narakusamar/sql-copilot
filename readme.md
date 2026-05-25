# SQL Copilot

自然语言查询数据库的 Multi-Agent 系统。输入问题，自动生成 SQL、审查、执行，支持交互式可视化与数据分析解读。

## 架构

```
用户输入
   │
   ▼
Router（意图路由）
   │
   ├─ QUERY ────────────────────────────────────┐
   │  Planner（复杂问题拆解）                      │
   │     │                                        │
   │     ▼                                        │
   │  SQLAgent                                    │
   │  ├─ Schema Agent     → 筛选相关表/字段        │
   │  ├─ Memory           → embedding 语义召回     │
   │  ├─ LLM              → 生成 SQL              │
   │  ├─ Critic Agent     → 5 维评分（<70 重生成） │
   │  ├─ Executor         → 执行查询               │
   │  └─ Compiler         → 自动修复（最多 3 轮）  │
   │     │                                        │
   │     ▼                                        │
   │  结果（表格 + CSV/Excel 导出）                │
   │                                              │
   └─ VIZ ──────────────────────────────────────┐
      SQLAgent（同上）                            │
         │                                        │
         ▼                                        │
      ChartAdvisor  → 推荐 2-3 种图表类型         │
         │                                        │
         ▼                                        │
      ChartGenerator → Plotly 单图 / 大屏        │
         │                                        │
         ▼                                        │
      Analyst Agent  → 数据洞察（可选）           │
         │                                        │
         ▼                                        │
      Reviewer Agent → 最终质检（4 维度评分）     │
```

## 快速开始

### 环境要求

- Python 3.10+
- SQLite（默认），可选 MySQL / PostgreSQL

### 安装

```bash
pip install -r requirements.txt
```

国内用户可使用清华镜像加速：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 配置

```bash
cp core/config.example.env core/config.env
# 编辑 core/config.env 填入你的 API Key 等配置
```

启动 Web UI 后也可在侧边栏 **设置** 面板中直接修改（即时生效，无需重启）。

### 初始化数据库

```bash
python init_db.py
```

### 运行

```bash
# Web UI
streamlit run ui.py

# CLI
python main.py
```

## Agent 说明

| Agent | 文件 | 职责 |
|-------|------|------|
| **Router** | `engine/router.py` | 意图路由：QUERY / INSERT / VIZ / OTHER |
| **Planner** | `agents/planner_agent.py` | 复杂问题拆解为子任务 |
| **SQLAgent** | `agents/sql_agent.py` | 核心调度：生成 → 审查 → 执行 → 修复 |
| **Schema Agent** | `agents/schema_agent.py` | 从全量 schema 筛选相关表/字段，减少 token |
| **Memory** | `core/memory.py` | Embedding 语义相似度召回历史 SQL 作为 few-shot |
| **Critic Agent** | `agents/critic_agent.py` | 5 维评分，<70 分触发自动重生成 |
| **Compiler** | `engine/compiler.py` | 根据报错 + schema 上下文修复 SQL |
| **ChartAgent** | `agents/chart_agent.py` | 图表推荐（ChartAdvisor）+ Plotly 生成（ChartGenerator） |
| **Analyst** | `agents/analyst_agent.py` | 统计摘要 + LLM 数据洞察 |
| **Reviewer** | `agents/reviewer_agent.py` | 最终质检：图表匹配度 / 轴映射 / 分析准确性 / 问题覆盖度 |

## 核心机制

### SQL 生命周期

1. **Schema 筛选**：表结构超过 600 字符时，Schema Agent 自动裁剪无关表/字段
2. **记忆召回**：`text2vec-base-chinese` 中文模型（768 维向量），余弦相似度检索历史成功 SQL
3. **LLM 生成**：注入 schema + few-shot 示例 + 对话上下文
4. **Critic 审查**：语法正确性、字段存在性、逻辑正确性、安全性（除零/NULL）、完整性
5. **自动修复**：执行失败时 Compiler 根据报错修复，最多重试 3 轮

### 可视化流程

1. **推荐**：分析列名、数据类型和样本数据，推荐 2-3 种图表（bar / line / pie / scatter / area / horizontal_bar）
2. **选择**：勾选图表类型，可选大屏报表（多图拼接）
3. **生成**：Plotly 交互图表，支持缩放、悬停详情
4. **分析**：统计摘要（max / min / avg / sum / 占比）+ LLM 中文解读
5. **质检**：Reviewer 4 维审核，≥80 分通过

### 多轮对话

维护对话历史（问题 + SQL + 结果摘要），后续查询注入上文。支持模糊追问：

```
> 查询各品类销售额
[返回 Furniture: 741,999, Office Supplies: 719,047, Technology: 836,154]

> 那技术类呢？
→ 自动理解为 WHERE Category = 'Technology'，复用上轮 SQL 结构
```

### 多数据源

| 数据库 | 驱动 | 配置 |
|--------|------|------|
| SQLite | 内置 | `DB_TYPE=sqlite` `DB_PATH=xxx.db` |
| MySQL | pymysql | `DB_TYPE=mysql` `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` |
| PostgreSQL | psycopg2 | `DB_TYPE=postgresql` `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` |

在 UI 设置面板中切换后即时生效，无需重启。

## 项目结构

```
sql-copilot/
├── core/
│   ├── config.py          # 配置读取
│   ├── config.env         # 环境变量（UI 可编辑）
│   ├── llm.py             # LLM 调用封装（OpenAI 兼容接口）
│   ├── memory.py          # Embedding 语义检索
│   └── utils.py           # 通用工具函数
├── agents/
│   ├── sql_agent.py       # 核心 Agent
│   ├── planner_agent.py   # 任务规划
│   ├── schema_agent.py    # Schema 筛选
│   ├── critic_agent.py    # SQL 审查
│   ├── chart_agent.py     # 图表推荐 + 生成
│   ├── analyst_agent.py   # 数据分析
│   └── reviewer_agent.py  # 最终质检
├── engine/
│   ├── executor.py        # 多数据库执行器
│   ├── compiler.py        # SQL 自动修复
│   ├── router.py          # 意图路由
│   └── exporter.py        # CSV/Excel 导出
├── prompts/
│   └── sql_prompt.txt     # SQL 生成模板
├── init_db.py             # 数据库初始化
├── main.py                # CLI 入口
├── ui.py                  # Streamlit Web UI
├── run.sh                 # 启动脚本
└── requirements.txt
```

## 使用示例

### 普通查询

```
> 查询销售额最高的5个城市
[Router: QUERY]

Generated SQL:
SELECT City, SUM(Sales) AS "总销售额"
FROM superstore
GROUP BY City
ORDER BY SUM(Sales) DESC
LIMIT 5;

Critic Score: 100/100
  - SQL 语法正确，字段名与 DDL 完全一致

OK (attempt 1)
共 5 条结果:
  New York City    256,368.16
  Los Angeles      175,851.27
  Seattle          119,540.74
  San Francisco    112,669.09
  Philadelphia     109,077.01
```

### 复杂问题拆解

```
> 对比家具类和技术类的利润率差异
[Router: QUERY]
Planner 拆解为 2 个子任务:
  1. 查询家具类产品的总利润和总收入，计算利润率
  2. 查询技术类产品的总利润和总收入，计算利润率

Generated SQL:
SELECT
    Category,
    SUM(Profit) / NULLIF(SUM(Sales), 0) AS "利润率"
FROM superstore
WHERE Category IN ('Furniture', 'Technology')
GROUP BY Category

Critic Score: 95/100
  - 逻辑正确，已使用 NULLIF 防止除零

OK
Furniture:    2.49%
Technology:   17.40%
```



### 可视化

```
> 各品类销售额对比
[Router: VIZ]

图表推荐:
  [bar] 各品类销售额对比 — 柱状图适合对比各品类销售额数值
  [pie] 各品类销售额占比 — 饼图适合展示占比

用户勾选 bar + pie → 点击"生成图表"

质检 95/100 通过

分析解读:
  Technology 品类以 836,154 的销售额位居第一，占比约 36.4%，
  显著领先于 Furniture（742,000）和 Office Supplies（719,047）。
  后两者差距仅约 3.2%，竞争较为激烈。
```

### 多轮追问

```
> 查询各城市的销售额
[返回 3 个城市]

> 只看前 3 个
[自动将 LIMIT 5 → LIMIT 3]

> 按利润再排一下
[自动将 ORDER BY Sales → ORDER BY Profit，并追加 Profit 列]
```
## 效果展示
```
![demo1](https://github.com/user-attachments/assets/c2a036b6-1561-42e4-adb8-3363c7dd98b9)

![demo2](https://github.com/user-attachments/assets/0caec8c2-ce34-454f-929a-a1d49320cf48)

![demo3](https://github.com/user-attachments/assets/8cc9cf86-033c-486f-b435-bbbcd40f1b76)

```
## 命令

| 命令 | 说明 |
|------|------|
| `/quit` `/exit` `/q` | 退出 |
| `/memory` | 查看历史成功查询记录 |

## 依赖

| 包 | 用途 |
|----|------|
| openai | LLM API 调用 |
| streamlit | Web UI |
| plotly | 交互图表 |
| sentence-transformers | Embedding 语义检索 |
| numpy | 向量计算 |
| openpyxl | Excel 导出 |
| python-dotenv | 环境变量管理 |
