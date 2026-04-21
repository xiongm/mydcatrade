from datetime import datetime
from dca_backtest.schedules import is_contribution_day

def test_weekly_schedule():
    # 2026-04-15 is a Wednesday
    assert is_contribution_day(datetime(2026, 4, 15), 'weekly') is True
    # 2026-04-16 is a Thursday
    assert is_contribution_day(datetime(2026, 4, 16), 'weekly') is False

def test_monthly_schedule():
    # First Wednesday of April 2026 is April 1st
    assert is_contribution_day(datetime(2026, 4, 1), 'monthly') is True
    # Second Wednesday is not
    assert is_contribution_day(datetime(2026, 4, 8), 'monthly') is False

def test_biweekly_schedule():
    start_date = datetime(2026, 4, 1) # A Wednesday
    # First Wednesday (Week 0)
    assert is_contribution_day(datetime(2026, 4, 1), 'biweekly', start_date) is True
    # Second Wednesday (Week 1)
    assert is_contribution_day(datetime(2026, 4, 8), 'biweekly', start_date) is False
    # Third Wednesday (Week 2)
    assert is_contribution_day(datetime(2026, 4, 15), 'biweekly', start_date) is True
