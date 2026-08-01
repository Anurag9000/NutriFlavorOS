from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from backend.database import Base
from backend.evidence_history_models import (  # noqa: F401
    DBIngredientConversionVersion,
    DBLeftoverStoragePolicyEvidence,
    DBStoragePolicyVersion,
)
from backend.preparation_models import DBRecipePreparationProfile  # noqa: F401
from backend.schema_verification import verify_runtime_schema


ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_current_alembic_head_passes_runtime_verification(tmp_path, monkeypatch):
    database = tmp_path / "current-head.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "head")
    verify_runtime_schema(create_engine(url))


def test_stale_alembic_revision_is_rejected(tmp_path, monkeypatch):
    database = tmp_path / "stale-head.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "20260731_0005")

    with pytest.raises(
        RuntimeError,
        match="Expected 20260801_0007; observed 20260731_0005",
    ):
        verify_runtime_schema(create_engine(url))


def test_orm_created_schema_without_revision_is_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'orm-only.db'}")
    Base.metadata.create_all(engine)

    with pytest.raises(RuntimeError, match="no Alembic revision record"):
        verify_runtime_schema(engine)


def test_missing_runtime_tables_are_reported_before_revision_check(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")

    with pytest.raises(RuntimeError, match="Missing tables"):
        verify_runtime_schema(engine)
