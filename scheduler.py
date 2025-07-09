import logging
from datetime import datetime, timedelta
from app import app, db, scheduler
from models import Job, JobLog, Site
from crypto_utils import decrypt_password
from ftp_client import FTPClient
from email_service import send_notification
from utils import log_system_message, calculate_rolling_date_range
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
        
        client = FTPClient(site.protocol, site.host, site.port, site.username, password)
        
        # Create local directory
        local_path = job.local_path or './downloads'
        os.makedirs(local_path, exist_ok=True)
        
        files_processed = 0
        bytes_transferred = 0
        log_messages = []
        
        if job.download_all:
            # Download all files/folders
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
            
            # Download files within date range
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
        
        source_site = job.site
        target_site = Site.query.get(job.target_site_id)
        
        if not target_site:
            return {
                'success': False,
                'error': 'Target site not found'
            }
        
        # Get passwords
        source_password = decrypt_password(source_site.password_encrypted)
        target_password = decrypt_password(target_site.password_encrypted)
        
        # Create clients
        source_client = FTPClient(source_site.protocol, source_site.host, source_site.port, source_site.username, source_password)
        target_client = FTPClient(target_site.protocol, target_site.host, target_site.port, target_site.username, target_password)
        
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
