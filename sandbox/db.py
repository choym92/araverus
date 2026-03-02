"""DB module: loads CSV data into in-memory SQLite and executes SQL queries."""

import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

SCHEMA_STR = """
Tables and columns:

employees(id INTEGER, name TEXT, dept TEXT, level TEXT, approver_id INTEGER)
  - id: unique employee ID
  - name: employee full name
  - dept: department name (영업팀, 개발팀, 마케팅팀, 인사팀, 경영진)
  - level: job level (사원, 대리, 과장, 부장, 팀장, 이사, 대표)
  - approver_id: employee ID of direct approver (FK -> employees.id)

trip_requests(id INTEGER, employee_id INTEGER, destination TEXT, purpose TEXT, start_date TEXT, end_date TEXT, status TEXT, approved_by INTEGER)
  - id: unique trip request ID
  - employee_id: FK -> employees.id
  - destination: trip destination city
  - purpose: reason for the trip
  - start_date: trip start date (YYYY-MM-DD)
  - end_date: trip end date (YYYY-MM-DD)
  - status: one of 'pending', 'approved', 'rejected'
  - approved_by: employee ID who approved (FK -> employees.id), NULL if not yet approved

expense_claims(id INTEGER, trip_id INTEGER, employee_id INTEGER, category TEXT, amount INTEGER, status TEXT)
  - id: unique expense claim ID
  - trip_id: FK -> trip_requests.id
  - employee_id: FK -> employees.id
  - category: expense type ('transport', 'hotel', 'meal', 'etc')
  - amount: amount in KRW (Korean Won)
  - status: one of 'pending', 'approved', 'rejected'

budget_limits(dept TEXT, level TEXT, annual_budget INTEGER, per_trip_limit INTEGER)
  - dept: department name
  - level: job level
  - annual_budget: total annual budget in KRW
  - per_trip_limit: maximum allowed expense per trip in KRW
"""

_conn: sqlite3.Connection | None = None


def load_db() -> sqlite3.Connection:
    """Load CSV files into in-memory SQLite. Returns cached connection."""
    global _conn
    if _conn is not None:
        return _conn

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    tables = {
        "employees": "employees.csv",
        "trip_requests": "trip_requests.csv",
        "expense_claims": "expense_claims.csv",
        "budget_limits": "budget_limits.csv",
    }
    for table_name, filename in tables.items():
        df = pd.read_csv(DATA_DIR / filename)
        df.to_sql(table_name, conn, index=False, if_exists="replace")

    _conn = conn
    return conn


def run_query(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """Execute SQL and return (DataFrame, None) or (None, error_message)."""
    conn = load_db()
    try:
        df = pd.read_sql_query(sql, conn)
        return df, None
    except Exception as e:
        return None, str(e)


def get_schema() -> str:
    """Return the schema description string for use in LLM prompts."""
    return SCHEMA_STR
