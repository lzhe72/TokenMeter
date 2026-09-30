"""TokenMeter authentication API. All identities and revocations live in the DB."""
import hashlib
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from starlette.exceptions import HTTPException

from .database import make_engine, transaction
from .migrations import assert_schema
from .models import AuditEvent, AuthSession, LoginBucket, User
from .security import hash_password, verify_password

SESSION_SECONDS = 30 * 24 * 60 * 60
FAILURE_LIMIT = 5
WINDOW_SECONDS = 300
DUMMY_HASH = hash_password("TokenMeter credential timing comparison")


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginInput(Input):
    username: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
    password: str = Field(min_length=1, max_length=128)


class PasswordInput(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ResetInput(Input):
    temporary_password: str = Field(min_length=12, max_length=128)


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def public_user(user):
    return {"id": user.id, "username": user.username, "role": user.role,
            "is_active": user.is_active, "must_change_password": user.must_change_password}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(session, actor, target, action, now):
    session.add(AuditEvent(id=str(uuid4()), actor_id=actor, target_id=target,
                           action=action, occurred_at=now))


def authenticate(session, request, now, *, admin=False):
    authorization = request.headers.get("authorization", "")
    parts = authorization.split()
    record = None
    if len(parts) == 2 and parts[0].lower() == "bearer" and len(parts[1]) == 43:
        record = session.get(AuthSession, digest(parts[1]))
    user = session.get(User, record.user_id) if record else None
    if (not record or not user or not user.is_active or record.expires_at <= now
            or record.credential_version != user.credential_version):
        raise APIError(401, "invalid_session", "登录已失效，请重新登录")
    if admin:
        if user.must_change_password:
            raise APIError(403, "password_change_required", "请先修改初始密码")
        if user.role != "admin":
            raise APIError(403, "forbidden", "没有管理员权限")
    return user, record


def issue(session, user, now):
    token = secrets.token_urlsafe(32)
    expires_at = now + SESSION_SECONDS
    session.add(AuthSession(token_hash=digest(token), user_id=user.id,
                            credential_version=user.credential_version, expires_at=expires_at))
    return {"access_token": token, "token_type": "bearer", "expires_at": iso(expires_at),
            "user": public_user(user)}


def revoke_all(session, user):
    user.credential_version += 1
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))


def create_app(database_url: str | None = None, *, clock=None) -> FastAPI:
    # Dependency injection is Python-only for deterministic API tests; no HTTP
    # route, environment variable or production auth bypass can set the clock.
    now = lambda: int((clock or time.time)())

    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(database_url or os.getenv("TOKENMETER_DATABASE_URL", ""))
        try:
            assert_schema(engine)
            app.state.engine = engine
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="TokenMeter", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(APIError)
    async def api_error(_request, error):
        headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else {}
        if error.status == 429:
            headers["Retry-After"] = str(WINDOW_SECONDS)
        return JSONResponse(status_code=error.status,
                            content={"error": {"code": error.code, "message": error.message}}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # Pydantic error dictionaries include raw inputs; never return them.
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "输入格式无效，请检查用户名和密码要求"}})

    @app.exception_handler(HTTPException)
    async def http_error(_request, error):
        return JSONResponse(status_code=error.status_code, content={"error": {
            "code": "not_found" if error.status_code == 404 else "request_rejected",
            "message": "请求的接口不存在" if error.status_code == 404 else "请求无法处理"}})

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/v1/health")
    def health():
        assert_schema(app.state.engine)
        return {"status": "ok", "schema_version": "0001"}

    @app.post("/v1/auth/login")
    def login(body: LoginInput, request: Request):
        username = body.username.lower()
        instant = now()
        source = request.client.host if request.client else "unknown"
        keys = ["user:" + digest(username), "source:" + digest(source)]
        error = None
        response = None
        with transaction(app.state.engine, write=True) as session:
            buckets = [session.get(LoginBucket, key) for key in keys]
            if any(bucket and instant < bucket.window_start + WINDOW_SECONDS
                   and bucket.failures >= FAILURE_LIMIT for bucket in buckets):
                raise APIError(429, "rate_limited", "登录失败次数过多，请稍后重试")
            user = session.scalar(select(User).where(User.username == username))
            valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
            if not valid or not user:
                for key, bucket in zip(keys, buckets):
                    if bucket is None:
                        session.add(LoginBucket(key=key, failures=1, window_start=instant))
                    elif instant >= bucket.window_start + WINDOW_SECONDS:
                        bucket.failures, bucket.window_start = 1, instant
                    else:
                        bucket.failures += 1
                error = APIError(401, "invalid_credentials", "用户名或密码错误")
            elif not user.is_active:
                error = APIError(403, "account_disabled", "账号已停用，请联系管理员")
            else:
                # Successful usernames cannot erase failures for the whole IP.
                session.execute(delete(LoginBucket).where(LoginBucket.key == keys[0]))
                response = issue(session, user, instant)
                audit(session, user.id, user.id, "login", instant)
        # Commit failed-login counters before returning the stable error.
        if error:
            raise error
        return response

    @app.get("/v1/me")
    def me(request: Request):
        with transaction(app.state.engine) as session:
            user, _ = authenticate(session, request, now())
            return public_user(user)

    @app.post("/v1/auth/change-password")
    def change_password(body: PasswordInput, request: Request):
        instant = now()
        with transaction(app.state.engine, write=True) as session:
            user, _ = authenticate(session, request, instant)
            if not verify_password(body.current_password, user.password_hash):
                raise APIError(401, "invalid_credentials", "当前密码错误")
            if verify_password(body.new_password, user.password_hash):
                raise APIError(409, "password_unchanged", "新密码不能与当前密码相同")
            user.password_hash = hash_password(body.new_password)
            user.must_change_password = False
            revoke_all(session, user)
            response = issue(session, user, instant)
            audit(session, user.id, user.id, "password_changed", instant)
            return response

    @app.post("/v1/auth/logout", status_code=204)
    def logout(request: Request):
        instant = now()
        with transaction(app.state.engine, write=True) as session:
            user, record = authenticate(session, request, instant)
            session.delete(record)
            audit(session, user.id, user.id, "logout", instant)
        return Response(status_code=204)

    @app.get("/v1/admin/users")
    def users(request: Request):
        with transaction(app.state.engine) as session:
            authenticate(session, request, now(), admin=True)
            return {"users": [public_user(user) for user in session.scalars(select(User).order_by(User.username))]}

    def manage(user_id, request, action, password=None):
        instant = now()
        with transaction(app.state.engine, write=True) as session:
            actor, _ = authenticate(session, request, instant, admin=True)
            target = session.get(User, user_id)
            if not target:
                raise APIError(404, "not_found", "账号不存在")
            if action == "account_disabled":
                # SQLite serializes this read/check/write with BEGIN IMMEDIATE.
                active_admins = session.scalar(select(func.count()).select_from(User).where(
                    User.role == "admin", User.is_active.is_(True)))
                if target.id == actor.id or (target.role == "admin" and target.is_active and active_admins <= 1):
                    raise APIError(409, "admin_protected", "不能停用自己或最后一个活动管理员")
                target.is_active = False
                revoke_all(session, target)
            elif action == "account_enabled":
                target.is_active = True
            else:
                if verify_password(password, target.password_hash):
                    raise APIError(409, "password_unchanged", "临时密码不能与当前密码相同")
                target.password_hash = hash_password(password)
                target.must_change_password = True
                revoke_all(session, target)
            audit(session, actor.id, target.id, action, instant)
            return public_user(target)

    @app.post("/v1/admin/users/{user_id}/disable")
    def disable(user_id: str, request: Request):
        return manage(user_id, request, "account_disabled")

    @app.post("/v1/admin/users/{user_id}/enable")
    def enable(user_id: str, request: Request):
        return manage(user_id, request, "account_enabled")

    @app.post("/v1/admin/users/{user_id}/reset-password")
    def reset_password(user_id: str, body: ResetInput, request: Request):
        return manage(user_id, request, "password_reset", body.temporary_password)

    @app.get("/v1/admin/audit")
    def audit_events(request: Request):
        with transaction(app.state.engine) as session:
            authenticate(session, request, now(), admin=True)
            events = session.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id).limit(100))
            return {"events": [{"id": item.id, "actor_id": item.actor_id, "target_id": item.target_id,
                                "action": item.action, "occurred_at": iso(item.occurred_at)} for item in events]}

    return app


app = create_app()
