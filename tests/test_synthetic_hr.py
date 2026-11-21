from datetime import date
from pathlib import Path
import sqlite3

import pytest

from hr_navigator.db import migrate, seed_scenario_fixtures
from hr_navigator.tools.synthetic_hr import SyntheticHRTools, ToolError, TrustedIdentity

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tools():
    connection = sqlite3.connect(':memory:')
    migrate(connection)
    fixtures = ROOT / 'evaluation/scenario_fixtures_v0.1.json'
    seed_scenario_fixtures(connection, fixtures)
    seed_scenario_fixtures(connection, fixtures)
    return SyntheticHRTools(connection, ROOT / 'data/synthetic/acme_handbook_v0.1.json')


def test_identity_scoped_profile_and_balance(tools):
    asha = TrustedIdentity(employee_id='demo-001')
    vikram = TrustedIdentity(employee_id='demo-002')
    assert tools.get_employee_profile(asha).display_name == 'Asha Rao'
    assert tools.get_leave_balance(asha, 'annual').days == 12
    assert tools.get_leave_balance(vikram, 'annual').days == 2
    with pytest.raises(ToolError):
        tools.get_leave_balance({'employee_id': 'demo-002'}, 'annual')
    with pytest.raises(ToolError):
        tools.get_employee_profile(TrustedIdentity(employee_id='unknown'))
    with pytest.raises(ToolError):
        tools.get_leave_balance(asha, 'unknown')


def test_inclusive_workdays_exclude_weekends_and_holidays(tools):
    result = tools.calculate_leave_days(date(2027, 1, 25), date(2027, 1, 27), 'Karnataka', '0.1-draft')
    assert result.working_days == 2
    assert tools.calculate_leave_days(date(2027, 1, 23), date(2027, 1, 24), 'Karnataka', '0.1-draft').working_days == 0


def test_fail_closed_for_missing_policy_calendar_and_balance(tools):
    with pytest.raises(ToolError, match='Invalid'):
        tools.calculate_leave_days(date(2027, 2, 2), date(2027, 2, 1), 'Karnataka', '0.1-draft')
    for state, start, end, version in [
        ('Maharashtra', date(2027, 1, 1), date(2027, 1, 2), '0.1-draft'),
        ('Karnataka', date(2027, 12, 31), date(2028, 1, 1), '0.1-draft'),
        ('Karnataka', date(2027, 1, 1), date(2027, 1, 2), 'unknown'),
    ]:
        with pytest.raises(ToolError):
            tools.calculate_leave_days(start, end, state, version)
    with pytest.raises(ToolError, match='Insufficient'):
        tools.check_leave_balance(TrustedIdentity(employee_id='demo-002'), 'annual', date(2027, 1, 18), date(2027, 1, 22), '0.1-draft')
    with pytest.raises(ToolError, match='policy'):
        tools.check_leave_balance(TrustedIdentity(employee_id='demo-001'), 'other', date(2027, 1, 18), date(2027, 1, 18), '0.1-draft')
