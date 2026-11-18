"""Versioned SQLite foundation; all seed identities are fictional."""
import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    if version > 1:
        raise ValueError('Database schema is newer than this code')
    if version == 0:
        with connection:
            connection.execute('CREATE TABLE employees (id TEXT PRIMARY KEY, display_name TEXT NOT NULL)')
            connection.execute('CREATE TABLE leave_balances (employee_id TEXT NOT NULL REFERENCES employees(id), leave_type TEXT NOT NULL, days REAL NOT NULL CHECK(days >= 0), PRIMARY KEY(employee_id, leave_type))')
            connection.execute('PRAGMA user_version = 1')
    connection.execute('PRAGMA foreign_keys = ON')


def seed_synthetic(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute("INSERT OR IGNORE INTO employees VALUES ('demo-001', 'Fictional Employee')")
        connection.execute("INSERT OR IGNORE INTO leave_balances VALUES ('demo-001', 'demo', 0)")
