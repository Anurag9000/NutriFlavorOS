from backend.database import Base, DBHouseholdMember, DBUser
from backend.domain.household_access import HouseholdRole, InvitationCreate, HouseholdMemberUpdate
from backend.services.household_access_service import accept_invitation, create_invitation, require_household_access
from backend.services.inventory_service_v4 import create_household
from backend.domain.inventory import HouseholdCreate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from fastapi import HTTPException


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_invitation_is_email_bound_one_time_and_role_limited():
    db = _db(); owner = DBUser(id="owner@example.com", name="Owner", hashed_password="x"); invitee = DBUser(id="member@example.com", name="Member", hashed_password="x")
    db.add_all([owner, invitee]); db.commit()
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    invite = create_invitation(db, household, owner, InvitationCreate(email=invitee.id, role=HouseholdRole.EDITOR))
    member = accept_invitation(db, invite.acceptance_token, invitee)
    assert member.household_id == household.id and member.role == "editor"
    with pytest.raises(HTTPException) as error:
        accept_invitation(db, invite.acceptance_token, invitee)
    assert error.value.status_code == 410
    assert require_household_access(db, household.id, invitee.id, HouseholdRole.EDITOR)[1] == HouseholdRole.EDITOR


def test_owner_role_cannot_be_assigned_through_member_update():
    with pytest.raises(Exception):
        HouseholdMemberUpdate(role=HouseholdRole.OWNER)
