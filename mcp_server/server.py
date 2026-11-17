"""MCP server that lets an LLM client (Claude Desktop, Claude Code, ...) query the transactions database.

Every tool is read-only: the database is opened in SQLite's read-only mode and all
inputs are passed as query parameters, never formatted into the SQL.

Run directly (stdio transport):
    python mcp_server/server.py
"""

import os
import re
import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("EXPENSES_DB_PATH", PROJECT_ROOT / "data" / "transactions.db"))

# Moving money between my own accounts is neither spending nor income.
EXCLUDED_CATEGORIES = ("Self-transfer",)
MAX_ROWS = 200  # keeps tool results small enough for the model's context
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

mcp = MCPServer(
    name="expenses",
    instructions=(
        "Personal bank transactions from four accounts (Eurobank, Revolut EUR, Revolut DKK, Lunar), "
        "merged into one table. Amounts are in EUR: negative = spending, positive = income. "
        "Transfers between my own accounts (category 'Self-transfer') are excluded from totals. "
        "Months are written YYYY-MM. Call list_months first if you do not know which months exist."
    ),
)


# ---------- helpers ----------

def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query and return the rows as dicts."""
    if not DB_PATH.exists():
        raise ToolError(
            f"No database at {DB_PATH}. Build it with notebooks/merge_datasets_in_one_db.ipynb "
            "or set EXPENSES_DB_PATH."
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def check_month(month: str) -> str:
    if not MONTH.match(month):
        raise ToolError(f"Month must look like 2025-10, got {month!r}")
    return month


def clamp(n: int) -> int:
    return max(1, min(n, MAX_ROWS))


def excluded(extra: list[str] | None) -> tuple[str, tuple]:
    """SQL fragment and parameters that leave out self-transfers and any extra categories."""
    categories = EXCLUDED_CATEGORIES + tuple(extra or ())
    placeholders = ", ".join("?" for _ in categories)
    return f"COALESCE(category, '') NOT IN ({placeholders})", categories


# ---------- tools ----------

@mcp.tool(annotations=READ_ONLY)
def list_months() -> list[str]:
    """All months (YYYY-MM) that have transactions, oldest first."""
    rows = query("SELECT DISTINCT strftime('%Y-%m', date) AS month FROM transactions ORDER BY month")
    return [r["month"] for r in rows]


@mcp.tool(annotations=READ_ONLY)
def list_categories() -> list[dict]:
    """Every category with its number of transactions, most used first."""
    return query("""
        SELECT category, COUNT(*) AS transactions
        FROM transactions
        GROUP BY category
        ORDER BY transactions DESC
    """)


@mcp.tool(annotations=READ_ONLY)
def spending_by_category(month: str, exclude_categories: list[str] | None = None) -> dict:
    """Spending per category for one month (YYYY-MM), most expensive first, plus the month's total.

    Use exclude_categories to leave out e.g. ["Rent"] and see the rest.
    """
    where, params = excluded(exclude_categories)
    rows = query(f"""
        SELECT category, ROUND(-SUM(amount), 2) AS spent, COUNT(*) AS transactions
        FROM transactions
        WHERE amount < 0 AND strftime('%Y-%m', date) = ? AND {where}
        GROUP BY category
        ORDER BY spent DESC
    """, (check_month(month), *params))
    return {"month": month, "total_spent": round(sum(r["spent"] for r in rows), 2), "categories": rows}


@mcp.tool(annotations=READ_ONLY)
def monthly_totals(start_month: str, end_month: str, category: str | None = None) -> list[dict]:
    """Spending, income and net per month between two months (inclusive).

    With category set, only that category's spending is counted (good for trends,
    e.g. "how has my Market spending changed this year?").
    """
    where, params = excluded(None)
    category_filter = "AND category = ?" if category else ""
    category_param = (category,) if category else ()
    return query(f"""
        SELECT strftime('%Y-%m', date) AS month,
               ROUND(-SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 2) AS spent,
               ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
               ROUND(SUM(amount), 2) AS net
        FROM transactions
        WHERE strftime('%Y-%m', date) BETWEEN ? AND ? AND {where} {category_filter}
        GROUP BY month
        ORDER BY month
    """, (check_month(start_month), check_month(end_month), *params, *category_param))


@mcp.tool(annotations=READ_ONLY)
def top_merchants(month: str, n: int = 10) -> list[dict]:
    """The n descriptions (shops, services, people) with the most spending in a month (YYYY-MM)."""
    where, params = excluded(None)
    return query(f"""
        SELECT description, category, ROUND(-SUM(amount), 2) AS spent, COUNT(*) AS transactions
        FROM transactions
        WHERE amount < 0 AND strftime('%Y-%m', date) = ? AND {where}
        GROUP BY description
        ORDER BY spent DESC
        LIMIT ?
    """, (check_month(month), *params, clamp(n)))


@mcp.tool(annotations=READ_ONLY)
def search_transactions(
    text: str | None = None,
    month: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Individual transactions, newest first, filtered by any mix of:
    text in the description (case-insensitive), month (YYYY-MM) and category.
    """
    conditions, params = [], []
    if text:
        conditions.append("description LIKE ?")
        params.append(f"%{text}%")
    if month:
        conditions.append("strftime('%Y-%m', date) = ?")
        params.append(check_month(month))
    if category:
        conditions.append("category = ?")
        params.append(category)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return query(f"""
        SELECT date, description, category, amount, source
        FROM transactions
        {where}
        ORDER BY date DESC
        LIMIT ?
    """, (*params, clamp(limit)))


# ---------- prompts ----------

@mcp.prompt()
def monthly_review(month: str) -> str:
    """A ready-made request: review one month's spending against the month before."""
    return (
        f"Review my spending for {month}. Compare it with the previous month using the expenses tools: "
        "which categories went up or down the most, which merchants drove the change, and is anything "
        "unusual? Finish with three short, concrete observations."
    )


if __name__ == "__main__":
    mcp.run()
