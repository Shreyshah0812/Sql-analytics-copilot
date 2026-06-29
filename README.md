# DataMind — AI Analytics Copilot

**Ask your data questions in plain English. Get SQL, results, charts, and an analyst-style explanation back.**

DataMind is an AI copilot that turns natural-language questions into validated SQL, runs them against a database or an uploaded CSV, auto-selects the right chart, and explains the result the way a data analyst would — including the assumptions and pitfalls behind the number.

🔗 **Live demo:** https://datamind-shrey.streamlit.app/
💻 **Code:** https://github.com/Shreyshah0812/Sql-analytics-copilot

> Built to mirror a real data-analyst workflow: ask → query → validate → visualize → interpret.

---

## Why this is interesting (the engineering, not the buzzwords)

Most "text-to-SQL" demos stop at generating a query. The harder, more realistic problems are everything *around* the generation — and that's where most of the work here went:

- **A safety layer that assumes the model can be wrong.** Generated SQL never touches the database until it passes a guardrail check: SELECT/CTE-only, a blocklist of mutating keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, …) matched as whole words, and an enforced row `LIMIT` so a careless query can't run away.
- **A self-correcting query loop.** If a query fails at execution, the error is fed back to the model with the schema and original question to produce a corrected query, which is then re-validated and retried — so a single malformed query doesn't dead-end the user.
- **Post-query data-quality checks.** After results come back, the app runs analyst sanity checks and surfaces warnings the user would otherwise miss: high null rates, likely many-to-many join explosions, duplicate keys (double-counting risk), extreme outliers, and mixed-grain time dimensions.
- **Context-aware chart selection.** A decision engine picks from 12 chart types based on the *shape* of the result — time series → line, ranking → horizontal bar, part-of-whole → donut/treemap, geographic → choropleth, two metrics → scatter with trendline, and so on.
- **Multi-turn follow-ups.** Conversation history is passed back to the model, so "now break it down by country" works without restating the question.

---

## What it does

1. **Load data** — use the built-in sample music-store database, or upload your own CSV.
2. **See an instant overview** — row/column counts, data types, null percentages per column, and a preview, before you ask anything.
3. **Ask in plain English** — "revenue trend by month", "top 10 customers by spend", "which genres are most popular?"
4. **Get back, in tabs:**
   - the generated SQL (transparent and inspectable)
   - the result table (with CSV export)
   - an auto-selected interactive chart
   - an analyst-style explanation covering assumptions and pitfalls
   - data-quality warnings, when any apply
5. **Follow up** — ask a refinement and it keeps the context.

---

## Architecture

```
              Streamlit UI  (app.py)
          upload → overview → chat
                     │
        ┌────────────┼─────────────────────────┐
        ▼            ▼                           ▼
   llm.py       guardrails.py                db.py
 Claude API   validate + enforce        SQLite / DuckDB
 gen→fix→     LIMIT, block writes        schema + execute
 explain          │                          │
        └─────────┴───────────┬──────────────┘
                              ▼
                  validators.py   charts.py
                  data-quality     auto chart
                   warnings        selection
```

**Request flow for one question:**

`question → generate_sql → validate_sql → run query → (on error: fix_sql → re-validate → retry) → run_validations → explain_results → auto_chart`

---

## Tech stack

| Layer | Choice |
|---|---|
| UI | Streamlit |
| Language | Python |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| Query engines | SQLite (sample DB), DuckDB (uploaded CSVs) |
| Data | pandas |
| Charts | Plotly |
| Config | YAML (KPI definitions), prompt templates as text files |

---

## Run it locally

```bash
git clone <your-repo-url>
cd datamind
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Add your Anthropic API key. For local runs, create `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Then:

```bash
streamlit run app.py
```

The sample database seeds automatically on first run — no setup needed.

---

## Project structure

```
datamind/
  app.py                  Streamlit app: upload → overview → chat
  requirements.txt
  db/
    sample.db             Auto-seeded sample music-store DB
  prompts/
    sql_gen.txt           Natural language → SQL
    sql_fix.txt           Error-correction prompt
    sql_explain.txt       Result-explanation prompt
  metrics/
    kpis.yaml             Business KPI definitions (consistent metric logic)
  utils/
    db.py                 Schema extraction + query execution (SQLite / DuckDB)
    llm.py                Claude API calls
    guardrails.py         SQL safety validation
    charts.py             Context-aware chart selection (12 types)
    validators.py         Post-query data-quality checks
```

---

## Design decisions worth calling out

- **KPIs live in a config file, not in prompts.** `metrics/kpis.yaml` defines metrics like revenue, AOV, and revenue-per-customer once, so the same definition is reused across questions instead of the model re-deriving (and potentially redefining) a metric each time.
- **Prompts are versioned as files, not inline strings.** Generation, fixing, and explanation each have their own template in `prompts/`, which keeps them easy to tune without touching application code.
- **Read-only by design.** The tool is deliberately incapable of mutating data — the guardrail layer enforces it rather than trusting the model to behave.

---

## Limitations (by design and otherwise)

- Read-only SELECT queries only — no data mutation, intentionally.
- SQL dialects: SQLite for the sample DB, DuckDB SQL for uploaded CSVs.
- Very large schemas (50+ tables) can crowd the prompt; schema filtering would be the next step.
- Single-table CSV uploads — multi-file CSV joins aren't supported yet.

---

## Possible next steps

These are deliberately scoped as future work rather than half-built features:

- An AI **data-profiling agent** that produces a dataset health score and per-column recommendations.
- A one-click **executive PDF report** (overview + key insights + charts).
- **Schema filtering / retrieval** to support large databases.

---

## License

MIT
