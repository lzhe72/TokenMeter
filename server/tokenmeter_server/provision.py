"""Explicit operator provisioning; there are no built-in production accounts."""
import time
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select

from .database import make_engine, transaction
from .migrations import assert_schema
from .models import AuditEvent, User
from .security import hash_password


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    username: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern=r"^(admin|member)$")
    is_active: bool

    @field_validator("username")
    @classmethod
    def normalize(cls, value):
        return value.lower()


def provision(database_url: str, accounts: list[dict]) -> int:
    entries = [AccountInput.model_validate(item) for item in accounts]
    if not entries or len({entry.username for entry in entries}) != len(entries):
        raise ValueError("Account input is empty or contains duplicate usernames")
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("Account input contains duplicate IDs")
    engine = make_engine(database_url)
    try:
        assert_schema(engine)
        with transaction(engine, write=True) as session:
            existing_admins = session.scalar(select(func.count()).select_from(User).where(
                User.role == "admin", User.is_active.is_(True)))
            if not existing_admins and not any(x.role == "admin" and x.is_active for x in entries):
                raise ValueError("Provisioning requires at least one active administrator")
            for entry in entries:
                if session.get(User, str(entry.id)) or session.scalar(select(User).where(User.username == entry.username)):
                    raise ValueError("Account already exists; refusing to overwrite credentials")
                session.add(User(id=str(entry.id), username=entry.username,
                                 password_hash=hash_password(entry.password), role=entry.role,
                                 is_active=entry.is_active, must_change_password=True, credential_version=1))
            session.flush()
            for entry in entries:
                session.add(AuditEvent(id=str(uuid4()), actor_id=None, target_id=str(entry.id),
                                       action="account_provisioned", occurred_at=int(time.time())))
        return len(entries)
    finally:
        engine.dispose()
