# MCP server: chat with your bank transactions

This folder turns the transactions database into an **MCP server**. Any MCP client (Claude Desktop, Claude Code, Cursor, or your own agent) can then answer questions about your spending by querying the data itself:

> "Compare my spending in September and October. What changed the most?"
>
> "How much did I spend on groceries each month this year?"
>
> "Find every Ticketmaster payment."

The model decides which tools to call and in what order, then explains the result.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard for connecting LLM applications to external tools and data. A server exposes **tools** (functions the model can call) and **prompts** (reusable request templates). Any client that speaks MCP can use them, so one server works with many apps.

## Tools

| Tool | What it returns |
|---|---|
| `list_months()` | every month (YYYY-MM) that has transactions |
| `list_categories()` | every category with its number of transactions |
| `spending_by_category(month, exclude_categories?)` | spending per category for a month, plus the total |
| `monthly_totals(start_month, end_month, category?)` | spending, income and net per month: trends over time |
| `top_merchants(month, n?)` | where most of a month's money went |
| `search_transactions(text?, month?, category?, limit?)` | individual transactions, filtered by any mix of these |

There is also one prompt, **`monthly_review(month)`**, a ready-made request that compares a month with the one before it.

Amounts are in EUR (negative = spending). Transfers between my own accounts (`Self-transfer`) are excluded from totals.

## Design decisions

- **Read-only by construction.** The database is opened in SQLite's read-only mode (`mode=ro`), and every tool is marked `read_only_hint` so clients know nothing can be changed.
- **No SQL injection.** The model chooses the inputs, so every value is passed as a query parameter (`?`), never formatted into the SQL. A test checks that an injection attempt leaves the table intact.
- **Small, composable tools.** There is no `compare_months` tool: the model calls `spending_by_category` twice and compares the results itself. Fewer, simpler tools are easier for the model to use correctly.
- **Bounded results.** Row limits are capped at 200, so a broad query cannot flood the model's context.
- **Errors the model can act on.** Invalid input returns a readable message (e.g. "Month must look like 2025-10, got 'October'"), so the model can correct itself and retry.

## Setup

Requires Python 3.10+ and a built database at `data/transactions.db` (see `notebooks/merge_datasets_in_one_db.ipynb`).

```bash
pip install -r requirements.txt
pytest mcp_server            # optional: 6 smoke tests on a throwaway database
```

Use absolute paths in the configurations below. To use a database somewhere else, set the `EXPENSES_DB_PATH` environment variable.

### Claude Desktop

Open **Settings > Developer > Edit Config** and add:

```json
{
  "mcpServers": {
    "expenses": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/bank-transactions-analyzer/mcp_server/server.py"]
    }
  }
}
```

Restart Claude Desktop. The tools appear under the tools icon in the chat box.

### Claude Code

```bash
claude mcp add expenses -- /absolute/path/to/venv/bin/python /absolute/path/to/bank-transactions-analyzer/mcp_server/server.py
```

### Inspect it without an LLM

The MCP Inspector lets you call each tool by hand and see the raw responses:

```bash
npx @modelcontextprotocol/inspector /absolute/path/to/venv/bin/python mcp_server/server.py
```

## Files

```
mcp_server/
  server.py        the server: tools, prompt and read-only database access
  test_server.py   smoke tests that connect a real MCP client to the server
```
