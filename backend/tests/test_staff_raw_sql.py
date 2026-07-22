"""
Tests for StaffRawSQLHandler — secure, row-level-filtered staff SQL queries.
"""
import sys
import os
import uuid
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def staff_uuid():
    return str(uuid.uuid4())


@pytest.fixture()
def user_uuid():
    return str(uuid.uuid4())


@pytest.fixture()
def mock_user(staff_uuid, user_uuid):
    """Return a mock User object with a linked staff_id."""
    user = MagicMock()
    user.id = user_uuid
    user.staff_id = staff_uuid
    return user


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _build_ctx(sql: str, user_id: str):
    from core.handlers import HandlerContext
    return HandlerContext(params={"sql": sql}, user_id=user_id, user_role="STAFF")


def _mock_session_for(user_obj):
    """Build a mock DB session that returns user_obj on query."""
    mock_sess = MagicMock()
    mock_sess.query.return_value.filter.return_value.first.return_value = user_obj
    mock_sess.close = MagicMock()
    return mock_sess


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestStaffRawSQLHandler:

    def _call(self, sql, mock_user, raw_result=None):
        """Set up mocks and call the handler."""
        from core.handlers import StaffRawSQLHandler
        mock_sess = _mock_session_for(mock_user)

        # Patch SessionLocal at the module level in core.handlers
        with patch("core.handlers.SessionLocal", return_value=mock_sess):
            if raw_result is not None:
                with patch("ai.agents.bi_agent.query_raw_analytics_database", return_value=raw_result):
                    handler = StaffRawSQLHandler()
                    ctx = _build_ctx(sql, str(mock_user.id))
                    return handler.handle(ctx)
            else:
                handler = StaffRawSQLHandler()
                ctx = _build_ctx(sql, str(mock_user.id))
                return handler.handle(ctx)

    def test_valid_query_succeeds(self, mock_user, staff_uuid):
        sql = f"SELECT id, COUNT(*) FROM appointments WHERE staff_id = '{staff_uuid}'"
        raw_result = [{"id": staff_uuid, "count": 10}]
        res = self._call(sql, mock_user, raw_result=raw_result)
        assert res["success"] is True
        assert len(res["result"]) == 1

    def test_missing_staff_id_filter_is_rejected(self, mock_user):
        sql = "SELECT * FROM appointments"
        res = self._call(sql, mock_user)
        assert res["success"] is False
        assert "Security violation" in res["error"]

    def test_users_table_is_forbidden(self, mock_user, staff_uuid):
        sql = f"SELECT * FROM users WHERE staff_id = '{staff_uuid}'"
        res = self._call(sql, mock_user)
        assert res["success"] is False
        assert "users table is forbidden" in res["error"]

    def test_non_select_statement_is_rejected(self, mock_user, staff_uuid):
        sql = f"DELETE FROM appointments WHERE staff_id = '{staff_uuid}'"
        res = self._call(sql, mock_user)
        assert res["success"] is False
        assert "Only SELECT statements" in res["error"]

    def test_cross_staff_rows_are_post_filtered(self, mock_user, staff_uuid):
        """Rows belonging to another staff member must be stripped from results."""
        other_staff_id = str(uuid.uuid4())
        raw_result = [
            {"staff_id": staff_uuid, "appointments": 5},        # own row → kept
            {"staff_id": other_staff_id, "appointments": 12},   # other → stripped
        ]
        sql = f"SELECT staff_id, COUNT(*) FROM appointments WHERE staff_id = '{staff_uuid}'"
        res = self._call(sql, mock_user, raw_result=raw_result)
        assert res["success"] is True
        assert len(res["result"]) == 1
        assert res["result"][0]["staff_id"] == staff_uuid

    def test_no_staff_linked_returns_error(self):
        """If the logged-in user has no linked staff record, return an error."""
        user_no_staff = MagicMock()
        user_no_staff.id = str(uuid.uuid4())
        user_no_staff.staff_id = None

        from core.handlers import StaffRawSQLHandler
        mock_sess = _mock_session_for(user_no_staff)

        with patch("core.handlers.SessionLocal", return_value=mock_sess):
            handler = StaffRawSQLHandler()
            ctx = _build_ctx("SELECT 1", str(user_no_staff.id))
            res = handler.handle(ctx)

        assert res["success"] is False
        assert "No associated staff member" in res["error"]
