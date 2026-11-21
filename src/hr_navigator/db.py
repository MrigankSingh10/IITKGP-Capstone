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


def seed_scenario_fixtures(connection: sqlite3.Connection, fixture_path) -> None:
    """Seed the explicitly fictional scenario dataset; do not overwrite existing records."""
    import json
    from pathlib import Path

    fixture = json.loads(Path(fixture_path).read_text(encoding='utf-8'))
    if not fixture.get('label', '').startswith('SYNTHETIC'):
        raise ValueError('Synthetic fixture required')
    with connection:
        connection.execute('CREATE TABLE IF NOT EXISTS synthetic_employee_details '
                           '(employee_id TEXT PRIMARY KEY REFERENCES employees(id), state TEXT NOT NULL)')
        for employee in fixture['employees']:
            # A conflicting placeholder or modified fixture must be resolved explicitly.
            existing = connection.execute('SELECT display_name FROM employees WHERE id = ?',
                                          (employee['id'],)).fetchone()
            if existing and existing[0] != employee['display_name']:
                raise ValueError('Employee conflicts with existing seed')
            connection.execute('INSERT OR IGNORE INTO employees VALUES (?, ?)',
                               (employee['id'], employee['display_name']))
            connection.execute('INSERT OR IGNORE INTO synthetic_employee_details VALUES (?, ?)',
                               (employee['id'], employee['state']))
        for balance in fixture['leave_balances']:
            connection.execute('INSERT OR IGNORE INTO leave_balances VALUES (?, ?, ?)',
                               (balance['employee_id'], balance['leave_type'], balance['days']))
