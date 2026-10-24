"""Quiescent disposable-test DB only; backup bytes never leave its container."""

import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.config import load_settings

ROOT = Path(__file__).resolve().parents[2]


def snapshot(engine):
    result = {}
    with engine.connect() as conn:
        tables = conn.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "ORDER BY tablename"
            )
        ).all()
        if not {"alembic_version", "users", "audit_events", "cases"} <= set(tables):
            raise RuntimeError("Migrate the disposable database first")
        for table in tables:
            if not re.fullmatch(r"[a-z_]+", table):
                raise RuntimeError("Unexpected table identifier")
            digest = hashlib.sha256()
            count = 0
            for row in conn.scalars(
                text(
                    f'SELECT row_to_json(t)::text FROM public."{table}" t '
                    "ORDER BY row_to_json(t)::text"
                )
            ):
                digest.update(row.encode() + b"\n")
                count += 1
            result[table] = (count, digest.digest())
    return result


def verify(project):
    settings = load_settings()
    if settings.environment != "test" or not re.fullmatch(
        r"experience-[a-z0-9-]+", project
    ):
        raise RuntimeError("Requires test configuration and experience-* project")
    url = make_url(settings.database_url)
    target = "experience_restore_" + uuid4().hex
    dump = "/tmp/" + target + ".dump"
    prefix = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        project,
        "-f",
        str(ROOT / "infra/compose.yml"),
        "exec",
        "-T",
        "db",
    ]

    def run(*args):
        # Never print subprocess errors: database output may contain private data.
        completed = subprocess.run(prefix + list(args), capture_output=True, timeout=90)
        if completed.returncode:
            raise RuntimeError("Disposable database command failed; output withheld")
        return completed.stdout

    engine = create_engine(url, hide_parameters=True)
    restored = create_engine(url.set(database=target), hide_parameters=True)
    created = False
    try:
        with engine.begin() as conn:
            if conn.scalar(text("SELECT current_database()")) != "experience_test":
                raise RuntimeError("Refusing non-test database")
            # Synthetic marker makes an empty-data restore insufficient evidence.
            conn.execute(
                text("INSERT INTO users(id,email) VALUES (:id,:email)"),
                {"id": uuid4(), "email": target + "@recovery.invalid"},
            )
        before = snapshot(engine)
        run("pg_dump", "-U", url.username, "-d", "experience_test", "-Fc", "-f", dump)
        run("createdb", "-U", url.username, "--template=template0", target)
        created = True
        run(
            "pg_restore",
            "-U",
            url.username,
            "--exit-on-error",
            "--single-transaction",
            "-d",
            target,
            dump,
        )
        if snapshot(engine) != before or snapshot(restored) != before:
            raise RuntimeError("Restore mismatch or source changed during verification")
        for statement, sqlstate in (
            ("DELETE FROM audit_events", "P0001"),
            (
                "INSERT INTO customers(id,user_id) VALUES "
                "(gen_random_uuid(),gen_random_uuid())",
                "23503",
            ),
        ):
            try:
                with restored.begin() as conn:
                    conn.execute(text(statement))
            except DBAPIError as error:
                if getattr(error.orig, "sqlstate", None) != sqlstate:
                    raise RuntimeError("Unexpected restored database failure") from None
            else:
                raise RuntimeError("Restored integrity protection missing")
        print(
            f"Backup/restore passed: {len(before)} tables match; "
            "audit immutability and foreign keys enforced"
        )
    finally:
        engine.dispose()
        restored.dispose()
        try:
            if created:
                run("dropdb", "-U", url.username, target)
        finally:
            run("rm", "-f", dump)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    try:
        verify(args.project)
    except Exception:
        raise SystemExit(
            "Backup/restore verification failed; details withheld"
        ) from None
