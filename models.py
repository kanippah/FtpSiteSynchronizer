from app import db
from datetime import datetime
from sqlalchemy import Text, LargeBinary
from werkzeug.security import generate_password_hash, check_password_hash

class Site(db.Model):
    __tablename__ = 'sites'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    protocol = db.Column(db.String(10), nullable=False)  # 'ftp', 'sftp', or 'nfs'
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=21)
    username = db.Column(db.String(100), nullable=False)
    password_encrypted = db.Column(LargeBinary, nullable=False)
    remote_path = db.Column(db.String(500), default='/')
    transfer_type = db.Column(db.String(20), default='files')  # 'files' or 'folders'
    
    # NFS-specific fields
    nfs_export_path = db.Column(db.String(500), nullable=True)  # NFS export path on server
    nfs_version = db.Column(db.String(10), nullable=True, default='4')  # NFS version (3, 4, 4.1, 4.2)
    nfs_mount_options = db.Column(db.String(200), nullable=True)  # Custom mount options
    nfs_auth_method = db.Column(db.String(20), nullable=True, default='sys')  # sys, krb5, krb5i, krb5p
    

    
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
    use_filename_date_filter = db.Column(db.Boolean, default=False)  # Filter by date in filename
    filename_date_pattern = db.Column(db.String(50), nullable=True)  # Date pattern in filename (e.g., YYYYMMDD)
    local_path = db.Column(db.String(500), nullable=True)
    target_site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=True)  # For upload jobs
    
    # Advanced download options (moved from sites to jobs for better granularity)
    enable_recursive_download = db.Column(db.Boolean, default=False)  # Traverse all subfolders and download files only
    enable_duplicate_renaming = db.Column(db.Boolean, default=False)  # Auto-rename duplicate files with _1, _2, etc.
    use_date_folders = db.Column(db.Boolean, default=False)  # Create date-based folders for downloads
    date_folder_format = db.Column(db.String(20), default='YYYY-MM-DD')  # Date format for folder creation
    
    # Job grouping for organized execution
    job_group_id = db.Column(db.Integer, db.ForeignKey('job_groups.id'), nullable=True)  # Optional group assignment
    status = db.Column(db.String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    target_site = db.relationship('Site', foreign_keys=[target_site_id], backref='upload_jobs')
    job_group = db.relationship('JobGroup', backref='jobs', lazy=True)
    logs = db.relationship('JobLog', backref='job', lazy=True, cascade='all, delete-orphan')

class JobGroup(db.Model):
    __tablename__ = 'job_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(Text, nullable=True)
    group_folder_name = db.Column(db.String(100), nullable=False)  # Custom folder name within YYYY-MM
    enable_date_organization = db.Column(db.Boolean, default=True)  # Create YYYY-MM folders
    date_folder_format = db.Column(db.String(20), default='YYYY-MM')  # Date format for group folders
    execution_order = db.Column(db.Integer, default=0)  # Order of execution within group
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NetworkDrive(db.Model):
    __tablename__ = 'network_drives'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    drive_type = db.Column(db.String(20), nullable=False)  # 'cifs', 'nfs', 'local'
    server_path = db.Column(db.String(500), nullable=False)  # //server/share or server:/export
    mount_point = db.Column(db.String(500), nullable=False)  # /mnt/drive_name
    username = db.Column(db.String(100), nullable=True)
    password_encrypted = db.Column(LargeBinary, nullable=True)
    mount_options = db.Column(db.String(200), nullable=True)  # Custom mount options
    auto_mount = db.Column(db.Boolean, default=True)  # Mount on system startup
    is_mounted = db.Column(db.Boolean, default=False)  # Current mount status
    last_mount_check = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
