"""Tests for the health check route."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import ArgumentError
from sqlalchemy.sql.elements import TextClause

from api.routes.health import health_check


def _strict_execute(statement, *args, **kwargs):
    """Reject plain strings the way SQLAlchemy 2.x AsyncSession.execute does."""
    if isinstance(statement, str):
        raise ArgumentError(
            f"Textual SQL expression {statement!r} should be explicitly declared as "
            f"text({statement!r})"
        )


async def _run_health_check(db: AsyncMock) -> Any:
    """Call the handler and return its status dict, whether it returns or raises 503."""
    try:
        return await health_check(db=db)
    except HTTPException as exc:
        return exc.detail


@pytest.mark.unit
class TestHealthCheckPostgresProbe:
    """Test suite for the PostgreSQL probe in health_check (issue #61)."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock async session whose execute() rejects raw SQL strings."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_strict_execute)
        return session

    @pytest.mark.asyncio
    async def test_probe_passes_text_clause(self, mock_db_session):
        """The probe wraps its SQL in text(), as SQLAlchemy 2.x requires."""
        await _run_health_check(mock_db_session)

        mock_db_session.execute.assert_awaited_once()
        assert isinstance(mock_db_session.execute.await_args.args[0], TextClause)

    @pytest.mark.asyncio
    async def test_reachable_postgres_reported_healthy(self, mock_db_session):
        """A database that accepts the probe is reported healthy."""
        result = await _run_health_check(mock_db_session)

        assert result["dependencies"]["postgres"] == "healthy"
