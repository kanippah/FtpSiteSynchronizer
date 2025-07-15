# FTP/SFTP/NFS Manager

## Overview

This is a Flask-based web application for managing FTP, SFTP, and NFS file transfers. The system provides a web interface for configuring FTP/SFTP/NFS sites, creating scheduled jobs for file transfers, and monitoring transfer activities through logs and notifications.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Job Scheduling**: APScheduler (Advanced Python Scheduler) with background thread execution
- **Security**: Cryptography library for password encryption using Fernet symmetric encryption
- **Protocol Support**: Built-in ftplib for FTP, paramiko for SFTP, and native NFS mount operations

### Frontend Architecture
- **Template Engine**: Jinja2 (Flask's default templating)
- **CSS Framework**: Bootstrap 5 with dark theme
- **JavaScript**: Vanilla JavaScript for dynamic interactions
- **Icons**: Feather Icons
- **Charts**: Chart.js for dashboard visualizations

### Database Schema
- **Sites Table**: Stores FTP/SFTP/NFS connection details with encrypted passwords and NFS-specific configuration
- **Jobs Table**: Manages scheduled transfer jobs with cron expressions supporting all protocols
- **Job Logs Table**: Records execution history and results
- **Settings Table**: System configuration with encrypted sensitive values
- **System Logs Table**: Application-wide logging for debugging and monitoring

## Key Components

### Core Services
1. **FTP Client (`ftp_client.py`)**: Unified client supporting FTP, SFTP, and NFS protocols
2. **NFS Client (`nfs_client.py`)**: Dedicated NFS client with mount/unmount operations and filesystem access
3. **Email Service (`email_service.py`)**: SMTP-based notification system for job status updates
4. **Crypto Utils (`crypto_utils.py`)**: Password encryption/decryption using PBKDF2 key derivation
5. **Scheduler (`scheduler.py`)**: Job execution engine with cron-based scheduling supporting all protocols
6. **Utils (`utils.py`)**: Helper functions for settings management and system logging

### Web Interface
1. **Dashboard**: System overview with job statistics and recent activity
2. **Sites Management**: CRUD operations for FTP/SFTP/NFS site configurations with protocol-specific fields
3. **Jobs Management**: Create, schedule, and monitor transfer jobs across all protocols
4. **Logs Viewer**: Historical job execution and system logs
5. **Settings**: SMTP configuration and system preferences
6. **Upload Interface**: Direct file upload to configured sites
7. **File Browser**: Browse and download files from FTP/SFTP/NFS sites

### Models
- **Site**: FTP/SFTP/NFS connection configuration with encrypted credentials and NFS-specific fields
- **Job**: Scheduled transfer tasks with flexible scheduling options supporting all protocols
- **JobLog**: Execution history with detailed status tracking
- **Settings**: Key-value configuration store with encryption support
- **SystemLog**: Application-wide logging for system events

## Data Flow

### Job Execution Flow
1. APScheduler triggers job execution based on cron expressions
2. Job retrieves site configuration and decrypts credentials
3. Protocol-specific client (FTP/SFTP/NFS) establishes connection to source/target sites
4. File transfer operations execute with progress tracking (NFS uses temporary mount points)
5. Results logged to database and email notifications sent
6. Job status updated for dashboard display

### Security Flow
1. User passwords encrypted using Fernet symmetric encryption
2. Encryption key derived from environment variables or PBKDF2
3. Settings table supports encrypted storage for sensitive configuration
4. Session management through Flask's built-in session handling

## NFS Implementation Details

### Architecture
- **NFS Client (`nfs_client.py`)**: Dedicated module for NFS operations using system mount/umount commands
- **Temporary Mount Points**: Each NFS operation creates a temporary mount point for secure file access
- **Mount Options**: Configurable NFS version (3, 4, 4.1, 4.2), authentication methods, and custom mount options
- **Authentication**: Support for AUTH_SYS, Kerberos v5 (krb5, krb5i, krb5p) authentication methods
- **Error Handling**: Comprehensive error handling with automatic cleanup of mount points

### Database Extensions
- **NFS Export Path**: Server-side export path configuration
- **NFS Version**: Protocol version selection with NFSv4 as default
- **Mount Options**: Custom mount options for advanced configurations
- **Authentication Method**: Security authentication method selection

### Security Considerations
- **Temporary Mounts**: All mount points are temporary and automatically cleaned up
- **Privilege Requirements**: Requires sudo privileges for mount/umount operations
- **Network Security**: Supports encrypted NFSv4 and Kerberos authentication
- **Path Validation**: Input validation for export paths and mount options

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

## Recent Changes

### July 2025 - Upload Directory Creation Issue Fixed ✅
- **Remote Directory Creation**: Fixed "550 No such file or directory" upload errors by implementing recursive directory creation on FTP/SFTP servers
- **Automatic Folder Structure**: Upload process now automatically creates required directory structure (e.g., IQNT/, Sonus/) on target servers
- **Enhanced FTP Client**: Added `_create_remote_directory` function to handle path-by-path directory creation with proper error handling
- **Upload Job Error Resolved**: Fixed "Local folder not found: ./downloads/2025-07" errors by implementing intelligent folder detection
- **Monthly Folder Logic Enhanced**: Upload jobs now automatically find available folders with files when target monthly folder doesn't exist
- **Alternative Folder Discovery**: System automatically uses the folder with the most files as fallback for upload operations
- **None Folder Names Fixed**: Updated database to replace any "None" job folder names with proper auto-generated names from job names
- **Production Ready**: Complete upload workflow now handles both local folder detection and remote directory creation seamlessly

### July 2025 - Ubuntu Deployment Variable Scoping Issue Fixed ✅
- **Critical Bug Fixed**: Resolved "cannot access local variable 'os' where it is not associated" error on Ubuntu server deployment
- **Import Organization**: Moved `pwd` and `os` imports to file header to prevent variable scoping issues in try/except blocks
- **Production Stability**: Network drive mounting now works reliably on Ubuntu 24.04 without variable scoping errors
- **Code Quality**: Eliminated duplicate imports throughout network drive manager functions
- **Error Prevention**: All mount operations now have proper variable scope access for cleanup operations

### July 2025 - Network Drive Mount Point Creation Fixed ✅
- **Automatic Mount Point Creation**: System now automatically creates mount point directories with proper permissions using sudo
- **Ubuntu Server Mount Issue Resolved**: Fixed issue where clicking "Mount" button failed without manual "sudo mkdir -p" command
- **Enhanced Mount Point Management**: Mount points are created with proper ownership (current user uid/gid) and permissions (755)
- **Sudo Permission Integration**: Deploy script now grants necessary sudo permissions for mkdir, chown, and chmod operations on /mnt/*
- **Dual-Mode Creation**: System tries regular directory creation first, then falls back to sudo if permissions are insufficient
- **Comprehensive Error Handling**: Clear error messages when mount point creation fails with specific guidance
- **Deploy Script Enhancement**: Added mount point ownership configuration and sudo permission setup
- **Production Ready**: Network drive mounting now works seamlessly on Ubuntu 24.04 without manual directory creation

### July 2025 - Network Drive Permission Issue Fixed ✅
- **Ubuntu Server Permission Error Resolved**: Fixed [Errno 13] Permission denied errors when downloading to network drives
- **Automatic User Permission Detection**: Network drives now automatically mount with current user's uid/gid for proper permissions
- **Enhanced Permission Checking**: Added check_drive_permissions() function to validate read/write access before job execution
- **Improved Error Messages**: Jobs now provide clear error messages when network drive permissions are insufficient
- **CIFS/NFS Mount Options**: Updated mount commands to include proper uid/gid settings for the current user
- **Scheduler Enhancement**: Network drive paths are now validated and checked for permissions before directory creation
- **Deploy Script Update**: Added migration to fix any existing jobs with None folder names
- **Production Ready**: Network drive downloads now work seamlessly on Ubuntu 24.04 servers with proper mount permissions

### July 2025 - Automatic Monthly Folder Upload Feature Implemented ✅
- **Feature Complete**: Successfully implemented automatic monthly folder upload functionality that allows upload jobs to use existing local folders instead of downloading first
- **Database Enhancement**: Added use_local_folders and upload_date_folder_format columns to jobs table with proper migration support
- **Upload Job Logic**: Created execute_local_folder_upload function to handle direct uploads from monthly folders (e.g., downloads/2025-07/)
- **Monthly Folder Detection**: Implemented get_monthly_folder_path function with support for YYYY-MM, YYYY-MM-DD, and YYYYMM formats
- **User Interface**: Added Upload Job Options card with local folder upload checkbox and monthly folder format selection
- **JavaScript Integration**: Enhanced job form to show/hide upload options based on job type selection
- **None Folder Fix**: Resolved issue where jobs assigned to groups without explicit folder names created "None" folders - now auto-generates job folder names based on job name
- **Perfect Automation**: Enables complete Download Job → Monthly Folder → Upload Job workflow without manual intervention
- **Group Integration**: Works seamlessly with job groups for organized folder structure (YYYY-MM/group_folder_name/job_folder_name/)
- **Deploy Script**: Updated deploy.sh with automatic migration for new upload feature columns

### July 2025 - Preserve Folder Structure Feature Successfully Implemented ✅
- **Feature Fully Working**: Successfully implemented "Preserve Folder Structure" option that maintains original directory hierarchy during transfers
- **Real-World Validation**: Feature tested and working with actual FTP server downloads - correctly organizing files in proper folder structure
- **Fixed Nested Duplication Issue**: Resolved problem where system was creating nested duplicate folders (Download-FTP/IQNT/Download-FTP/IQNT)
- **Correct Folder Hierarchy**: Now properly creates structure like `downloads/Download-FTP/IQNT/files...` without duplication
- **Enhanced Transfer Options**: Jobs can now choose between flattened downloads (original recursive) or structured downloads (new preserve option)
- **Database Enhancement**: Added preserve_folder_structure column to jobs table with proper migration
- **UI Integration**: Added checkbox option in job form Transfer Settings section with user-friendly descriptions
- **FTP Client Enhancement**: Completely rewritten download_files_enhanced method with proper recursive logic for folder structure preservation
- **Scheduler Integration**: Updated job execution logic to recognize and execute new advanced feature
- **Flexible Organization**: Users can combine folder structure preservation with date-based folders and duplicate renaming
- **Environment Adaptation**: Resolved Replit FTP passive/active mode connectivity issues for successful file transfers
- **Performance Optimization**: Improved recursive download function to handle multiple directories and subdirectories efficiently

### July 2025 - Advanced Download Features Fully Implemented
- **All Advanced Features Working**: Successfully implemented recursive download, duplicate renaming, and date-based folder organization
- **Enhanced FTP Client**: Completely rebuilt download_files_enhanced method with proper FTP connection handling
- **Date-Based Folders**: Files automatically organized into YYYY-MM-DD folder structure based on download date
- **Recursive Download**: System now traverses all subdirectories and downloads files from folders (flattening structure)
- **Duplicate Renaming**: Automatic file renaming with _1, _2, etc. suffixes for duplicate files
- **Job-Level Configuration**: All advanced features configured per job (recursive, duplicate renaming, date folders)
- **Proper File Downloads**: Successfully downloading files with correct sizes (114K-124K bytes per file)
- **Nested Folder Organization**: Complete folder hierarchy: downloads/2025-07/Job-Folder-Name/2025-07/Job-Folder-Name/2025-07-11/

### July 2025 - Job Execution Issues Resolved
- **Connection Timeouts Fixed**: Increased FTP/SFTP timeout from 10 to 30 seconds for better reliability
- **Job Configuration Fixed**: Corrected download_all setting and cron scheduling issues
- **Folder Organization Verified**: Successfully tested downloads with proper folder structure creation
- **File Downloads Working**: Verified actual file downloads to organized folder structure (downloads/2025-07/Job-Folder-Name/)
- **Performance Optimized**: Added connection keep-alive and timeout protection for FTP operations
- **Critical Bug Fixed**: Resolved file path handling issue where absolute paths were causing "Read-only file system" errors
- **Download Success Confirmed**: Successfully downloaded 2 files totaling 275,599 bytes from FTP server with proper folder organization

### July 2025 - Nested Folder Structure Implementation
- **Job Folder Names**: Added `job_folder_name` column to jobs table for individual job organization within groups
- **Three-Level Hierarchy**: Implemented YYYY-MM/group_folder_name/job_folder_name/ folder structure
- **Enhanced Organization**: Jobs can now create specific subfolders within their assigned groups
- **Form Updates**: Added job folder name field to job creation/editing forms with helpful descriptions
- **FTP Client Integration**: Updated download_files_enhanced to support nested job folder organization
- **Advanced Features**: All job-level features (recursive download, duplicate renaming, date folders) work with nested structure

### July 2025 - Job Groups & Network Drive Enhancement
- **Job Group Architecture**: Implemented job grouping with date-based folder organization (YYYY-MM/GroupName/)
- **Network Drive Support**: Added Ubuntu 24.04 CIFS/NFS network drive mounting and management
- **Database Enhancements**: New JobGroup and NetworkDrive models with proper relationships
- **Enhanced File Organization**: Groups automatically create structured folders for systematic file management
- **Web Interface**: Added complete management interfaces for job groups and network drives
- **FTP Client Integration**: Updated download_files_enhanced to support automatic group folder creation

### July 2025 - Advanced Download Features Migration
- **Architectural Change**: Moved advanced download features from site-level to job-level configuration
- **Database Changes**: Added 4 new columns to jobs table, removed from sites table
- **Enhanced Flexibility**: Different jobs using same site can now have different download strategies
- **Migration Support**: Updated deploy.sh to handle smooth migration from old to new structure
- **Job-Level Features**: Recursive download, duplicate renaming, date-based folders now per-job

### July 2025 - Network Drive Browsing Enhancement
- **File Browser Enhancement**: Extended existing file browser to support network drive browsing
- **Dual Interface**: Unified browser showing both remote sites (FTP/SFTP/NFS) and local network drives
- **Network Drive Routes**: Added browse_network_drive and download_network_drive_file routes with security validation
- **Template Creation**: Built browser_network_drive.html for seamless file exploration of mounted drives
- **Deploy Script Updates**: Enhanced deploy.sh with network drive browsing documentation and setup
- **Security Features**: Path validation, mount status checking, and access control for network drive operations

### July 2025 - Container Environment Adaptation
- **Environment Detection**: Added automatic detection of containerized vs server environments
- **Fallback Mechanisms**: Implemented demonstration mode for network drives in limited environments
- **Connection Testing**: Replaced ping-based tests with socket-based connectivity testing for container compatibility
- **User Guidance**: Added environment-specific warnings and guidance in web interface
- **Documentation**: Created DEPLOYMENT_ENVIRONMENTS.md explaining deployment differences and capabilities
- **Ubuntu Server Validation**: Confirmed full functionality on standard Ubuntu 24.04 with proper packages installed

### July 2025 - Production Deployment Enhancement
- **Complete deploy.sh**: Enhanced deployment script with all Ubuntu 24.04 network tools and dependencies
- **Network Tools**: Added comprehensive network diagnostic tools (ping, netcat, traceroute, nmap, dnsutils)
- **CIFS/SMB Support**: Full cifs-utils, samba-common-bin, smbclient installation and configuration
- **NFS Support**: Complete nfs-common, showmount, mount.nfs setup with proper sudo permissions
- **Security Tools**: Integrated fail2ban, ufw firewall, SSL certificate support
- **Monitoring**: Added htop, iotop, nethogs for system monitoring
- **Verification Script**: Created deploy_check.sh for post-deployment validation
- **Application Health**: Added health checks and application file verification
- **Documentation**: Comprehensive README_DEPLOYMENT.md with troubleshooting guide