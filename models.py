from app import db
from datetime import datetime
from sqlalchemy import Text, LargeBinary
from werkzeug.security import generate_password_hash, check_password_hash

class Site(db.Model):
    __tablename__ = 'sites'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    protocol = db.Column(db.String(10), nullable=False)  # 'ftp' or 'sftp'
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=21)
    username = db.Column(db.String(100), nullable=False)
    password_encrypted = db.Column(LargeBinary, nullable=False)
    remote_path = db.Column(db.String(500), default='/')
    transfer_type = db.Column(db.String(20), default='files')  # 'files' or 'folders'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', foreign_keys='Job.site_id', backref='site', lazy=True, cascade='all, delete-orphan')

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    job_type = db.Column(db.String(20), nullable=False)  # 'download', 'upload'
    schedule_type = db.Column(db.String(20), nullable=False)  # 'one_time', 'recurring'
    schedule_datetime = db.Column(db.DateTime, nullable=True)
    cron_expression = db.Column(db.String(100), nullable=True)
    use_date_range = db.Column(db.Boolean, default=False)
    date_from = db.Column(db.DateTime, nullable=True)
    date_to = db.Column(db.DateTime, nullable=True)
    use_rolling_date_range = db.Column(db.Boolean, default=False)
    rolling_pattern = db.Column(db.String(50), nullable=True)  # 'prev_month_26_to_curr_25', 'prev_month_full', etc.
    date_offset_from = db.Column(db.Integer, nullable=True)  # Days offset from reference point
    date_offset_to = db.Column(db.Integer, nullable=True)  # Days offset to reference point
    download_all = db.Column(db.Boolean, default=False)
    local_path = db.Column(db.String(500), nullable=True)
    target_site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=True)  # For upload jobs
    status = db.Column(db.String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    target_site = db.relationship('Site', foreign_keys=[target_site_id], backref='upload_jobs')
    logs = db.relationship('JobLog', backref='job', lazy=True, cascade='all, delete-orphan')

class JobLog(db.Model):
    __tablename__ = 'job_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False)  # 'running', 'completed', 'failed'
    files_processed = db.Column(db.Integer, default=0)
    bytes_transferred = db.Column(db.BigInteger, default=0)
    error_message = db.Column(Text, nullable=True)
    log_content = db.Column(Text, nullable=True)

class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(Text, nullable=True)
    encrypted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemLog(db.Model):
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False)  # 'info', 'warning', 'error'
    message = db.Column(Text, nullable=False)
    component = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
