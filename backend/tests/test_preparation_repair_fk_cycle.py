from __future__ import annotations

from sqlalchemy.sql.ddl import sort_tables_and_constraints

from backend.database import Base
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import DBPreparationRepairProposal


def test_repair_schedule_cycle_has_named_alterable_edge():
    column = DBPersistedPreparationSchedule.__table__.c.source_repair_proposal_id
    constraints = {
        foreign_key.constraint
        for foreign_key in column.foreign_keys
    }

    assert len(constraints) == 1
    constraint = next(iter(constraints))
    assert constraint.name == (
        "fk_persisted_preparation_schedule_source_repair_proposal"
    )
    assert constraint.use_alter is True
    assert constraint.referred_table is DBPreparationRepairProposal.__table__


def test_metadata_sort_can_break_repair_schedule_proposal_cycle():
    # PostgreSQL drop_all() needs a named ALTER edge for the intentional cycle:
    # proposal -> source schedule, replacement schedule -> source proposal.
    result = list(sort_tables_and_constraints(list(Base.metadata.tables.values())))
    trailing_constraints = {
        constraint
        for table, constraints in result
        if table is None
        for constraint in constraints
    }

    replacement_constraint = next(
        foreign_key.constraint
        for foreign_key in (
            DBPersistedPreparationSchedule.__table__
            .c.source_repair_proposal_id.foreign_keys
        )
    )
    assert replacement_constraint in trailing_constraints
