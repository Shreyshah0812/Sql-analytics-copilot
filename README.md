# 🧠 SQL + Analytics Copilot

A production-quality AI copilot that converts plain English into SQL, runs queries, auto-charts results, and explains them like a senior data analyst.

Built for **data analyst portfolio projects** — maps directly to real DA workflows.

---

## 📸 What it does

1. **Connect** to a sample SQLite DB or upload your own CSV
2. **Ask** a question in plain English
3. **Get back:**
   - ✅ Generated SQL (transparent, editable)
   - ✅ Query results table (downloadable)
   - ✅ Auto chart (line, bar, scatter, KPI card)
   - ✅ Analyst-style explanation with assumptions + pitfalls
4. **Auto-fix** — if SQL errors, Claude rewrites and retries automatically
5. **Follow-up questions** — multi-turn context (ask "now break it down by country")

---

## 🏗️ Architecture

```
User (Streamlit UI)
        ↕
    app.py  ← orchestration layer
        ↕
  utils/llm.py  ← Claude API (sql_gen → sql_fix → explain)
        ↕
utils/guardrails.py  ← safety validation
        ↕
  utils/db.py  ← SQLite or DuckDB (CSV) execution
        ↕
 utils/charts.py  ← auto Plotly chart selection
        ↕
utils/validators.py  ← data quality checks
```

---

## 🚀 Setup

### 1. Clone & install

```bash
git clone <your-repo>
cd sql-analytics-copilot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run

```bash
streamlit run app.py
```

The sample DB is auto-seeded on first run. No setup needed.

---

## 💡 Example questions to try

| Question | What it demonstrates |
|---|---|
| "Revenue trend by month" | Time series line chart |
| "Top 10 customers by total spend" | Bar chart + ranking |
| "Revenue by country" | Category aggregation |
| "Average order value" | KPI card |
| "Which genres are most popular?" | Join across tables |
| "Now break it down by year" | Follow-up / multi-turn |

---

## 🛡️ Safety features

- Blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `PRAGMA`, `ATTACH`
- Enforces `LIMIT 1000` max to prevent runaway queries
- Auto-adds `LIMIT 100` if missing
- Rejects queries that don't start with `SELECT` or `WITH`

---

## 📁 Project structure

```
sql-analytics-copilot/
  app.py                  ← Main Streamlit app
  requirements.txt
  .env.example
  db/
    sample.db             ← Auto-seeded Chinook-style DB
  prompts/
    sql_gen.txt           ← NL → SQL system prompt
    sql_fix.txt           ← Error correction prompt
    sql_explain.txt       ← Result explanation prompt
  metrics/
    kpis.yaml             ← Business KPI definitions
  utils/
    db.py                 ← Schema extraction + query execution
    llm.py                ← Claude API calls
    guardrails.py         ← SQL safety validation
    charts.py             ← Auto chart selection (Plotly)
    validators.py         ← Post-query data quality checks
```

---

## 🔧 Extending it

| Feature | Where to add |
|---|---|
| Connect to Postgres | `utils/db.py` — swap SQLite for `psycopg2` |
| Add more KPIs | `metrics/kpis.yaml` |
| Tune SQL rules | `prompts/sql_gen.txt` |
| Add more chart types | `utils/charts.py` |
| Add auth | Wrap `app.py` with `streamlit-authenticator` |

---

## ⚠️ Limitations

- Read-only queries only (by design)
- SQL dialect: SQLite (for file DB) or DuckDB SQL (for CSV uploads)
- LLM may hallucinate if schema is very large (>50 tables) — use schema filtering
- Multi-file CSV joins not yet supported

---

## 📄 License

MIT
