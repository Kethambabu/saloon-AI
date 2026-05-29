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


def _format_date_expr(col):
    """Helper to format datetime field to YYYY-MM-DD based on dialect (PostgreSQL vs SQLite)."""
    from db.database import engine
    if engine.dialect.name == "sqlite":
        return func.strftime("%Y-%m-%d", col)
    return func.to_char(col, "YYYY-MM-DD")


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
# 1. Revenue Analytics Tool
# ---------------------------------------------------------------------------
def get_revenue_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes total revenue, average ticket sizes, and revenue over time.
    Generates React-friendly chart datasets.

    Args:
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        branch_id: Optional UUID string of a salon branch to filter.
    """
    logger.info(f"[BI Tool] Calculating revenue analytics (branch={branch_id})")
    db: Session = SessionLocal()
    try:
        query = db.query(Appointment).filter(Appointment.status == AppointmentStatus.COMPLETED)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                query = query.filter(Appointment.start_time >= start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                query = query.filter(Appointment.start_time <= end_dt)
            except ValueError:
                pass
        if branch_id:
            query = query.filter(Appointment.branch_id == branch_id)

        appointments = query.all()

        total_revenue = Decimal("0.00")
        booking_count = len(appointments)

        for appt in appointments:
            if appt.service:
                total_revenue += Decimal(str(appt.service.price))

        avg_ticket = total_revenue / Decimal(str(booking_count)) if booking_count > 0 else Decimal("0.00")

        # Aggregate revenue by service
        revenue_by_service = {}
        for appt in appointments:
            if appt.service:
                s_name = appt.service.name
                revenue_by_service[s_name] = revenue_by_service.get(s_name, Decimal("0.00")) + Decimal(str(appt.service.price))

        # Aggregate revenue by branch
        revenue_by_branch = {}
        for appt in appointments:
            if appt.branch:
                b_name = appt.branch.name
                if appt.service:
                    revenue_by_branch[b_name] = revenue_by_branch.get(b_name, Decimal("0.00")) + Decimal(str(appt.service.price))

        # Revenue over time for line charts
        # Group by formatted date
        date_expr = _format_date_expr(Appointment.start_time)
        time_query = (
            db.query(date_expr.label("date"), func.sum(Service.price).label("sum"))
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
        )
        if branch_id:
            time_query = time_query.filter(Appointment.branch_id == branch_id)
        
        time_results = time_query.group_by(text("date")).order_by(text("date")).all()

        chart_labels = [row.date for row in time_results]
        chart_data = [float(row.sum or 0.0) for row in time_results]

        return {
            "success": True,
            "metrics": {
                "total_revenue": float(total_revenue),
                "total_bookings": booking_count,
                "average_ticket": round(float(avg_ticket), 2),
            },
            "revenue_by_service": {k: float(v) for k, v in revenue_by_service.items()},
            "revenue_by_branch": {k: float(v) for k, v in revenue_by_branch.items()},
            "charts": {
                "revenue_over_time": {
                    "labels": chart_labels,
                    "datasets": [{
                        "label": "Daily Revenue ($)",
                        "data": chart_data,
                    }]
                }
            }
        }
    except Exception as e:
        logger.error(f"[BI Tool] Revenue analytics calculation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. Staff Performance Analytics Tool
# ---------------------------------------------------------------------------
def get_staff_performance_analytics(
    branch_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes stylist performance indicators: bookings, total revenue,
    utilization rates, and average rating reviews.

    Args:
        branch_id: Optional UUID string of a branch to filter.
    """
    logger.info(f"[BI Tool] Calculating staff performance (branch={branch_id})")
    db: Session = SessionLocal()
    try:
        staff_query = db.query(Staff).filter(Staff.is_active == True)
        if branch_id:
            staff_query = staff_query.filter(Staff.branch_id == branch_id)
        
        staff_list = staff_query.all()
        results = []

        chart_labels = []
        chart_revenue = []
        chart_ratings = []

        for member in staff_list:
            appointments = db.query(Appointment).filter(
                Appointment.staff_id == member.id,
                Appointment.status == AppointmentStatus.COMPLETED
            ).all()

            total_rev = Decimal("0.00")
            total_minutes = 0
            for appt in appointments:
                if appt.service:
                    total_rev += Decimal(str(appt.service.price))
                    total_minutes += appt.service.duration_minutes

            # Calculate average review rating for this staff member (reviews linked to appointments)
            rating_query = db.query(func.avg(Review.rating)).join(
                Appointment, Review.appointment_id == Appointment.id
            ).filter(
                Appointment.staff_id == member.id,
                Review.status == ReviewStatus.APPROVED
            ).scalar()

            avg_rating = round(float(rating_query), 2) if rating_query is not None else 5.0

            # Calculate approximate utilization rate (assuming 40 hours = 2400 minutes workload)
            utilization_rate = min(100.0, round((total_minutes / 2400.0) * 100.0, 1))

            staff_name = f"{member.first_name} {member.last_name}"
            results.append({
                "staff_id": str(member.id),
                "name": staff_name,
                "role": member.role,
                "completed_bookings": len(appointments),
                "revenue_generated": float(total_rev),
                "utilization_rate_pct": utilization_rate,
                "average_rating": avg_rating,
            })

            chart_labels.append(staff_name)
            chart_revenue.append(float(total_rev))
            chart_ratings.append(avg_rating)

        # Sort staff list by revenue descending
        results.sort(key=lambda x: x["revenue_generated"], reverse=True)

        return {
            "success": True,
            "staff_metrics": results,
            "charts": {
                "staff_revenue": {
                    "labels": chart_labels,
                    "datasets": [{
                        "label": "Revenue Generated ($)",
                        "data": chart_revenue,
                    }]
                },
                "staff_ratings": {
                    "labels": chart_labels,
                    "datasets": [{
                        "label": "Average Rating",
                        "data": chart_ratings,
                    }]
                }
            }
        }
    except Exception as e:
        logger.error(f"[BI Tool] Staff performance calculation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Retention Analytics Tool
# ---------------------------------------------------------------------------
def get_retention_analytics() -> Dict[str, Any]:
    """
    Computes cohort customer retention and Lifetime Value (LTV) metrics.
    Determines percentage of repeat bookers.
    """
    logger.info("[BI Tool] Calculating customer retention analytics")
    db: Session = SessionLocal()
    try:
        # 1. Total customers
        total_customers = db.query(Customer).count()

        # 2. Count appointments per customer to find repeat bookers
        cust_bookings = (
            db.query(Appointment.customer_id, func.count(Appointment.id).label("count"))
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Appointment.customer_id)
            .all()
        )

        one_time_bookers = 0
        repeat_bookers = 0
        three_plus_bookers = 0

        for row in cust_bookings:
            if row.count == 1:
                one_time_bookers += 1
            elif row.count == 2:
                repeat_bookers += 1
            elif row.count >= 3:
                repeat_bookers += 1
                three_plus_bookers += 1

        total_booked_customers = len(cust_bookings)
        retention_rate = (repeat_bookers / total_booked_customers * 100.0) if total_booked_customers > 0 else 0.0

        # LTV analysis
        ltv_query = (
            db.query(Customer.id, Customer.first_name, Customer.last_name, func.sum(Service.price).label("ltv"))
            .join(Appointment, Customer.id == Appointment.customer_id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Customer.id)
            .order_by(desc("ltv"))
            .limit(10)
            .all()
        )

        top_customers = [
            {
                "customer_name": f"{row.first_name} {row.last_name}",
                "ltv": float(row.ltv or 0.0)
            }
            for row in ltv_query
        ]

        return {
            "success": True,
            "retention_metrics": {
                "total_registered_customers": total_customers,
                "total_transacting_customers": total_booked_customers,
                "one_time_visitors": one_time_bookers,
                "repeat_visitors": repeat_bookers,
                "loyal_visitors_3plus": three_plus_bookers,
                "retention_rate_pct": round(retention_rate, 2),
            },
            "top_customers_by_ltv": top_customers,
            "charts": {
                "retention_distribution": {
                    "labels": ["One-Time Customers", "Repeat Customers (2+ Visited)"],
                    "datasets": [{
                        "label": "Customer Count",
                        "data": [one_time_bookers, repeat_bookers],
                    }]
                }
            }
        }
    except Exception as e:
        logger.error(f"[BI Tool] Retention analytics failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Service Popularity Analytics Tool
# ---------------------------------------------------------------------------
def get_service_popularity_analytics() -> Dict[str, Any]:
    """
    Analyzes which service catalog items drive the most business and volume.
    """
    logger.info("[BI Tool] Calculating service popularity analytics")
    db: Session = SessionLocal()
    try:
        service_data = (
            db.query(Service.name, func.count(Appointment.id).label("bookings"), func.sum(Service.price).label("revenue"))
            .join(Appointment, Service.id == Appointment.service_id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Service.id)
            .order_by(desc("bookings"))
            .all()
        )

        chart_labels = []
        chart_bookings = []
        chart_revenue = []

        services_summary = []
        for row in service_data:
            services_summary.append({
                "service_name": row.name,
                "total_bookings": row.bookings,
                "total_revenue": float(row.revenue or 0.0)
            })
            chart_labels.append(row.name)
            chart_bookings.append(row.bookings)
            chart_revenue.append(float(row.revenue or 0.0))

        return {
            "success": True,
            "services": services_summary,
            "charts": {
                "service_bookings": {
                    "labels": chart_labels,
                    "datasets": [{
                        "label": "Bookings Count",
                        "data": chart_bookings,
                    }]
                },
                "service_revenue_share": {
                    "labels": chart_labels,
                    "datasets": [{
                        "label": "Revenue Share ($)",
                        "data": chart_revenue,
                    }]
                }
            }
        }
    except Exception as e:
        logger.error(f"[BI Tool] Service popularity analytics failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Natural Language SQL Generation & Protection Tool
# ---------------------------------------------------------------------------
def execute_bi_sql_query(sql_query: str) -> Dict[str, Any]:
    """
    Executes a raw SQL analytical query inside an atomic read-only transaction.
    Protects against SQL injection and write operations.

    Args:
        sql_query: The SQL query string to run.
    """
    logger.info(f"[BI Tool] Request to execute raw SQL query: '{sql_query[:120]}'")

    # 1. Strict safety validation
    is_safe, error_msg = validate_sql_safety(sql_query)
    if not is_safe:
        logger.warning(f"[BI Tool] SQL Safety violation block: {error_msg}")
        return {"success": False, "error": error_msg}

    # 2. Enforce limits on the query results to prevent memory issues
    # Append LIMIT 50 if it doesn't already specify a limit
    sql_clean = sql_query.strip()
    if "LIMIT" not in sql_clean.upper():
        if sql_clean.endswith(";"):
            sql_clean = sql_clean[:-1]
        sql_clean += " LIMIT 50"

    db: Session = SessionLocal()
    try:
        # 3. Execute query inside transaction
        # Note: We execute raw SELECT queries, but we always rollback at the end 
        # as a secondary line of absolute defense against mutations.
        cursor = db.execute(text(sql_clean))
        
        # Parse column headers and rows
        columns = list(cursor.keys())
        rows = [list(row) for row in cursor.fetchall()]

        # Convert Decimals and datetimes to float/strings for standard JSON serialization compatibility
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

        db.rollback()  # Primary safety rollback to ensure 100% read-only operations
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
