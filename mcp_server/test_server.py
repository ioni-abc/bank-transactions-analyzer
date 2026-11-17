"""Smoke tests: connect a real MCP client to the server (in memory) over a throwaway database.

    pytest mcp_server
"""

import asyncio
import json
import sqlite3

import pytest
from mcp.client import Client

from mcp_server import server

ROWS = [
    ("2025-09-03 12:00:00", "Lidl", "Market", -45.2),
    ("2025-09-10 09:00:00", "Rent", "Rent", -800.0),
    ("2025-09-25 00:00:00", "Salary", "Income", 1500.0),
    ("2025-09-26 00:00:00", "To savings", "Self-transfer", -300.0),
    ("2025-10-02 12:00:00", "Lidl", "Market", -60.5),
    ("2025-10-15 20:00:00", "Ticketmaster", "Entertainment", -120.0),
]


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    db = tmp_path / "transactions.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE transactions (date TEXT, description TEXT, category TEXT, amount REAL, source TEXT)")
    conn.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, 'test')", ROWS)
    conn.commit()
    conn.close()
    monkeypatch.setattr(server, "DB_PATH", db)
    return db


def call(tool: str, args: dict | None = None):
    async def run():
        async with Client(server.mcp) as client:
            return await client.call_tool(tool, args or {})
    return asyncio.run(run())


def data(result):
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)


def test_every_tool_is_read_only():
    async def run():
        async with Client(server.mcp) as client:
            return (await client.list_tools()).tools
    assert all(tool.annotations.read_only_hint for tool in asyncio.run(run()))


def test_spending_excludes_income_and_self_transfers():
    result = data(call("spending_by_category", {"month": "2025-09"}))
    assert result["total_spent"] == 845.2
    assert {c["category"] for c in result["categories"]} == {"Rent", "Market"}


def test_exclude_categories():
    result = data(call("spending_by_category", {"month": "2025-09", "exclude_categories": ["Rent"]}))
    assert result["total_spent"] == 45.2


def test_monthly_totals():
    rows = data(call("monthly_totals", {"start_month": "2025-09", "end_month": "2025-10"}))
    assert rows[0] == {"month": "2025-09", "spent": 845.2, "income": 1500.0, "net": 654.8}


def test_bad_month_returns_a_readable_error():
    result = call("top_merchants", {"month": "October"})
    assert result.is_error
    assert "2025-10" in result.content[0].text


def test_sql_injection_is_harmless(database):
    call("search_transactions", {"text": "'; DROP TABLE transactions; --"})
    assert sqlite3.connect(database).execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == len(ROWS)
