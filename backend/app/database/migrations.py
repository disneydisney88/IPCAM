from __future__ import annotations

from app.database.core import Base, engine


CURRENT_SCHEMA_VERSION = 5


def _table_columns(connection, table_name: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").mappings().all()
    return {row["name"] for row in rows}


def _add_column(connection, table_name: str, column_sql: str, column_name: str) -> None:
    if column_name not in _table_columns(connection, table_name):
        connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def migrate_database() -> int:
    """Apply idempotent local SQLite migrations and return the schema version.

    Version 4 adds scheduler run history without changing or deleting existing data.
    Version 5 adds GeoIP location columns to cameras and external targets.
    """
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS external_targets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port_overrides TEXT,
                enabled INTEGER DEFAULT 1,
                notes TEXT,
                last_scan TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                target_id TEXT,
                target_name TEXT,
                details JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_audit_logs_status ON audit_logs(status)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_audit_logs_target_id ON audit_logs(target_id)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)")
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS scheduler_runs (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                targets_count INTEGER DEFAULT 0,
                succeeded INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                cancelled INTEGER DEFAULT 0,
                duration_seconds FLOAT
            )
            """
        )
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_scheduler_runs_status ON scheduler_runs(status)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_scheduler_runs_started_at ON scheduler_runs(started_at)")
        _add_column(connection, "cameras", "connection_type TEXT DEFAULT 'lan'", "connection_type")
        _add_column(connection, "cameras", "host TEXT", "host")
        _add_column(connection, "cameras", "resolved_ip TEXT", "resolved_ip")
        _add_column(connection, "cameras", "snapshot_url TEXT", "snapshot_url")
        _add_column(connection, "cameras", "model_specs TEXT", "model_specs")
        _add_column(connection, "cameras", "sort_order INTEGER DEFAULT 0", "sort_order")
        _add_column(connection, "cameras", "latitude REAL", "latitude")
        _add_column(connection, "cameras", "longitude REAL", "longitude")
        _add_column(connection, "cameras", "country TEXT", "country")
        _add_column(connection, "cameras", "city TEXT", "city")
        _add_column(connection, "cameras", "isp TEXT", "isp")
        _add_column(connection, "external_targets", "latitude REAL", "latitude")
        _add_column(connection, "external_targets", "longitude REAL", "longitude")
        _add_column(connection, "external_targets", "country TEXT", "country")
        _add_column(connection, "external_targets", "city TEXT", "city")
        current = int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())
        if current < CURRENT_SCHEMA_VERSION:
            connection.exec_driver_sql(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            current = CURRENT_SCHEMA_VERSION
    return current
