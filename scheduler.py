import logging
from datetime import datetime, timedelta
from app import app, db, scheduler
from models import Job, JobLog, Site
from crypto_utils import decrypt_password
from ftp_client import FTPClient
from email_service import send_notification
from utils import log_system_message, calculate_rolling_date_range, filter_files_by_filename_date
import os
import glob

logger = logging.getLogger(__name__)

def schedule_job(job):
    """Schedule a job with APScheduler"""
    try:
        job_id = f'job_{job.id}'
        
        # Remove existing job if it exists
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        
        if job.schedule_type == 'one_time':
            # Use naive datetime to avoid timezone issues
            run_date = job.schedule_datetime
            if hasattr(run_date, 'tzinfo') and run_date.tzinfo is not None:
                run_date = run_date.replace(tzinfo=None)
            
            scheduler.add_job(
                func=execute_job,
                args=[job.id],
                trigger='date',
                run_date=run_date,
                id=job_id,
                replace_existing=True
            )
        elif job.schedule_type == 'recurring' and job.cron_expression:
            # Parse cron expression (simplified)
            cron_parts = job.cron_expression.split()
            if len(cron_parts) == 5:
                minute, hour, day, month, day_of_week = cron_parts
                
                scheduler.add_job(
                    func=execute_job,
                    args=[job.id],
                    trigger='cron',
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                    id=job_id,
                    replace_existing=True
                )
        
        logger.info(f"Job {job.name} scheduled successfully")
        
    except Exception as e:
        logger.error(f"Error scheduling job {job.name}: {str(e)}")
        # Don't raise the exception, just log it
        return False
    
    return True

def execute_job(job_id):
    """Execute a job"""
    with app.app_context():
        job_log = None
        try:
            job = Job.query.get(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            logger.info(f"Executing job: {job.name}")
            
            # Update job status
            job.status = 'running'
            job.last_run = datetime.utcnow()
            db.session.commit()
            
            # Create job log
            job_log = JobLog(
                job_id=job.id,
                start_time=datetime.utcnow(),
                status='running'
            )
            db.session.add(job_log)
            db.session.commit()
            
            # Execute based on job type
            if job.job_type == 'download':
                result = execute_download_job(job, job_log)
            elif job.job_type == 'upload':
                result = execute_upload_job(job, job_log)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
            
            # Update job and log status
            if result['success']:
                job.status = 'completed'
                job_log.status = 'completed'
                job_log.files_processed = result.get('files_processed', 0)
                job_log.bytes_transferred = result.get('bytes_transferred', 0)
                
                log_system_message('info', f'Job "{job.name}" completed successfully', 'scheduler')
                
                # Send success notification
                send_notification(
                    subject=f'Job "{job.name}" completed successfully',
                    body=f'Job "{job.name}" has been completed successfully.\n\nFiles processed: {result.get("files_processed", 0)}\nBytes transferred: {result.get("bytes_transferred", 0)}',
                    is_success=True
                )
            else:
                job.status = 'failed'
                job_log.status = 'failed'
                job_log.error_message = result.get('error', 'Unknown error')
                
                log_system_message('error', f'Job "{job.name}" failed: {result.get("error", "Unknown error")}', 'scheduler')
                
                # Send failure notification
                send_notification(
                    subject=f'Job "{job.name}" failed',
                    body=f'Job "{job.name}" has failed.\n\nError: {result.get("error", "Unknown error")}',
                    is_success=False
                )
            
            job_log.end_time = datetime.utcnow()
            job_log.log_content = result.get('log', '')
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error executing job {job_id}: {str(e)}")
            
            # Update job and log status on error
            if job_log:
                job_log.status = 'failed'
                job_log.error_message = str(e)
                job_log.end_time = datetime.utcnow()
            
            if 'job' in locals():
                job.status = 'failed'
                job.error_message = str(e)
            
            db.session.commit()
            
            # Send failure notification
            send_notification(
                subject=f'Job execution failed',
                body=f'Job execution failed with error: {str(e)}',
                is_success=False
            )

def execute_download_job(job, job_log):
    """Execute a download job"""
    try:
        site = job.site
        password = decrypt_password(site.password_encrypted)
        
        # Build client parameters with NFS support
        client_kwargs = {}
        if site.protocol == 'nfs':
            client_kwargs.update({
                'nfs_export_path': site.nfs_export_path or '/',
                'nfs_version': site.nfs_version or '4',
                'nfs_mount_options': site.nfs_mount_options or '',
                'nfs_auth_method': site.nfs_auth_method or 'sys'
            })
        
        client = FTPClient(site.protocol, site.host, site.port, site.username, password, **client_kwargs)
        
        # Create local directory - incorporate job group and folder structure
        from job_group_manager import JobGroupManager
        
        if job.job_group_id:
            # Use group manager to get organized folder path
            group_manager = JobGroupManager()
            base_path = job.local_path or './downloads'
            
            # Use job folder name only if it's explicitly set and not empty
            job_folder_name = job.job_folder_name
            if job_folder_name == 'None' or (job_folder_name and job_folder_name.strip() == ''):
                job_folder_name = None
            
            # Ensure the group folder structure exists first
            group_manager.ensure_group_folder(job.job_group_id, base_path, job_folder_name=job_folder_name)
            
            # Get the final path including job folder
            local_path = group_manager.get_group_folder_path(
                job.job_group_id, 
                base_path, 
                job_folder_name=job_folder_name
            )
        else:
            local_path = job.local_path or './downloads'
        
        # Check if path is on a network drive and handle permissions
        if local_path.startswith('/mnt/') or local_path.startswith('\\\\'):
            # Network drive path - check mount status and permissions
            try:
                from network_drive_manager import NetworkDriveManager
                drive_manager = NetworkDriveManager()
                
                # Find matching network drive
                from models import NetworkDrive
                network_drive = None
                for drive in NetworkDrive.query.all():
                    if local_path.startswith(drive.mount_point):
                        network_drive = drive
                        break
                
                if network_drive:
                    # Ensure drive is mounted
                    if not network_drive.is_mounted:
                        mount_success = drive_manager.mount_drive(network_drive.id)
                        if not mount_success:
                            return {
                                'success': False,
                                'error': f'Failed to mount network drive {network_drive.name}. Check network drive configuration.'
                            }
                    
                    # Check permissions before proceeding
                    permission_check = drive_manager.check_drive_permissions(network_drive.id)
                    if not permission_check['success']:
                        return {
                            'success': False,
                            'error': f'Network drive permission error: {permission_check["error"]}. Try remounting the drive or check mount options.'
                        }
                    
                    # Try to create directory with proper permissions
                    try:
                        os.makedirs(local_path, exist_ok=True)
                    except PermissionError:
                        return {
                            'success': False,
                            'error': f'Permission denied: Cannot create directory {local_path}. Check mount options (uid={os.getuid()}, gid={os.getgid()}) and user permissions.'
                        }
                    except Exception as e:
                        return {
                            'success': False,
                            'error': f'Cannot create directory {local_path}: {str(e)}'
                        }
                else:
                    return {
                        'success': False,
                        'error': f'Network drive not found for path {local_path}. Configure the network drive first.'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Network drive error: {str(e)}'
                }
        else:
            # Local path - standard directory creation
            os.makedirs(local_path, exist_ok=True)
        
        files_processed = 0
        bytes_transferred = 0
        log_messages = []
        log_messages.append(f"Target folder: {local_path}")
        
        if job.download_all:
            # Download all files/folders (with optional filename date filtering)
            if job.use_filename_date_filter and job.filename_date_pattern and site.transfer_type == 'files':
                # Get file list first, apply filename date filtering, then download
                files_list = client.list_files(site.remote_path)
                if not files_list['success']:
                    return files_list
                
                log_messages.append(f"Found {len(files_list['files'])} files before filtering")
                
                # Apply filename date filtering (no date range - just files with valid dates)
                filtered_files = filter_files_by_filename_date(files_list['files'], job.filename_date_pattern, None, None)
                log_messages.append(f"Files after filename date filter: {len(filtered_files)}")
                
                # Download filtered files manually
                files_processed = 0
                bytes_transferred = 0
                
                for file_info in filtered_files:
                    if file_info['type'] == 'file':
                        remote_file_path = os.path.join(site.remote_path, file_info['name']).replace('\\', '/')
                        local_file_path = os.path.join(local_path, file_info['name'])
                        
                        result = client.download_file(remote_file_path, local_file_path)
                        
                        if result['success']:
                            files_processed += 1
                            bytes_transferred += result['bytes_transferred']
                            log_messages.append(f"Downloaded: {file_info['name']}")
                        else:
                            log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
            else:
                # Check if any advanced download features are enabled at job level
                has_advanced_features = (job.enable_recursive_download or 
                                       job.preserve_folder_structure or
                                       job.enable_duplicate_renaming or 
                                       job.use_date_folders)
                
                if has_advanced_features:
                    # Use enhanced download method with job-level configuration
                    result = client.download_files_enhanced(site.remote_path, local_path, job)
                else:
                    # Regular download without advanced features (with timeout protection)
                    if site.transfer_type == 'files':
                        result = client.download_all_files(site.remote_path, local_path)
                    else:
                        result = client.download_folder(site.remote_path, local_path)
                
                if result['success']:
                    files_processed = result.get('files_processed', 0)
                    bytes_transferred = result.get('bytes_transferred', 0)
                    log_messages = result.get('log', [])
                else:
                    return result
        
        elif job.use_date_range or job.use_rolling_date_range:
            # Determine date range
            if job.use_rolling_date_range and job.rolling_pattern:
                # Calculate rolling date range based on current execution time
                date_from, date_to = calculate_rolling_date_range(
                    job.rolling_pattern, 
                    reference_date=None,
                    date_offset_from=job.date_offset_from,
                    date_offset_to=job.date_offset_to
                )
                log_messages.append(f"Using rolling date range: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            else:
                # Use static date range
                date_from, date_to = job.date_from, job.date_to
                log_messages.append(f"Using static date range: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            
            # Download files within date range (with optional filename date filtering)
            if job.use_filename_date_filter and job.filename_date_pattern and site.transfer_type == 'files':
                # Get file list first, apply filename date filtering based on date range, then download
                files_list = client.list_files(site.remote_path)
                if not files_list['success']:
                    return files_list
                
                log_messages.append(f"Found {len(files_list['files'])} files before filtering")
                
                # Apply filename date filtering with date range
                filtered_files = filter_files_by_filename_date(files_list['files'], job.filename_date_pattern, date_from, date_to)
                log_messages.append(f"Files after filename date filter: {len(filtered_files)}")
                
                # Download filtered files manually
                files_processed = 0
                bytes_transferred = 0
                
                for file_info in filtered_files:
                    if file_info['type'] == 'file':
                        remote_file_path = os.path.join(site.remote_path, file_info['name']).replace('\\', '/')
                        local_file_path = os.path.join(local_path, file_info['name'])
                        
                        result = client.download_file(remote_file_path, local_file_path)
                        
                        if result['success']:
                            files_processed += 1
                            bytes_transferred += result['bytes_transferred']
                            log_messages.append(f"Downloaded: {file_info['name']}")
                        else:
                            log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
            else:
                # Regular date range download using file modification times
                result = client.download_files_by_date_range(
                    site.remote_path, 
                    local_path, 
                    date_from, 
                    date_to
                )
                
                if result['success']:
                    files_processed = result.get('files_processed', 0)
                    bytes_transferred = result.get('bytes_transferred', 0)
                    log_messages = result.get('log', [])
                else:
                    return result
        
        else:
            # Download specific files/folders
            # Check if any advanced download features are enabled at job level
            has_advanced_features = (job.enable_recursive_download or 
                                   job.preserve_folder_structure or
                                   job.enable_duplicate_renaming or 
                                   job.use_date_folders)
            
            if has_advanced_features:
                # Use enhanced download method with job-level configuration
                result = client.download_files_enhanced(site.remote_path, local_path, job)
            else:
                # Regular download without advanced features
                if site.transfer_type == 'files':
                    result = client.download_files(site.remote_path, local_path)
                else:
                    result = client.download_folder(site.remote_path, local_path)
            
            if result['success']:
                files_processed = result.get('files_processed', 0)
                bytes_transferred = result.get('bytes_transferred', 0)
                log_messages = result.get('log', [])
            else:
                return result
        
        return {
            'success': True,
            'files_processed': files_processed,
            'bytes_transferred': bytes_transferred,
            'log': '\n'.join(log_messages)
        }
        
    except Exception as e:
        logger.error(f"Error in download job: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def execute_upload_job(job, job_log):
    """Execute an upload job"""
    try:
        if not job.target_site_id:
            return {
                'success': False,
                'error': 'No target site specified for upload job'
            }
        
        target_site = Site.query.get(job.target_site_id)
        
        if not target_site:
            return {
                'success': False,
                'error': 'Target site not found'
            }
        
        # Check if using local folders for upload
        if job.use_local_folders:
            return execute_local_folder_upload(job, job_log, target_site)
        
        # Original upload logic: download from source, then upload to target
        source_site = job.site
        
        # Get passwords
        source_password = decrypt_password(source_site.password_encrypted)
        target_password = decrypt_password(target_site.password_encrypted)
        
        # Build source client parameters with NFS support
        source_kwargs = {}
        if source_site.protocol == 'nfs':
            source_kwargs.update({
                'nfs_export_path': source_site.nfs_export_path or '/',
                'nfs_version': source_site.nfs_version or '4',
                'nfs_mount_options': source_site.nfs_mount_options or '',
                'nfs_auth_method': source_site.nfs_auth_method or 'sys'
            })
        
        # Build target client parameters with NFS support
        target_kwargs = {}
        if target_site.protocol == 'nfs':
            target_kwargs.update({
                'nfs_export_path': target_site.nfs_export_path or '/',
                'nfs_version': target_site.nfs_version or '4',
                'nfs_mount_options': target_site.nfs_mount_options or '',
                'nfs_auth_method': target_site.nfs_auth_method or 'sys'
            })
        
        # Create clients
        source_client = FTPClient(source_site.protocol, source_site.host, source_site.port, source_site.username, source_password, **source_kwargs)
        target_client = FTPClient(target_site.protocol, target_site.host, target_site.port, target_site.username, target_password, **target_kwargs)
        
        # Download from source first
        temp_path = f'./temp_transfer_{job.id}'
        os.makedirs(temp_path, exist_ok=True)
        
        try:
            # Download from source
            if job.download_all:
                download_result = source_client.download_all_files(source_site.remote_path, temp_path)
            elif job.use_date_range:
                download_result = source_client.download_files_by_date_range(
                    source_site.remote_path, 
                    temp_path, 
                    job.date_from, 
                    job.date_to
                )
            else:
                download_result = source_client.download_files(source_site.remote_path, temp_path)
            
            if not download_result['success']:
                return download_result
            
            # Upload to target
            files_processed = 0
            bytes_transferred = 0
            log_messages = []
            
            # Upload all downloaded files
            for root, dirs, files in os.walk(temp_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, temp_path)
                    remote_file_path = os.path.join(target_site.remote_path, relative_path).replace('\\', '/')
                    
                    upload_result = target_client.upload_file(local_file_path, remote_file_path)
                    
                    if upload_result['success']:
                        files_processed += 1
                        bytes_transferred += os.path.getsize(local_file_path)
                        log_messages.append(f"Uploaded: {relative_path}")
                    else:
                        log_messages.append(f"Failed to upload: {relative_path} - {upload_result.get('error', 'Unknown error')}")
            
            return {
                'success': True,
                'files_processed': files_processed,
                'bytes_transferred': bytes_transferred,
                'log': '\n'.join(log_messages)
            }
            
        finally:
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(temp_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"Error in upload job: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def execute_local_folder_upload(job, job_log, target_site):
    """Execute upload from local folders (automatic monthly folders)"""
    try:
        # Get target site password
        target_password = decrypt_password(target_site.password_encrypted)
        
        # Build target client parameters with NFS support
        target_kwargs = {}
        if target_site.protocol == 'nfs':
            target_kwargs.update({
                'nfs_export_path': target_site.nfs_export_path or '/',
                'nfs_version': target_site.nfs_version or '4',
                'nfs_mount_options': target_site.nfs_mount_options or '',
                'nfs_auth_method': target_site.nfs_auth_method or 'sys'
            })
        
        # Create target client
        target_client = FTPClient(target_site.protocol, target_site.host, target_site.port, target_site.username, target_password, **target_kwargs)
        
        # Determine local folder path
        local_folder = get_monthly_folder_path(job)
        
        if not os.path.exists(local_folder):
            # Try to find any available folders with data
            base_path = job.local_path or './downloads'
            available_folders = []
            
            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path):
                        # Check if folder has files
                        file_count = sum(len(files) for _, _, files in os.walk(item_path))
                        if file_count > 0:
                            available_folders.append((item_path, file_count))
                
                if available_folders:
                    # Use the folder with the most files
                    available_folders.sort(key=lambda x: x[1], reverse=True)
                    local_folder = available_folders[0][0]
                    logger.info(f"Using alternative folder: {local_folder} ({available_folders[0][1]} files)")
                else:
                    return {
                        'success': False,
                        'error': f'Local folder not found: {local_folder}. No folders with files available in {base_path}'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Local folder not found: {local_folder}. Error scanning for alternatives: {str(e)}'
                }
        
        # Force refresh of file system cache by re-scanning
        import time
        time.sleep(0.1)  # Small delay to ensure filesystem consistency
        
        # Check if folder has files
        file_count = sum(len(files) for _, _, files in os.walk(local_folder))
        if file_count == 0:
            return {
                'success': False,
                'error': f'No files found in local folder: {local_folder}. Total folders checked: {local_folder}'
            }
        
        # Upload files from local folder
        files_processed = 0
        bytes_transferred = 0
        log_messages = []
        
        log_messages.append(f"Uploading from local folder: {local_folder}")
        
        # Upload all files from local folder (flatten structure - upload only filenames)
        for root, dirs, files in os.walk(local_folder):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_folder)
                
                # Upload files to root directory only - don't recreate nested folder structure
                remote_file_path = os.path.join(target_site.remote_path, file).replace('\\', '/')
                
                upload_result = target_client.upload_file(local_file_path, remote_file_path)
                
                if upload_result['success']:
                    files_processed += 1
                    bytes_transferred += os.path.getsize(local_file_path)
                    log_messages.append(f"Uploaded: {file} (from {relative_path})")
                else:
                    log_messages.append(f"Failed to upload: {file} (from {relative_path}) - {upload_result.get('error', 'Unknown error')}")
        
        return {
            'success': True,
            'files_processed': files_processed,
            'bytes_transferred': bytes_transferred,
            'log': '\n'.join(log_messages)
        }
        
    except Exception as e:
        logger.error(f"Error in local folder upload job: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_monthly_folder_path(job):
    """Get the monthly folder path for upload jobs"""
    from datetime import datetime
    import os
    
    # Get base local path
    base_path = job.local_path or './downloads'
    
    # Get current month in the specified format
    current_date = datetime.now()
    date_format = job.upload_date_folder_format or 'YYYY-MM'
    
    # Convert format to Python datetime format
    if date_format == 'YYYY-MM':
        month_folder = current_date.strftime('%Y-%m')
    elif date_format == 'YYYY-MM-DD':
        month_folder = current_date.strftime('%Y-%m-%d')
    elif date_format == 'YYYYMM':
        month_folder = current_date.strftime('%Y%m')
    else:
        # Default to YYYY-MM
        month_folder = current_date.strftime('%Y-%m')
    
    # Handle job groups and folder organization
    if job.job_group_id:
        from job_group_manager import JobGroupManager
        group_manager = JobGroupManager()
        
        # Use job folder name only if it's explicitly set and not empty
        job_folder_name = job.job_folder_name
        if job_folder_name == 'None' or (job_folder_name and job_folder_name.strip() == ''):
            job_folder_name = None
        
        return group_manager.get_group_folder_path(
            job.job_group_id, 
            base_path, 
            reference_date=current_date,
            job_folder_name=job_folder_name
        )
    else:
        # Direct monthly folder path - if it doesn't exist, look for any existing dated folders
        primary_path = os.path.join(base_path, month_folder)
        
        # If the primary path doesn't exist, try to find any existing month folders
        if not os.path.exists(primary_path):
            # Look for any folders that match the date pattern
            pattern_paths = []
            try:
                if date_format == 'YYYY-MM':
                    # Look for YYYY-MM pattern folders
                    pattern_paths = glob.glob(os.path.join(base_path, '20??-??'))
                elif date_format == 'YYYY-MM-DD':
                    # Look for YYYY-MM-DD pattern folders
                    pattern_paths = glob.glob(os.path.join(base_path, '20??-??-??'))
                elif date_format == 'YYYYMM':
                    # Look for YYYYMM pattern folders
                    pattern_paths = glob.glob(os.path.join(base_path, '20????'))
                
                # If we found matching folders, use the most recent one
                if pattern_paths:
                    pattern_paths.sort(reverse=True)  # Most recent first
                    return pattern_paths[0]
            except Exception:
                pass
        
        return primary_path

def fix_none_folder_issue(job):
    """Fix the 'None' folder issue in job group paths"""
    if job.job_group_id and job.job_folder_name == 'None':
        # Clear the 'None' value - empty folder name means no job folder
        job.job_folder_name = None
        db.session.commit()
        return job.job_folder_name
    return job.job_folder_name

def reschedule_existing_jobs():
    """Reschedule all existing jobs on application start"""
    with app.app_context():
        try:
            active_jobs = Job.query.filter(Job.status.in_(['pending', 'running'])).all()
            
            for job in active_jobs:
                try:
                    # Reset running jobs to pending
                    if job.status == 'running':
                        job.status = 'pending'
                        db.session.commit()
                    
                    # Try to schedule the job
                    success = schedule_job(job)
                    if success:
                        logger.info(f"Rescheduled job: {job.name}")
                    else:
                        logger.warning(f"Failed to reschedule job {job.name}, keeping as pending")
                        job.status = 'pending'
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error rescheduling job {job.name}: {str(e)}")
                    # Set job status to pending if scheduling fails
                    job.status = 'pending'
                    db.session.commit()
                    
        except Exception as e:
            logger.error(f"Error rescheduling jobs: {str(e)}")

# Schedule existing jobs on startup
reschedule_existing_jobs()
