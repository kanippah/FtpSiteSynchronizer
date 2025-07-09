import os
import logging
from datetime import datetime
from app import db
from models import SystemLog, Settings
from crypto_utils import encrypt_text, decrypt_text

logger = logging.getLogger(__name__)

def log_system_message(level, message, component=None):
    """Log a system message to database"""
    try:
        log_entry = SystemLog(
            level=level,
            message=message,
            component=component,
            created_at=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to Python logger
        if level == 'info':
            logger.info(f"[{component}] {message}")
        elif level == 'warning':
            logger.warning(f"[{component}] {message}")
        elif level == 'error':
            logger.error(f"[{component}] {message}")
        
    except Exception as e:
        logger.error(f"Error logging system message: {str(e)}")

def get_setting(key, default=None, encrypted=False):
    """Get a setting value"""
    try:
        setting = Settings.query.filter_by(key=key).first()
        
        if not setting:
            return default
        
        if encrypted and setting.encrypted:
            return decrypt_text(setting.value) if setting.value else default
        else:
            return setting.value or default
            
    except Exception as e:
        logger.error(f"Error getting setting {key}: {str(e)}")
        return default

def set_setting(key, value, encrypted=False):
    """Set a setting value"""
    try:
        setting = Settings.query.filter_by(key=key).first()
        
        if not setting:
            setting = Settings(key=key)
            db.session.add(setting)
        
        if encrypted and value:
            setting.value = encrypt_text(value)
            setting.encrypted = True
        else:
            setting.value = value
            setting.encrypted = False
        
        setting.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting {key}: {str(e)}")
        db.session.rollback()
        return False

def ensure_directory_exists(path):
    """Ensure a directory exists"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {path}: {str(e)}")
        return False

def format_bytes(bytes_count):
    """Format bytes into human readable format"""
    try:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"
    except:
        return "0 B"

def format_datetime(dt):
    """Format datetime for display"""
    try:
        if not dt:
            return "Never"
        
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Invalid date"

def get_file_extension(filename):
    """Get file extension"""
    try:
        return os.path.splitext(filename)[1].lower()
    except:
        return ""

def validate_cron_expression(cron_expr):
    """Basic validation of cron expression"""
    try:
        parts = cron_expr.split()
        if len(parts) != 5:
            return False, "Cron expression must have 5 parts"
        
        # Basic validation (minute, hour, day, month, day_of_week)
        ranges = [
            (0, 59),    # minute
            (0, 23),    # hour
            (1, 31),    # day
            (1, 12),    # month
            (0, 6)      # day_of_week
        ]
        
        for i, part in enumerate(parts):
            if part == '*':
                continue
            
            # Handle ranges like 0-5
            if '-' in part:
                start, end = part.split('-', 1)
                start_val = int(start)
                end_val = int(end)
                
                if start_val < ranges[i][0] or end_val > ranges[i][1] or start_val > end_val:
                    return False, f"Invalid range in part {i+1}: {part}"
            
            # Handle lists like 1,3,5
            elif ',' in part:
                values = part.split(',')
                for val in values:
                    val_int = int(val)
                    if val_int < ranges[i][0] or val_int > ranges[i][1]:
                        return False, f"Invalid value in part {i+1}: {val}"
            
            # Handle single values
            else:
                val_int = int(part)
                if val_int < ranges[i][0] or val_int > ranges[i][1]:
                    return False, f"Invalid value in part {i+1}: {part}"
        
        return True, "Valid cron expression"
        
    except Exception as e:
        return False, f"Error validating cron expression: {str(e)}"

def cleanup_old_logs(days_to_keep=30):
    """Clean up old log entries"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Clean up job logs
        old_job_logs = JobLog.query.filter(JobLog.start_time < cutoff_date).all()
        for log in old_job_logs:
            db.session.delete(log)
        
        # Clean up system logs
        old_system_logs = SystemLog.query.filter(SystemLog.created_at < cutoff_date).all()
        for log in old_system_logs:
            db.session.delete(log)
        
        db.session.commit()
        
        log_system_message('info', f'Cleaned up logs older than {days_to_keep} days', 'cleanup')
        
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {str(e)}")
        db.session.rollback()

def calculate_rolling_date_range(rolling_pattern, reference_date=None, date_offset_from=None, date_offset_to=None):
    """Calculate rolling date range based on pattern and reference date"""
    if reference_date is None:
        reference_date = datetime.utcnow()
    
    # Handle custom pattern with user-defined offsets
    if rolling_pattern == 'custom' and date_offset_from is not None and date_offset_to is not None:
        # Previous month day X to current month day Y
        prev_month = reference_date.month - 1 if reference_date.month > 1 else 12
        prev_year = reference_date.year if reference_date.month > 1 else reference_date.year - 1
        
        # Handle edge case where day doesn't exist in the month (e.g., Feb 30)
        try:
            date_from = datetime(prev_year, prev_month, date_offset_from, 0, 0, 0)
        except ValueError:
            # If day doesn't exist, use last day of month
            from calendar import monthrange
            last_day = monthrange(prev_year, prev_month)[1]
            date_from = datetime(prev_year, prev_month, min(date_offset_from, last_day), 0, 0, 0)
        
        try:
            date_to = datetime(reference_date.year, reference_date.month, date_offset_to, 23, 59, 59)
        except ValueError:
            # If day doesn't exist, use last day of month
            from calendar import monthrange
            last_day = monthrange(reference_date.year, reference_date.month)[1]
            date_to = datetime(reference_date.year, reference_date.month, min(date_offset_to, last_day), 23, 59, 59)
        
        return date_from, date_to
    
    patterns = {
        'prev_month_26_to_curr_25': {
            'from_offset': lambda ref: datetime(ref.year, ref.month - 1 if ref.month > 1 else 12, 26, 0, 0, 0) if ref.month > 1 else datetime(ref.year - 1, 12, 26, 0, 0, 0),
            'to_offset': lambda ref: datetime(ref.year, ref.month, 25, 23, 59, 59)
        },
        'prev_month_full': {
            'from_offset': lambda ref: datetime(ref.year, ref.month - 1 if ref.month > 1 else 12, 1, 0, 0, 0) if ref.month > 1 else datetime(ref.year - 1, 12, 1, 0, 0, 0),
            'to_offset': lambda ref: (datetime(ref.year, ref.month, 1, 0, 0, 0) - timedelta(days=1)).replace(hour=23, minute=59, second=59)
        },
        'curr_month_1_to_25': {
            'from_offset': lambda ref: datetime(ref.year, ref.month, 1, 0, 0, 0),
            'to_offset': lambda ref: datetime(ref.year, ref.month, 25, 23, 59, 59)
        },
        'prev_15_days': {
            'from_offset': lambda ref: (ref - timedelta(days=15)).replace(hour=0, minute=0, second=0, microsecond=0),
            'to_offset': lambda ref: ref.replace(hour=23, minute=59, second=59, microsecond=0)
        },
        'last_30_days': {
            'from_offset': lambda ref: (ref - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0),
            'to_offset': lambda ref: ref.replace(hour=23, minute=59, second=59, microsecond=0)
        }
    }
    
    if rolling_pattern not in patterns:
        raise ValueError(f"Unknown rolling pattern: {rolling_pattern}")
    
    pattern = patterns[rolling_pattern]
    date_from = pattern['from_offset'](reference_date)
    date_to = pattern['to_offset'](reference_date)
    
    return date_from, date_to
