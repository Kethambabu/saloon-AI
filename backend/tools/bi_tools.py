"""
Business Intelligence Analytics Tools for SalonAI Workforce Platform.
Provides database aggregation, SQL injection protection, and React-friendly chart data.
Compatible with both SQLite (testing) and PostgreSQL (production).
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, text, desc
from sqlalchemy.orm import Session

from db.database import SessionLocal, engine
from db.models import (
    Appointment, Customer, Service, Staff, Branch, Review, Lead,
    AppointmentStatus, LeadStatus, ReviewStatus
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL Injection & Safety Validation Engine
# ---------------------------------------------------------------------------
def validate_sql_safety(sql: str) -> tuple[bool, Optional[str]]:
    """
    Validates a SQL query for execution safety.
    Enforces strict read-only SELECT constraints and prevents SQL injection mutations.

    Returns:
        tuple: (is_safe: bool, error_message: str)
    """
    sql_clean = sql.strip().upper()

    # 1. Must be a SELECT query
    if not sql_clean.startswith("SELECT"):
        return False, "Strict safety violation: Only read-only 'SELECT' queries are allowed."

    # 2. Prevent forbidden SQL keywords (DML, DDL, administrative)
    forbidden_patterns = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bALTER\b",
        r"\bCREATE\b", r"\bTRUNCATE\b", r"\bREPLACE\b", r"\bGRANT\b", r"\bREVOKE\b",
        r"\bRENAME\b", r"\bEXEC\b", r"\bEXECUTE\b", r";", r"--"
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, sql_clean):
            return False, f"Strict safety violation: Query contains forbidden SQL keyword/pattern: {pattern.replace(r'\b', '')}"

    # 3. Restrict whitelisted tables only to protect system tables
    allowed_tables = ["BRANCHES", "STAFF", "CUSTOMERS", "SERVICES", "APPOINTMENTS", "LEADS", "REVIEWS"]
    
    # Simple regex parsing to extract table names (looking for FROM <table_name> or JOIN <table_name>)
    table_refs = re.findall(r"\bFROM\s+([A-Za-z0-9_]+)\b", sql_clean)
    table_refs += re.findall(r"\bJOIN\s+([A-Za-z0-9_]+)\b", sql_clean)

    for table in table_refs:
        if table not in allowed_tables:
            return False, f"Strict safety violation: Access denied to table '{table}'. Query must only target whitelisted tables."

    return True, None


# ---------------------------------------------------------------------------
# Natural Language SQL Generation & Protection Tool
# ---------------------------------------------------------------------------
def execute_bi_sql_query(sql_query: str) -> Dict[str, Any]:
    """
    Executes a raw SQL analytical query inside an atomic read-only transaction.
    Protects against SQL injection and write operations.

    Args:
        sql_query: The SQL query string to run.
    """
    logger.info(f"[BI Tool] Request to execute raw SQL query: '{sql_query[:120]}'")

    # 1. Clean and repair SQL to be PostgreSQL-compatible
    sql_clean = _repair_sql_for_postgres(sql_query.strip())
    logger.info(f"[BI Tool] SQL after repair: '{sql_clean[:200]}'")

    # 2. Strict safety validation
    is_safe, error_msg = validate_sql_safety(sql_clean)
    if not is_safe:
        logger.warning(f"[BI Tool] SQL Safety violation block: {error_msg}")
        return {"success": False, "error": error_msg}

    # 3. Enforce limits on the query results to prevent memory issues
    if "LIMIT" not in sql_clean.upper():
        if sql_clean.endswith(";"):
            sql_clean = sql_clean[:-1]
        sql_clean += " LIMIT 50"

    db: Session = SessionLocal()
    try:
        cursor = db.execute(text(sql_clean))

        # Parse column headers and rows
        columns = list(cursor.keys())
        rows = [list(row) for row in cursor.fetchall()]

        # Convert Decimals and datetimes to float/strings for JSON serialization
        serialized_rows = []
        for row in rows:
            new_row = []
            for item in row:
                if isinstance(item, Decimal):
                    new_row.append(float(item))
                elif isinstance(item, datetime):
                    new_row.append(item.isoformat())
                else:
                    new_row.append(item)
            serialized_rows.append(new_row)

        db.rollback()  # Safety rollback — always read-only
        logger.info(f"[BI Tool] Raw SQL executed successfully (returned {len(rows)} rows)")

        return {
            "success": True,
            "columns": columns,
            "rows": serialized_rows,
            "row_count": len(rows),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[BI Tool] Raw SQL execution encountered error: {e}", exc_info=True)
        return {"success": False, "error": f"Database execution error: {str(e)}"}
    finally:
        db.close()


def _repair_sql_for_postgres(sql: str) -> str:
    """
    Converts MySQL/generic SQL dialect patterns to valid PostgreSQL syntax.
    Called automatically before every query execution.
    """

    def quote_interval(match):
        number = match.group(1)
        unit = match.group(2).lower()
        unit_map = {
            'day': 'day', 'days': 'day',
            'hour': 'hour', 'hours': 'hour',
            'minute': 'minute', 'minutes': 'minute',
            'second': 'second', 'seconds': 'second',
            'week': 'week', 'weeks': 'week',
            'month': 'month', 'months': 'month',
            'year': 'year', 'years': 'year',
        }
        pg_unit = unit_map.get(unit, unit)
        return f"INTERVAL '{number} {pg_unit}'"

    sql = re.sub(
        r"\bINTERVAL\s+(\d+)\s+(DAY|DAYS|HOUR|HOURS|MINUTE|MINUTES|SECOND|SECONDS|WEEK|WEEKS|MONTH|MONTHS|YEAR|YEARS)\b",
        quote_interval,
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(
        r"INTERVAL\s+'([^'\)]+)\)'",
        r"INTERVAL '\1')",
        sql,
        flags=re.IGNORECASE
    )

    def replace_date_sub(match):
        expr = match.group(1).strip()
        interval_val = match.group(2).strip()
        return f"({expr} - INTERVAL '{interval_val}')"

    sql = re.sub(
        r"\bDATE_SUB\s*\(\s*([^,]+),\s*INTERVAL\s+'?([^')]+)'?\s*\)",
        replace_date_sub,
        sql,
        flags=re.IGNORECASE
    )

    def replace_date_add(match):
        expr = match.group(1).strip()
        interval_val = match.group(2).strip()
        return f"({expr} + INTERVAL '{interval_val}')"

    sql = re.sub(
        r"\bDATE_ADD\s*\(\s*([^,]+),\s*INTERVAL\s+'?([^')]+)'?\s*\)",
        replace_date_add,
        sql,
        flags=re.IGNORECASE
    )

    def replace_date_interval_cast(match):
        inner = match.group(1).strip()
        return f"({inner})::date"

    sql = re.sub(
        r"\bDATE\s*\(\s*((?:NOW\s*\(\s*\)|CURRENT_TIMESTAMP|CURRENT_DATE)\s*[-+]\s*INTERVAL\s+'[^']+')\s*\)",
        replace_date_interval_cast,
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(
        r"\bDATE\s*\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\)",
        r"\1::date",
        sql,
        flags=re.IGNORECASE
    )

    def replace_datediff(match):
        a = match.group(1).strip()
        b = match.group(2).strip()
        return f"DATE_PART('day', {a} - {b})::int"

    sql = re.sub(
        r"\bDATEDIFF\s*\(\s*([^,]+),\s*([^)]+)\)",
        replace_datediff,
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(r"\bYEAR\s*\(\s*([^)]+)\)", r"EXTRACT(YEAR FROM \1)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bMONTH\s*\(\s*([^)]+)\)", r"EXTRACT(MONTH FROM \1)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bDAY\s*\(\s*([^)]+)\)", r"EXTRACT(DAY FROM \1)", sql, flags=re.IGNORECASE)

    sql = re.sub(r"\bIFNULL\s*\(", "COALESCE(", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bISNULL\s*\(\s*([^)]+)\)", r"\1 IS NULL", sql, flags=re.IGNORECASE)

    sql = re.sub(r"\bGROUP_CONCAT\s*\(\s*([^)]+)\)", r"STRING_AGG(\1, ',')", sql, flags=re.IGNORECASE)

    sql = sql.rstrip().rstrip(";").rstrip()

    return sql
