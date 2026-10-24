"""Identity operations and their small PostgreSQL-backed throttle."""

import hashlib
import hmac
import math
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import case, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.modules.customers.models import customers
from app.modules.identity.models import (
    auth_limits,
    identity_events,
    otp_challenges,
    roles,
    sessions,
    user_roles,
    users,
)

COOKIE_NAME = "experience_session"
SESSION_SECONDS = 24 * 60 * 60


def digest(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def event(connection, name, subject_id):
    connection.execute(
        insert(identity_events).values(
            id=uuid4(),
            event=name,
            subject_id=subject_id,
        )
    )


def lock_email(connection, email):
    lock_id = int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], signed=True)
    connection.execute(select(func.pg_advisory_xact_lock(lock_id)))


def throttle(engine, key, operation, ip, email=None):
    """Per-key windows start at the first attempt; rejected attempts stay counted."""
    if operation == "request":
        limits = [
            (f"send-ip:{ip}", 20, 3600),
            (f"send-minute:{email}", 1, 60),
            (f"send-hour:{email}", 5, 3600),
        ]
    elif operation == "booking":
        limits = [(f"booking-ip:{ip}", 30, 60), (f"booking-user:{email}", 15, 60)]
    elif operation == "options":
        limits = [(f"options-ip:{ip}", 30, 60), (f"options-user:{email}", 15, 60)]
    elif operation == "intent":
        limits = [(f"intent-ip:{ip}", 20, 60), (f"intent-user:{email}", 10, 60)]
    elif operation == "verify":
        limits = [(f"verify-ip:{ip}", 30, 600)]
    else:
        limits = [(f"session-ip:{ip}", 120, 60)]
    retry_after = 0
    with engine.begin() as connection:
        for name, maximum, seconds in limits:
            now = connection.scalar(select(func.clock_timestamp()))
            expired = auth_limits.c.reset_at <= now
            statement = (
                pg_insert(auth_limits)
                .values(
                    key=digest(key, f"limit:{name}"),
                    count=1,
                    reset_at=now + timedelta(seconds=seconds),
                )
                .on_conflict_do_update(
                    index_elements=[auth_limits.c.key],
                    set_={
                        "count": case(
                            (expired, 1),
                            else_=func.least(auth_limits.c.count + 1, maximum + 1),
                        ),
                        "reset_at": case(
                            (expired, now + timedelta(seconds=seconds)),
                            else_=auth_limits.c.reset_at,
                        ),
                    },
                )
                .returning(auth_limits.c.count, auth_limits.c.reset_at)
            )
            count, reset_at = connection.execute(statement).one()
            if count > maximum:
                retry_after = max(
                    retry_after, math.ceil((reset_at - now).total_seconds())
                )
                # A blocked IP must not create fresh email counters indefinitely.
                break
    return retry_after


def request_otp(engine, key, email, delivery):
    challenge_id = uuid4()
    code = f"{secrets.randbelow(1_000_000):06d}"
    with engine.begin() as connection:
        lock_email(connection, email)
        now = connection.scalar(select(func.clock_timestamp()))
        old_id = connection.scalar(
            select(otp_challenges.c.id).where(otp_challenges.c.email == email)
        )
        if old_id:
            event(connection, "otp_superseded", old_id)
        values = dict(
            id=challenge_id,
            email=email,
            code_hash=digest(key, f"otp:{challenge_id}:{code}"),
            expires_at=now + timedelta(minutes=5),
            attempts=0,
            consumed_at=None,
        )
        connection.execute(
            pg_insert(otp_challenges)
            .values(**values)
            .on_conflict_do_update(index_elements=[otp_challenges.c.email], set_=values)
        )
        event(connection, "otp_requested", challenge_id)
        delivery.send(email, code)
    return challenge_id


def revoke(connection, token, now):
    if not token or len(token) > 128:
        return
    revoked = (
        connection.execute(
            update(sessions)
            .where(
                sessions.c.token_hash == token_hash(token),
                sessions.c.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            .returning(sessions.c.id)
        )
        .scalars()
        .all()
    )
    for session_id in revoked:
        event(connection, "session_revoked", session_id)


def verify_otp(engine, key, challenge_id, code, old_token=None):
    with engine.begin() as connection:
        email = connection.scalar(
            select(otp_challenges.c.email).where(otp_challenges.c.id == challenge_id)
        )
        if email is None:
            return None
        lock_email(connection, email)
        challenge = (
            connection.execute(
                select(otp_challenges)
                .where(otp_challenges.c.id == challenge_id)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        now = connection.scalar(select(func.clock_timestamp()))
        if (
            not challenge
            or challenge["consumed_at"] is not None
            or challenge["expires_at"] <= now
            or challenge["attempts"] >= 5
        ):
            return None
        expected = digest(key, f"otp:{challenge_id}:{code}")
        if not hmac.compare_digest(challenge["code_hash"], expected):
            attempts = challenge["attempts"] + 1
            connection.execute(
                update(otp_challenges)
                .where(otp_challenges.c.id == challenge_id)
                .values(attempts=attempts)
            )
            event(
                connection,
                "otp_exhausted" if attempts == 5 else "otp_rejected",
                challenge_id,
            )
            return None  # Commit the failed-attempt count before the API rejects it.
        connection.execute(
            update(otp_challenges)
            .where(otp_challenges.c.id == challenge_id)
            .values(consumed_at=now)
        )
        event(connection, "otp_verified", challenge_id)
        user_id = connection.scalar(select(users.c.id).where(users.c.email == email))
        if user_id is None:
            user_id = uuid4()
            connection.execute(insert(users).values(id=user_id, email=email))
            role_id = connection.scalar(
                select(roles.c.id).where(roles.c.name == "customer")
            )
            connection.execute(
                insert(user_roles).values(user_id=user_id, role_id=role_id)
            )
            connection.execute(insert(customers).values(id=uuid4(), user_id=user_id))
            event(connection, "customer_registered", user_id)
        revoke(connection, old_token, now)
        token = secrets.token_urlsafe(32)
        session_id = uuid4()
        connection.execute(
            insert(sessions).values(
                id=session_id,
                user_id=user_id,
                token_hash=token_hash(token),
                expires_at=now + timedelta(seconds=SESSION_SECONDS),
            )
        )
        event(connection, "session_created", session_id)
    return token


def get_identity(engine, token):
    if not token or len(token) > 128:
        return None
    with engine.connect() as connection:
        identity = (
            connection.execute(
                select(
                    users.c.id,
                    users.c.email,
                    customers.c.id.label("customer_id"),
                )
                .join(sessions, sessions.c.user_id == users.c.id)
                .join(customers, customers.c.user_id == users.c.id)
                .where(
                    sessions.c.token_hash == token_hash(token),
                    sessions.c.revoked_at.is_(None),
                    sessions.c.expires_at > func.clock_timestamp(),
                )
            )
            .mappings()
            .first()
        )
        if identity is None:
            return None
        identity = dict(identity)
        identity["roles"] = list(
            connection.execute(
                select(roles.c.name)
                .join(user_roles, user_roles.c.role_id == roles.c.id)
                .where(user_roles.c.user_id == identity["id"])
                .order_by(roles.c.name)
            ).scalars()
        )
        return identity


def logout(engine, token):
    with engine.begin() as connection:
        revoke(connection, token, connection.scalar(select(func.clock_timestamp())))
