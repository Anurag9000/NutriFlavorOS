import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBHouseholdInvitation, DBHouseholdMember, DBUser
from backend.domain.household_access import (
    HouseholdMemberUpdate,
    HouseholdRole,
    InvitationCreate,
)
from backend.domain.inventory import HouseholdCreate
from backend.services.household_access_service import (
    accept_invitation,
    create_invitation,
    require_household_access,
    revoke_invitation,
    update_member,
)
from backend.services.inventory_service_v4 import create_household


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _users(db):
    owner = DBUser(
        id="owner@example.com",
        name="Owner",
        hashed_password="x",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    invitee = DBUser(
        id="member@example.com",
        name="Member",
        hashed_password="x",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=["peanut"],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    other = DBUser(
        id="other@example.com",
        name="Other",
        hashed_password="x",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    db.add_all([owner, invitee, other])
    db.commit()
    return owner, invitee, other


def test_household_creation_persists_explicit_owner_membership():
    db = _db()
    owner, _, _ = _users(db)
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    membership = (
        db.query(DBHouseholdMember)
        .filter(
            DBHouseholdMember.household_id == household.id,
            DBHouseholdMember.linked_user_id == owner.id,
        )
        .one()
    )
    assert membership.role == HouseholdRole.OWNER.value
    assert membership.active is True
    assert membership.display_name == "Owner"


def test_invitation_is_email_bound_retry_safe_and_role_limited():
    db = _db()
    owner, invitee, other = _users(db)
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    invite = create_invitation(
        db,
        household,
        owner,
        InvitationCreate(email=invitee.id, role=HouseholdRole.EDITOR),
    )

    with pytest.raises(HTTPException) as wrong_account:
        accept_invitation(db, invite.acceptance_token, other)
    assert wrong_account.value.status_code == 403

    member = accept_invitation(db, invite.acceptance_token, invitee)
    repeated = accept_invitation(db, invite.acceptance_token, invitee)
    assert repeated.id == member.id
    assert member.household_id == household.id
    assert member.role == "editor"
    assert member.allergies == ["peanut"]
    assert (
        db.query(DBHouseholdMember)
        .filter(DBHouseholdMember.household_id == household.id)
        .count()
        == 2
    )
    assert (
        require_household_access(
            db, household.id, invitee.id, HouseholdRole.EDITOR
        )[1]
        == HouseholdRole.EDITOR
    )


def test_new_invitation_revokes_previous_token_and_updates_household_version():
    db = _db()
    owner, invitee, _ = _users(db)
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    initial_version = household.version
    first = create_invitation(
        db,
        household,
        owner,
        InvitationCreate(email=invitee.id, role=HouseholdRole.VIEWER),
    )
    second = create_invitation(
        db,
        household,
        owner,
        InvitationCreate(email=invitee.id, role=HouseholdRole.EDITOR),
    )
    db.expire_all()
    persisted = db.get(DBHousehold, household.id)
    assert persisted.version == initial_version + 2
    first_row = db.get(DBHouseholdInvitation, first.id)
    second_row = db.get(DBHouseholdInvitation, second.id)
    assert first_row.revoked_at is not None
    assert second_row.revoked_at is None

    with pytest.raises(HTTPException) as old_token:
        accept_invitation(db, first.acceptance_token, invitee)
    assert old_token.value.status_code == 410
    member = accept_invitation(db, second.acceptance_token, invitee)
    assert member.role == HouseholdRole.EDITOR.value


def test_revocation_is_idempotent_and_token_cannot_be_accepted():
    db = _db()
    owner, invitee, _ = _users(db)
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    invite = create_invitation(
        db,
        household,
        owner,
        InvitationCreate(email=invitee.id, role=HouseholdRole.VIEWER),
    )
    revoked = revoke_invitation(db, household.id, invite.id)
    repeated = revoke_invitation(db, household.id, invite.id)
    assert repeated.id == revoked.id
    with pytest.raises(HTTPException) as error:
        accept_invitation(db, invite.acceptance_token, invitee)
    assert error.value.status_code == 410


def test_member_update_is_versioned_normalized_and_owner_role_cannot_be_assigned():
    db = _db()
    owner, invitee, _ = _users(db)
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    invite = create_invitation(
        db,
        household,
        owner,
        InvitationCreate(email=invitee.id, role=HouseholdRole.VIEWER),
    )
    member = accept_invitation(db, invite.acceptance_token, invitee)
    db.refresh(household)
    version_before = household.version
    updated = update_member(
        db,
        household,
        member.id,
        HouseholdMemberUpdate(
            display_name="  Household   Member  ",
            role=HouseholdRole.EDITOR,
            servings_multiplier=1.5,
            allergies=["Peanut", " peanut "],
        ),
    )
    assert updated.display_name == "Household Member"
    assert updated.role == HouseholdRole.EDITOR.value
    assert updated.servings_multiplier == 1.5
    assert updated.allergies == ["peanut"]
    db.expire_all()
    assert db.get(DBHousehold, household.id).version == version_before + 1

    with pytest.raises(ValidationError, match="Ownership transfer"):
        HouseholdMemberUpdate(role=HouseholdRole.OWNER)


def test_empty_and_whitespace_member_updates_are_rejected():
    with pytest.raises(ValidationError, match="At least one member field"):
        HouseholdMemberUpdate()
    with pytest.raises(ValidationError, match="display_name cannot be blank"):
        HouseholdMemberUpdate(display_name="   ")
    with pytest.raises(ValidationError):
        HouseholdMemberUpdate(allergies=[f"allergen-{index}" for index in range(101)])
