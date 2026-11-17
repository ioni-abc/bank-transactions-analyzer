# Bank Transactions Analyzer

A personal finance tool that merges six years of transactions from four bank accounts into one database, categorises every transaction and shows monthly spending in a Streamlit dashboard.

## What it does

**1. Clean each bank's export** (`notebooks/<bank>.ipynb`)
Every bank exports in its own format. One notebook per source handles its quirks:

| Source | Currency | Period | Quirks handled |
|---|---|---|---|
| Eurobank | EUR | 2021 – 2026 | Greek column headers, European number format, several yearly files |
| Revolut | EUR | 2020 – 2026 | reverted transactions, transfers between Revolut users all labelled "Revolut Bank UAB" |
| Revolut | DKK | 2024 – 2026 | reverted transactions, DKK → EUR conversion |
| Lunar | DKK | 2024 – 2026 | separate date and time columns, partial categories, vague MobilePay entries |

**2. Categorise** (e.g. "Lidl" → Market)
Unique descriptions are exported to JSON in batches, categorised with an LLM, merged into one mapping per bank and reviewed by hand. Ambiguous transfers are resolved manually, and sanity checks catch any transaction left without a category.

**3. Merge** (`notebooks/merge_datasets_in_one_db.ipynb`)
The cleaned per-bank parquet files are aligned to one schema and loaded into a single SQLite table.

**4. Explore** (`app.py`)
A Streamlit dashboard: pick a month, see spending per category and the total, and exclude categories (e.g. rent) to see the rest.

## Run it

Raw statements, processed data and mappings contain personal data, so they are git-ignored. To run it, put your own exports in `data/raw/<bank>/` and run the notebooks.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Next steps

- [ ] **Frontend**: a proper web UI with charts and trends over time, replacing the basic Streamlit page
- [ ] **AI agent**: ask questions about your spending in plain language (e.g. "Why was October more expensive than September?"), with the agent querying the database through tools

## Stack

Python · pandas · SQLite · Streamlit · Jupyter · LLM-assisted categorisation
