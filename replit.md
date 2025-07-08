# FTP/SFTP Manager

## Overview

This is a Flask-based web application for managing FTP and SFTP file transfers. The system provides a web interface for configuring FTP/SFTP sites, creating scheduled jobs for file transfers, and monitoring transfer activities through logs and notifications.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Job Scheduling**: APScheduler (Advanced Python Scheduler) with background thread execution
- **Security**: Cryptography library for password encryption using Fernet symmetric encryption
- **FTP/SFTP Support**: Built-in ftplib for FTP and paramiko for SFTP connections

### Frontend Architecture
- **Template Engine**: Jinja2 (Flask's default templating)
- **CSS Framework**: Bootstrap 5 with dark theme
- **JavaScript**: Vanilla JavaScript for dynamic interactions
- **Icons**: Feather Icons
- **Charts**: Chart.js for dashboard visualizations

### Database Schema
- **Sites Table**: Stores FTP/SFTP connection details with encrypted passwords
- **Jobs Table**: Manages scheduled transfer jobs with cron expressions
- **Job Logs Table**: Records execution history and results
- **Settings Table**: System configuration with encrypted sensitive values
- **System Logs Table**: Application-wide logging for debugging and monitoring

## Key Components

### Core Services
1. **FTP Client (`ftp_client.py`)**: Unified client supporting both FTP and SFTP protocols
2. **Email Service (`email_service.py`)**: SMTP-based notification system for job status updates
3. **Crypto Utils (`crypto_utils.py`)**: Password encryption/decryption using PBKDF2 key derivation
4. **Scheduler (`scheduler.py`)**: Job execution engine with cron-based scheduling
5. **Utils (`utils.py`)**: Helper functions for settings management and system logging

### Web Interface
1. **Dashboard**: System overview with job statistics and recent activity
2. **Sites Management**: CRUD operations for FTP/SFTP site configurations
3. **Jobs Management**: Create, schedule, and monitor transfer jobs
4. **Logs Viewer**: Historical job execution and system logs
5. **Settings**: SMTP configuration and system preferences
6. **Upload Interface**: Direct file upload to configured sites

### Models
- **Site**: FTP/SFTP connection configuration with encrypted credentials
- **Job**: Scheduled transfer tasks with flexible scheduling options
- **JobLog**: Execution history with detailed status tracking
- **Settings**: Key-value configuration store with encryption support
- **SystemLog**: Application-wide logging for system events

## Data Flow

### Job Execution Flow
1. APScheduler triggers job execution based on cron expressions
2. Job retrieves site configuration and decrypts credentials
3. FTP/SFTP client establishes connection to source/target sites
4. File transfer operations execute with progress tracking
5. Results logged to database and email notifications sent
6. Job status updated for dashboard display

### Security Flow
1. User passwords encrypted using Fernet symmetric encryption
2. Encryption key derived from environment variables or PBKDF2
3. Settings table supports encrypted storage for sensitive configuration
4. Session management through Flask's built-in session handling

## External Dependencies

### Python Packages
- **flask**: Web framework
- **flask-sqlalchemy**: Database ORM
- **apscheduler**: Background job scheduling
- **cryptography**: Encryption/decryption operations
- **paramiko**: SFTP client implementation
- **werkzeug**: WSGI utilities and security

### Frontend Dependencies (CDN)
- **Bootstrap 5**: UI framework with dark theme
- **Feather Icons**: Icon library
- **Chart.js**: Dashboard charts and visualizations

### Database
- **PostgreSQL**: Primary database with connection pooling
- **SQLAlchemy**: ORM with automatic table creation
- **APScheduler SQLAlchemy JobStore**: Persistent job storage

## Deployment Strategy

### Environment Configuration
- Database connection via `DATABASE_URL` environment variable
- Session security via `SESSION_SECRET` environment variable
- Encryption keys via `ENCRYPTION_KEY` and `ENCRYPTION_PASSWORD`
- SMTP configuration stored in database settings table

### Production Considerations
- ProxyFix middleware for reverse proxy deployment
- Connection pooling with automatic reconnection
- Background scheduler with thread pool execution
- Graceful shutdown handling with atexit registration

### Security Measures
- All passwords encrypted at rest using Fernet
- Environment-based configuration for sensitive values
- Session-based authentication with configurable secrets
- Input validation and SQL injection prevention through ORM

### Scalability
- Background job execution with configurable thread pools
- Database connection pooling for concurrent requests
- Stateless job execution suitable for horizontal scaling
- Persistent job storage in database for reliability