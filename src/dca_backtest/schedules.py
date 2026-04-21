from datetime import datetime, timedelta
from typing import Optional

def is_contribution_day(dt: datetime, frequency: str, start_date: Optional[datetime] = None) -> bool:
    """
    Checks if a given date is a scheduled contribution day (Wednesday-based).
    """
    if dt.weekday() != 2:  # 0=Monday, 1=Tuesday, 2=Wednesday
        return False
    
    if frequency == 'weekly':
        return True
    
    if frequency == 'monthly':
        # Check if it's the first Wednesday (day of month <= 7)
        return dt.day <= 7
    
    if frequency == 'biweekly':
        if start_date is None:
            # If no start_date, default to every Wednesday for safety
            return True
        
        # Calculate full weeks since start_date (which must be a Wednesday)
        # We ensure we're comparing Wednesdays
        days_since = (dt.date() - start_date.date()).days
        weeks_since = days_since // 7
        return weeks_since % 2 == 0
    
    return False
