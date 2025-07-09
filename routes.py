from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from app import app, db, scheduler
from models import Site, Job, JobLog, Settings, SystemLog
from crypto_utils import encrypt_password, decrypt_password
from ftp_client import FTPClient
from ftp_browser import FTPBrowser
from email_service import send_notification, send_test_email
from utils import log_system_message, get_setting, set_setting
from datetime import datetime, timedelta
import os
import json
import logging
import sys
import flask

logger = logging.getLogger(__name__)

@app.route('/')
def dashboard():
    """Dashboard showing system overview and recent activity"""
    try:
        # Get recent jobs
        recent_jobs = Job.query.order_by(Job.updated_at.desc()).limit(10).all()
        
        # Get job statistics
        total_jobs = Job.query.count()
        pending_jobs = Job.query.filter_by(status='pending').count()
        running_jobs = Job.query.filter_by(status='running').count()
        completed_jobs = Job.query.filter_by(status='completed').count()
        failed_jobs = Job.query.filter_by(status='failed').count()
        
        # Get recent logs
        recent_logs = JobLog.query.order_by(JobLog.start_time.desc()).limit(5).all()
        
        # Get system stats
        total_sites = Site.query.count()
        
        stats = {
            'total_jobs': total_jobs,
            'pending_jobs': pending_jobs,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'total_sites': total_sites
        }
        
        return render_template('dashboard.html', 
                             recent_jobs=recent_jobs, 
                             stats=stats, 
                             recent_logs=recent_logs)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        stats = {
            'total_jobs': 0,
            'pending_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'total_sites': 0
        }
        return render_template('dashboard.html', recent_jobs=[], stats=stats, recent_logs=[])

@app.route('/sites')
def sites():
    """List all FTP/SFTP sites"""
    try:
        sites = Site.query.order_by(Site.name).all()
        return render_template('sites.html', sites=sites)
    except Exception as e:
        logger.error(f"Error loading sites: {str(e)}")
        flash(f'Error loading sites: {str(e)}', 'error')
        return render_template('sites.html', sites=[])

@app.route('/sites/new', methods=['GET', 'POST'])
def new_site():
    """Create a new FTP/SFTP site"""
    if request.method == 'POST':
        try:
            name = request.form['name']
            protocol = request.form['protocol']
            host = request.form['host']
            port = int(request.form['port'])
            username = request.form['username']
            password = request.form['password']
            remote_path = request.form['remote_path'] or '/'
            transfer_type = request.form['transfer_type']
            
            # Encrypt password
            encrypted_password = encrypt_password(password)
            
            # Create new site
            site = Site(
                name=name,
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password_encrypted=encrypted_password,
                remote_path=remote_path,
                transfer_type=transfer_type
            )
            
            db.session.add(site)
            db.session.commit()
            
            flash(f'Site "{name}" created successfully!', 'success')
            log_system_message('info', f'Site "{name}" created', 'sites')
            
            return redirect(url_for('sites'))
        except Exception as e:
            logger.error(f"Error creating site: {str(e)}")
            flash(f'Error creating site: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('site_form.html')

@app.route('/sites/<int:site_id>/edit', methods=['GET', 'POST'])
def edit_site(site_id):
    """Edit an existing FTP/SFTP site"""
    site = Site.query.get_or_404(site_id)
    
    if request.method == 'POST':
        try:
            site.name = request.form['name']
            site.protocol = request.form['protocol']
            site.host = request.form['host']
            site.port = int(request.form['port'])
            site.username = request.form['username']
            site.remote_path = request.form['remote_path'] or '/'
            site.transfer_type = request.form['transfer_type']
            
            # Update password if provided
            if request.form['password']:
                site.password_encrypted = encrypt_password(request.form['password'])
            
            site.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash(f'Site "{site.name}" updated successfully!', 'success')
            log_system_message('info', f'Site "{site.name}" updated', 'sites')
            
            return redirect(url_for('sites'))
        except Exception as e:
            logger.error(f"Error updating site: {str(e)}")
            flash(f'Error updating site: {str(e)}', 'error')
            db.session.rollback()
    
    # Decrypt password for display (show placeholder)
    site.password_decrypted = ''
    return render_template('site_form.html', site=site)

@app.route('/sites/<int:site_id>/delete', methods=['POST'])
def delete_site(site_id):
    """Delete an FTP/SFTP site"""
    try:
        site = Site.query.get_or_404(site_id)
        name = site.name
        
        db.session.delete(site)
        db.session.commit()
        
        flash(f'Site "{name}" deleted successfully!', 'success')
        log_system_message('info', f'Site "{name}" deleted', 'sites')
        
        return redirect(url_for('sites'))
    except Exception as e:
        logger.error(f"Error deleting site: {str(e)}")
        flash(f'Error deleting site: {str(e)}', 'error')
        db.session.rollback()
        return redirect(url_for('sites'))

@app.route('/sites/<int:site_id>/test')
def test_site(site_id):
    """Test connection to an FTP/SFTP site"""
    try:
        site = Site.query.get_or_404(site_id)
        password = decrypt_password(site.password_encrypted)
        
        client = FTPClient(site.protocol, site.host, site.port, site.username, password)
        result = client.test_connection()
        
        if result['success']:
            log_system_message('info', f'Connection test successful for "{site.name}"', 'sites')
            return jsonify({
                'success': True,
                'message': f'Connection to "{site.name}" successful!'
            })
        else:
            log_system_message('error', f'Connection test failed for "{site.name}": {result["error"]}', 'sites')
            return jsonify({
                'success': False,
                'message': f'Connection to "{site.name}" failed: {result["error"]}'
            })
    except Exception as e:
        logger.error(f"Error testing site connection: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error testing site connection: {str(e)}'
        })

@app.route('/jobs')
def jobs():
    """List all jobs"""
    try:
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        return render_template('jobs.html', jobs=jobs)
    except Exception as e:
        logger.error(f"Error loading jobs: {str(e)}")
        flash(f'Error loading jobs: {str(e)}', 'error')
        return render_template('jobs.html', jobs=[])

@app.route('/jobs/new', methods=['GET', 'POST'])
def new_job():
    """Create a new job"""
    if request.method == 'POST':
        try:
            from scheduler import schedule_job
            
            name = request.form['name']
            site_id = int(request.form['site_id'])
            job_type = request.form['job_type']
            schedule_type = request.form['schedule_type']
            
            # Create job object
            job = Job(
                name=name,
                site_id=site_id,
                job_type=job_type,
                schedule_type=schedule_type
            )
            
            # Handle scheduling
            if schedule_type == 'one_time':
                schedule_datetime = datetime.strptime(request.form['schedule_datetime'], '%Y-%m-%dT%H:%M')
                job.schedule_datetime = schedule_datetime
                job.next_run = schedule_datetime
            else:
                job.cron_expression = request.form['cron_expression']
            
            # Handle date range
            if request.form.get('use_date_range'):
                job.use_date_range = True
                job.date_from = datetime.strptime(request.form['date_from'], '%Y-%m-%d')
                job.date_to = datetime.strptime(request.form['date_to'], '%Y-%m-%d')
            
            job.download_all = bool(request.form.get('download_all'))
            job.local_path = request.form.get('local_path', './downloads')
            
            # For upload jobs
            if job_type == 'upload' and request.form.get('target_site_id'):
                job.target_site_id = int(request.form['target_site_id'])
            
            db.session.add(job)
            db.session.commit()
            
            # Schedule the job
            schedule_job(job)
            
            flash(f'Job "{name}" created successfully!', 'success')
            log_system_message('info', f'Job "{name}" created', 'jobs')
            
            return redirect(url_for('jobs'))
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            flash(f'Error creating job: {str(e)}', 'error')
            db.session.rollback()
    
    sites = Site.query.order_by(Site.name).all()
    return render_template('job_form.html', sites=sites)

@app.route('/jobs/<int:job_id>/run')
def run_job(job_id):
    """Run a job immediately"""
    try:
        from scheduler import execute_job
        
        job = Job.query.get_or_404(job_id)
        
        # Execute job immediately in background thread
        import threading
        
        def run_job_thread():
            try:
                execute_job(job_id)
            except Exception as e:
                logger.error(f"Error in job thread: {str(e)}")
        
        thread = threading.Thread(target=run_job_thread)
        thread.daemon = True
        thread.start()
        
        flash(f'Job "{job.name}" started!', 'success')
        log_system_message('info', f'Job "{job.name}" started manually', 'jobs')
        
        return redirect(url_for('jobs'))
    except Exception as e:
        logger.error(f"Error running job: {str(e)}")
        flash(f'Error running job: {str(e)}', 'error')
        return redirect(url_for('jobs'))

@app.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
def edit_job(job_id):
    """Edit an existing job"""
    try:
        job = Job.query.get_or_404(job_id)
        
        if request.method == 'POST':
            from scheduler import schedule_job
            
            name = request.form['name']
            site_id = int(request.form['site_id'])
            job_type = request.form['job_type']
            schedule_type = request.form['schedule_type']
            
            # Remove old job from scheduler
            try:
                scheduler.remove_job(f'job_{job_id}')
            except:
                pass
            
            # Update job object
            job.name = name
            job.site_id = site_id
            job.job_type = job_type
            job.schedule_type = schedule_type
            
            # Clear previous scheduling info
            job.schedule_datetime = None
            job.cron_expression = None
            job.next_run = None
            
            # Handle scheduling
            if schedule_type == 'one_time':
                schedule_datetime = datetime.strptime(request.form['schedule_datetime'], '%Y-%m-%dT%H:%M')
                job.schedule_datetime = schedule_datetime
                job.next_run = schedule_datetime
            else:
                job.cron_expression = request.form['cron_expression']
            
            # Handle date range
            job.use_date_range = bool(request.form.get('use_date_range'))
            if job.use_date_range:
                job.date_from = datetime.strptime(request.form['date_from'], '%Y-%m-%d')
                job.date_to = datetime.strptime(request.form['date_to'], '%Y-%m-%d')
            else:
                job.date_from = None
                job.date_to = None
            
            job.download_all = bool(request.form.get('download_all'))
            job.local_path = request.form.get('local_path', './downloads')
            
            # For upload jobs
            if job_type == 'upload' and request.form.get('target_site_id'):
                job.target_site_id = int(request.form['target_site_id'])
            else:
                job.target_site_id = None
            
            job.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Reschedule the job
            schedule_job(job)
            
            flash(f'Job "{name}" updated successfully!', 'success')
            log_system_message('info', f'Job "{name}" updated', 'jobs')
            
            return redirect(url_for('jobs'))
        
        # GET request - show edit form
        sites = Site.query.order_by(Site.name).all()
        return render_template('edit_job.html', job=job, sites=sites)
        
    except Exception as e:
        logger.error(f"Error editing job: {str(e)}")
        flash(f'Error editing job: {str(e)}', 'error')
        db.session.rollback()
        return redirect(url_for('jobs'))

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
def delete_job(job_id):
    """Delete a job"""
    try:
        job = Job.query.get_or_404(job_id)
        name = job.name
        
        # Remove from scheduler
        try:
            scheduler.remove_job(f'job_{job_id}')
        except:
            pass
        
        db.session.delete(job)
        db.session.commit()
        
        flash(f'Job "{name}" deleted successfully!', 'success')
        log_system_message('info', f'Job "{name}" deleted', 'jobs')
        
        return redirect(url_for('jobs'))
    except Exception as e:
        logger.error(f"Error deleting job: {str(e)}")
        flash(f'Error deleting job: {str(e)}', 'error')
        db.session.rollback()
        return redirect(url_for('jobs'))

@app.route('/logs')
def logs():
    """View system and job logs"""
    try:
        page = request.args.get('page', 1, type=int)
        log_type = request.args.get('type', 'all')
        per_page = request.args.get('per_page', 25, type=int)
        level_filter = request.args.get('level', 'all')
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        
        # Validate per_page
        if per_page not in [10, 25, 50, 100]:
            per_page = 25
        
        if log_type == 'job':
            query = JobLog.query
            
            # Apply status filter for job logs
            if status_filter != 'all':
                query = query.filter(JobLog.status == status_filter)
            
            # Apply search filter for job logs
            if search_query:
                query = query.join(Job).filter(
                    db.or_(
                        Job.name.ilike(f'%{search_query}%'),
                        JobLog.error_message.ilike(f'%{search_query}%'),
                        JobLog.log_content.ilike(f'%{search_query}%')
                    )
                )
            
            logs = query.order_by(JobLog.start_time.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        elif log_type == 'system':
            query = SystemLog.query
            
            # Apply level filter for system logs
            if level_filter != 'all':
                query = query.filter(SystemLog.level == level_filter)
            
            # Apply search filter for system logs
            if search_query:
                query = query.filter(
                    db.or_(
                        SystemLog.message.ilike(f'%{search_query}%'),
                        SystemLog.component.ilike(f'%{search_query}%')
                    )
                )
            
            logs = query.order_by(SystemLog.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        else:
            # For combined view, create a mixed dataset
            # Get both job logs and system logs, then combine them
            job_logs = []
            system_logs = []
            
            # Get job logs with filters
            job_query = JobLog.query
            if status_filter != 'all':
                job_query = job_query.filter(JobLog.status == status_filter)
            if search_query:
                job_query = job_query.join(Job).filter(
                    db.or_(
                        Job.name.ilike(f'%{search_query}%'),
                        JobLog.error_message.ilike(f'%{search_query}%'),
                        JobLog.log_content.ilike(f'%{search_query}%')
                    )
                )
            job_logs = job_query.all()
            
            # Get system logs with filters  
            system_query = SystemLog.query
            if level_filter != 'all':
                system_query = system_query.filter(SystemLog.level == level_filter)
            if search_query:
                system_query = system_query.filter(
                    db.or_(
                        SystemLog.message.ilike(f'%{search_query}%'),
                        SystemLog.component.ilike(f'%{search_query}%')
                    )
                )
            system_logs = system_query.all()
            
            # Combine and sort by timestamp
            combined_logs = []
            for log in job_logs:
                combined_logs.append({
                    'log': log,
                    'timestamp': log.start_time,
                    'type': 'job'
                })
            for log in system_logs:
                combined_logs.append({
                    'log': log,
                    'timestamp': log.created_at,
                    'type': 'system'
                })
            
            # Sort by timestamp descending
            combined_logs.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Manual pagination
            total = len(combined_logs)
            start = (page - 1) * per_page
            end = start + per_page
            items = combined_logs[start:end]
            
            # Create a mock pagination object
            class MockPagination:
                def __init__(self, items, page, per_page, total):
                    self.items = [item['log'] for item in items]
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page
                    self.has_prev = page > 1
                    self.has_next = page < self.pages
                    self.prev_num = page - 1 if self.has_prev else None
                    self.next_num = page + 1 if self.has_next else None
                    
                def iter_pages(self, left_edge=2, right_edge=2, left_current=2, right_current=3):
                    for num in range(1, self.pages + 1):
                        if num <= left_edge or (self.pages - num) < right_edge or abs(num - self.page) < left_current:
                            yield num
                        elif abs(num - self.page) == left_current:
                            yield None
            
            logs = MockPagination(items, page, per_page, total)
        
        return render_template('logs.html', 
                             logs=logs, 
                             log_type=log_type,
                             per_page=per_page,
                             level_filter=level_filter,
                             status_filter=status_filter,
                             search_query=search_query)
    except Exception as e:
        logger.error(f"Error loading logs: {str(e)}")
        flash(f'Error loading logs: {str(e)}', 'error')
        return render_template('logs.html', logs=None, log_type='all', per_page=25, 
                             level_filter='all', status_filter='all', search_query='')

@app.route('/logs/<int:log_id>/delete', methods=['POST'])
def delete_log(log_id):
    """Delete a log entry"""
    try:
        log_type = request.form.get('log_type', 'job')
        
        if log_type == 'job':
            log = JobLog.query.get_or_404(log_id)
        else:
            log = SystemLog.query.get_or_404(log_id)
        
        db.session.delete(log)
        db.session.commit()
        
        flash('Log entry deleted successfully!', 'success')
        return redirect(url_for('logs', type=log_type))
    except Exception as e:
        logger.error(f"Error deleting log: {str(e)}")
        flash(f'Error deleting log: {str(e)}', 'error')
        return redirect(url_for('logs'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """System settings configuration"""
    if request.method == 'POST':
        try:
            # SMTP settings
            smtp_settings = [
                'smtp_server', 'smtp_port', 'smtp_use_tls', 'smtp_username', 
                'smtp_password', 'smtp_from_email', 'notification_email'
            ]
            
            for setting in smtp_settings:
                value = request.form.get(setting, '')
                encrypted = setting in ['smtp_password']
                set_setting(setting, value, encrypted)
            
            # Database settings
            db_settings = [
                'db_host', 'db_port', 'db_name', 'db_username', 'db_password'
            ]
            
            for setting in db_settings:
                value = request.form.get(setting, '')
                encrypted = setting in ['db_password']
                set_setting(setting, value, encrypted)
            
            flash('Settings updated successfully!', 'success')
            log_system_message('info', 'System settings updated', 'settings')
            
            return redirect(url_for('settings'))
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            flash(f'Error updating settings: {str(e)}', 'error')
    
    # Load current settings
    current_settings = {}
    setting_keys = [
        'smtp_server', 'smtp_port', 'smtp_use_tls', 'smtp_username', 
        'smtp_from_email', 'notification_email',
        'db_host', 'db_port', 'db_name', 'db_username'
    ]
    
    for key in setting_keys:
        current_settings[key] = get_setting(key, '')
    
    # Add system information
    current_settings['python_version'] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    current_settings['flask_version'] = flask.__version__
    
    return render_template('settings.html', settings=current_settings)

@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    """Upload files to FTP/SFTP sites"""
    if request.method == 'POST':
        try:
            site_id = int(request.form['site_id'])
            files = request.files.getlist('files')
            
            if not files:
                flash('No files selected!', 'error')
                return redirect(url_for('upload_files'))
            
            site = Site.query.get_or_404(site_id)
            password = decrypt_password(site.password_encrypted)
            
            client = FTPClient(site.protocol, site.host, site.port, site.username, password)
            
            upload_results = []
            for file in files:
                if file.filename:
                    # Save file temporarily
                    temp_path = os.path.join('./uploads', file.filename)
                    os.makedirs('./uploads', exist_ok=True)
                    file.save(temp_path)
                    
                    # Upload to FTP/SFTP
                    result = client.upload_file(temp_path, site.remote_path + '/' + file.filename)
                    upload_results.append({
                        'filename': file.filename,
                        'success': result['success'],
                        'error': result.get('error', '')
                    })
                    
                    # Clean up temp file
                    try:
                        os.remove(temp_path)
                    except:
                        pass
            
            # Show results
            success_count = sum(1 for r in upload_results if r['success'])
            total_count = len(upload_results)
            
            flash(f'Upload completed: {success_count}/{total_count} files uploaded successfully!', 
                  'success' if success_count == total_count else 'warning')
            
            log_system_message('info', f'Manual upload to "{site.name}": {success_count}/{total_count} files', 'upload')
            
            return redirect(url_for('upload_files'))
        except Exception as e:
            logger.error(f"Error uploading files: {str(e)}")
            flash(f'Error uploading files: {str(e)}', 'error')
    
    sites = Site.query.order_by(Site.name).all()
    return render_template('upload.html', sites=sites)

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    try:
        # Job status distribution
        job_stats = {
            'pending': Job.query.filter_by(status='pending').count(),
            'running': Job.query.filter_by(status='running').count(),
            'completed': Job.query.filter_by(status='completed').count(),
            'failed': Job.query.filter_by(status='failed').count()
        }
        
        # Recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = JobLog.query.filter(JobLog.start_time >= seven_days_ago).all()
        
        daily_stats = {}
        for log in recent_logs:
            day = log.start_time.strftime('%Y-%m-%d')
            if day not in daily_stats:
                daily_stats[day] = {'completed': 0, 'failed': 0}
            
            if log.status == 'completed':
                daily_stats[day]['completed'] += 1
            elif log.status == 'failed':
                daily_stats[day]['failed'] += 1
        
        return jsonify({
            'job_stats': job_stats,
            'daily_stats': daily_stats
        })
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-email', methods=['POST'])
def api_test_email():
    """API endpoint to test email configuration"""
    try:
        result = send_test_email()
        
        if result['success']:
            log_system_message('info', 'Test email sent successfully', 'settings')
            return jsonify({'success': True, 'message': 'Test email sent successfully'})
        else:
            log_system_message('error', f'Test email failed: {result.get("error", "Unknown error")}', 'settings')
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')})
            
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        log_system_message('error', f'Test email error: {str(e)}', 'settings')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/browser')
def file_browser():
    """File browser listing all sites"""
    try:
        sites = Site.query.order_by(Site.name).all()
        return render_template('browser.html', sites=sites)
    except Exception as e:
        logger.error(f"Error loading file browser: {str(e)}")
        flash(f'Error loading file browser: {str(e)}', 'error')
        return render_template('browser.html', sites=[])

@app.route('/browser/<int:site_id>')
@app.route('/browser/<int:site_id>/<path:remote_path>')
def browse_site(site_id, remote_path='.'):
    """Browse files and folders on a specific site"""
    try:
        site = Site.query.get_or_404(site_id)
        password = decrypt_password(site.password_encrypted)
        
        browser = FTPBrowser(site.protocol, site.host, site.port, site.username, password)
        result = browser.browse_directory(remote_path)
        
        if not result['success']:
            flash(f'Error browsing directory: {result["error"]}', 'error')
            return redirect(url_for('file_browser'))
        
        # Add breadcrumb navigation
        path_parts = []
        if result['current_path'] and result['current_path'] != '/':
            parts = result['current_path'].strip('/').split('/')
            current = ''
            for part in parts:
                current += '/' + part
                path_parts.append({
                    'name': part,
                    'path': current.lstrip('/')
                })
        
        return render_template('browser_site.html', 
                             site=site,
                             current_path=result['current_path'],
                             parent_path=result['parent_path'],
                             items=result['items'],
                             path_parts=path_parts)
                             
    except Exception as e:
        logger.error(f"Error browsing site {site_id}: {str(e)}")
        flash(f'Error browsing site: {str(e)}', 'error')
        return redirect(url_for('file_browser'))

@app.route('/browser/<int:site_id>/download/<path:remote_path>')
def download_file(site_id, remote_path):
    """Download a single file from FTP/SFTP site"""
    try:
        site = Site.query.get_or_404(site_id)
        password = decrypt_password(site.password_encrypted)
        
        # Ensure remote_path starts with / for absolute path
        if not remote_path.startswith('/'):
            remote_path = '/' + remote_path
        
        client = FTPClient(site.protocol, site.host, site.port, site.username, password)
        
        # Create a temporary local file
        import tempfile
        filename = os.path.basename(remote_path)
        temp_dir = tempfile.mkdtemp()
        local_path = os.path.join(temp_dir, filename)
        
        # Ensure directory exists
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Downloading file: {remote_path} to {local_path}")
        result = client.download_file(remote_path, local_path)
        
        if result['success']:
            log_system_message('info', f'File downloaded from "{site.name}": {filename}', 'browser')
            
            def remove_file(response):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except:
                    pass
                return response
            
            response = send_file(local_path, as_attachment=True, download_name=filename)
            # Schedule cleanup after response is sent
            return response
        else:
            flash(f'Error downloading file: {result["error"]}', 'error')
            # Go back to parent directory
            parent_dir = os.path.dirname(remote_path.lstrip('/'))
            if parent_dir:
                return redirect(url_for('browse_site', site_id=site_id, remote_path=parent_dir))
            else:
                return redirect(url_for('browse_site', site_id=site_id))
            
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('file_browser'))

@app.route('/api/browser/<int:site_id>/preview/<path:remote_path>')
def preview_file(site_id, remote_path):
    """Get a preview of file content"""
    try:
        site = Site.query.get_or_404(site_id)
        password = decrypt_password(site.password_encrypted)
        
        # Ensure remote_path starts with / for absolute path
        if not remote_path.startswith('/'):
            remote_path = '/' + remote_path
        
        logger.info(f"Previewing file: {remote_path} on site {site.name}")
        
        browser = FTPBrowser(site.protocol, site.host, site.port, site.username, password)
        result = browser.get_file_content_preview(remote_path)
        
        logger.info(f"Preview result: {result.get('success', False)}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error previewing file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('base.html'), 500
