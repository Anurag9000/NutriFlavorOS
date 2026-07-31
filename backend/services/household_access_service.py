"""Role-based household access and invitation workflows."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import (
    DBHousehold,
    DBHouseholdInvitation,
    DBHouseholdMember,
    DBUser,
)
from backend.domain.household_access import (
    HouseholdMemberUpdate,
    HouseholdRole,
    InvitationCreate,
    InvitationView,
    ROLE_RANK,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


def _locked_household(db: Session, household_id: str) -> DBHousehold:
    household = (
        db.query(DBHousehold)
        .filter(DBHousehold.id == household_id)
        .with_for_update()
        .first()
    )
    if household is None:
        raise _not_found()
    return household


def _membership(
    db: Session, household_id: str, user_id: str
) -> Tuple[DBHousehold, HouseholdRole]:
    household = db.get(DBHousehold, household_id)
    if household is None:
        raise _not_found()
    if household.owner_user_id == user_id:
        return household, HouseholdRole.OWNER
    member = (
        db.query(DBHouseholdMember)
        .filter(
            DBHouseholdMember.household_id == household_id,
            DBHouseholdMember.linked_user_id == user_id,
            DBHouseholdMember.active.is_(True),
        )
        .first()
    )
    if member is None:
        raise _not_found()
    try:
        return household, HouseholdRole(member.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "invalid_household_role",
                "message": "Stored member role is invalid",
            },
        ) from exc


def require_household_access(
    db: Session,
    household_id: str,
    user_id: str,
    minimum_role: HouseholdRole = HouseholdRole.VIEWER,
) -> Tuple[DBHousehold, HouseholdRole]:
    household, role = _membership(db, household_id, user_id)
    if ROLE_RANK[role] < ROLE_RANK[minimum_role]:
        raise _not_found()
    return household, role


def list_accessible_households(
    db: Session, user_id: str
) -> List[Tuple[DBHousehold, HouseholdRole]]:
    owned = (
        db.query(DBHousehold)
        .filter(DBHousehold.owner_user_id == user_id)
        .order_by(DBHousehold.created_at, DBHousehold.id)
        .all()
    )
    result: List[Tuple[DBHousehold, HouseholdRole]] = [
        (value, HouseholdRole.OWNER) for value in owned
    ]
    member_rows = (
        db.query(DBHouseholdMember, DBHousehold)
        .join(DBHousehold, DBHousehold.id == DBHouseholdMember.household_id)
        .filter(
            DBHouseholdMember.linked_user_id == user_id,
            DBHouseholdMember.active.is_(True),
            DBHousehold.owner_user_id != user_id,
        )
        .order_by(DBHousehold.created_at, DBHousehold.id)
        .all()
    )
    for member, household in member_rows:
        try:
            result.append((household, HouseholdRole(member.role)))
        except ValueError:
            continue
    return result


def create_invitation(
    db: Session,
    household: DBHousehold,
    current_user: DBUser,
    payload: InvitationCreate,
) -> InvitationView:
    # Serialise invitation changes per household. This prevents two concurrent
    # requests for the same email from both creating active invitations.
    locked_household = _locked_household(db, household.id)
    if locked_household.owner_user_id != current_user.id:
        raise _not_found()

    email = normalize_email(str(payload.email))
    if email == current_user.id:
        raise HTTPException(
            status_code=422, detail="The household owner is already a member"
        )
    if (
        db.query(DBHouseholdMember)
        .filter(
            DBHouseholdMember.household_id == locked_household.id,
            DBHouseholdMember.linked_user_id == email,
        )
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=409, detail="That account is already a household member"
        )

    now = utcnow()
    duplicates = (
        db.query(DBHouseholdInvitation)
        .filter(
            DBHouseholdInvitation.household_id == locked_household.id,
            DBHouseholdInvitation.invited_email == email,
            DBHouseholdInvitation.accepted_at.is_(None),
            DBHouseholdInvitation.revoked_at.is_(None),
        )
        .order_by(DBHouseholdInvitation.id)
        .with_for_update()
        .all()
    )
    for invitation in duplicates:
        invitation.revoked_at = now
        db.add(invitation)

    token = secrets.token_urlsafe(48)
    invitation = DBHouseholdInvitation(
        id=str(uuid4()),
        household_id=locked_household.id,
        invited_email=email,
        role=payload.role.value,
        token_hash=_token_hash(token),
        expires_at=now + timedelta(hours=payload.expires_in_hours),
        created_by_user_id=current_user.id,
        created_at=now,
    )
    locked_household.version += 1
    locked_household.updated_at = now
    db.add_all([invitation, locked_household])
    db.commit()
    db.refresh(invitation)
    return InvitationView.model_validate(invitation).model_copy(
        update={"acceptance_token": token}
    )


def list_invitations(
    db: Session, household_id: str, include_closed: bool = False
) -> List[DBHouseholdInvitation]:
    query = db.query(DBHouseholdInvitation).filter(
        DBHouseholdInvitation.household_id == household_id
    )
    if not include_closed:
        query = query.filter(
            DBHouseholdInvitation.accepted_at.is_(None),
            DBHouseholdInvitation.revoked_at.is_(None),
            DBHouseholdInvitation.expires_at > utcnow(),
        )
    return query.order_by(
        DBHouseholdInvitation.created_at.desc(), DBHouseholdInvitation.id
    ).all()


def revoke_invitation(
    db: Session, household_id: str, invitation_id: str
) -> DBHouseholdInvitation:
    locked_household = _locked_household(db, household_id)
    invitation = (
        db.query(DBHouseholdInvitation)
        .filter(
            DBHouseholdInvitation.id == invitation_id,
            DBHouseholdInvitation.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if invitation is None:
        raise _not_found()
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=409, detail="Accepted invitations cannot be revoked"
        )
    if invitation.revoked_at is not None:
        return invitation

    now = utcnow()
    invitation.revoked_at = now
    locked_household.version += 1
    locked_household.updated_at = now
    db.add_all([invitation, locked_household])
    db.commit()
    db.refresh(invitation)
    return invitation


def accept_invitation(
    db: Session, token: str, current_user: DBUser
) -> DBHouseholdMember:
    token_hash = _token_hash(token)
    preliminary = (
        db.query(DBHouseholdInvitation)
        .filter(DBHouseholdInvitation.token_hash == token_hash)
        .first()
    )
    if preliminary is None:
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")

    # Lock in the same household -> invitation order used by create/revoke.
    household = _locked_household(db, preliminary.household_id)
    invitation = (
        db.query(DBHouseholdInvitation)
        .filter(
            DBHouseholdInvitation.id == preliminary.id,
            DBHouseholdInvitation.token_hash == token_hash,
        )
        .with_for_update()
        .first()
    )
    now = utcnow()
    if invitation is None or invitation.revoked_at is not None:
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")
    if normalize_email(current_user.id) != invitation.invited_email:
        raise HTTPException(
            status_code=403,
            detail="Sign in with the exact email address that was invited",
        )

    existing = (
        db.query(DBHouseholdMember)
        .filter(
            DBHouseholdMember.household_id == invitation.household_id,
            DBHouseholdMember.linked_user_id == current_user.id,
        )
        .with_for_update()
        .first()
    )
    if invitation.accepted_at is not None:
        if existing is not None:
            return existing
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")
    if _as_utc(invitation.expires_at) <= now:
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")

    if existing is None:
        member = DBHouseholdMember(
            household_id=invitation.household_id,
            display_name=current_user.name or current_user.id,
            linked_user_id=current_user.id,
            role=invitation.role,
            servings_multiplier=1.0,
            allergies=list(current_user.allergies or []),
            dietary_restrictions=list(current_user.dietary_restrictions or []),
            disliked_ingredients=list(current_user.disliked_ingredients or []),
            target_calories=current_user.target_calories,
            target_protein_g=current_user.target_protein_g,
            target_carbs_g=current_user.target_carbs_g,
            target_fat_g=current_user.target_fat_g,
            active=True,
            created_at=now,
        )
        db.add(member)
    else:
        member = existing
        member.role = invitation.role
        member.active = True
        db.add(member)

    invitation.accepted_at = now
    household.version += 1
    household.updated_at = now
    db.add_all([invitation, household])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent acceptance can win the unique linked-membership race.
        invitation = (
            db.query(DBHouseholdInvitation)
            .filter(DBHouseholdInvitation.token_hash == token_hash)
            .first()
        )
        existing = (
            db.query(DBHouseholdMember)
            .filter(
                DBHouseholdMember.household_id == preliminary.household_id,
                DBHouseholdMember.linked_user_id == current_user.id,
            )
            .first()
        )
        if invitation is not None and invitation.accepted_at is not None and existing is not None:
            return existing
        raise
    db.refresh(member)
    return member


def update_member(
    db: Session,
    household: DBHousehold,
    member_id: int,
    payload: HouseholdMemberUpdate,
) -> DBHouseholdMember:
    locked_household = _locked_household(db, household.id)
    member = (
        db.query(DBHouseholdMember)
        .filter(
            DBHouseholdMember.id == member_id,
            DBHouseholdMember.household_id == locked_household.id,
        )
        .with_for_update()
        .first()
    )
    if member is None:
        raise _not_found()
    if member.linked_user_id == locked_household.owner_user_id:
        raise HTTPException(
            status_code=409,
            detail="The household owner's membership cannot be edited through this endpoint",
        )

    values = payload.model_dump(exclude_unset=True)
    for field in (
        "allergies",
        "dietary_restrictions",
        "disliked_ingredients",
    ):
        if field in values:
            values[field] = sorted(
                {
                    str(item).strip().lower()
                    for item in values[field]
                    if str(item).strip()
                }
            )
    if "role" in values:
        values["role"] = values["role"].value
    for key, value in values.items():
        setattr(member, key, value)

    locked_household.version += 1
    locked_household.updated_at = utcnow()
    db.add_all([member, locked_household])
    db.commit()
    db.refresh(member)
    return member
