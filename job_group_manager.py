"""
Job Group Manager
Handles job grouping functionality with date-based folder organization
"""

import os
import logging
from datetime import datetime
from models import JobGroup, Job, db
from utils import log_system_message, ensure_directory_exists

class JobGroupManager:
    """Manager for job group operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_group(self, name, group_folder_name, description=None, 
                    enable_date_organization=True, date_folder_format='YYYY-MM', 
                    execution_order=0):
        """Create a new job group"""
        try:
            group = JobGroup(
                name=name,
                description=description,
                group_folder_name=group_folder_name,
                enable_date_organization=enable_date_organization,
                date_folder_format=date_folder_format,
                execution_order=execution_order
            )
            
            db.session.add(group)
            db.session.commit()
            
            log_system_message('info', f"Created job group: {name}")
            return group.id
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to create job group {name}: {e}")
            raise e
    
    def update_group(self, group_id, **kwargs):
        """Update a job group"""
        try:
            group = JobGroup.query.get(group_id)
            if not group:
                raise Exception("Job group not found")
            
            for key, value in kwargs.items():
                if hasattr(group, key):
                    setattr(group, key, value)
            
            group.updated_at = datetime.utcnow()
            db.session.commit()
            
            log_system_message('info', f"Updated job group: {group.name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to update job group: {e}")
            return False
    
    def delete_group(self, group_id, unassign_jobs=True):
        """Delete a job group"""
        try:
            group = JobGroup.query.get(group_id)
            if not group:
                raise Exception("Job group not found")
            
            if unassign_jobs:
                # Unassign jobs from this group
                jobs = Job.query.filter_by(job_group_id=group_id).all()
                for job in jobs:
                    job.job_group_id = None
                    
            db.session.delete(group)
            db.session.commit()
            
            log_system_message('info', f"Deleted job group: {group.name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to delete job group: {e}")
            return False
    
    def assign_job_to_group(self, job_id, group_id):
        """Assign a job to a group"""
        try:
            job = Job.query.get(job_id)
            if not job:
                raise Exception("Job not found")
            
            if group_id:
                group = JobGroup.query.get(group_id)
                if not group:
                    raise Exception("Job group not found")
            
            job.job_group_id = group_id
            job.updated_at = datetime.utcnow()
            db.session.commit()
            
            group_name = group.name if group_id else "None"
            log_system_message('info', f"Assigned job {job.name} to group {group_name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to assign job to group: {e}")
            return False
    
    def get_group_jobs(self, group_id, order_by_execution=True):
        """Get all jobs in a group"""
        try:
            query = Job.query.filter_by(job_group_id=group_id)
            
            if order_by_execution:
                # Order by group execution order, then by job name
                group = JobGroup.query.get(group_id)
                if group:
                    query = query.order_by(Job.name)
            
            return query.all()
            
        except Exception as e:
            log_system_message('error', f"Failed to get group jobs: {e}")
            return []
    
    def run_group(self, group_id):
        """Execute all jobs in a group"""
        try:
            group = JobGroup.query.get(group_id)
            if not group:
                raise Exception("Job group not found")
            
            jobs = self.get_group_jobs(group_id)
            if not jobs:
                log_system_message('warning', f"No jobs found in group {group.name}")
                return []
            
            results = []
            for job in jobs:
                try:
                    # Import here to avoid circular imports
                    from scheduler import execute_job
                    
                    log_system_message('info', f"Executing job {job.name} in group {group.name}")
                    result = execute_job(job.id)
                    results.append({
                        'job_id': job.id,
                        'job_name': job.name,
                        'success': result,
                        'timestamp': datetime.utcnow()
                    })
                    
                except Exception as e:
                    log_system_message('error', f"Failed to execute job {job.name}: {e}")
                    results.append({
                        'job_id': job.id,
                        'job_name': job.name,
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.utcnow()
                    })
            
            log_system_message('info', f"Completed group execution for {group.name}")
            return results
            
        except Exception as e:
            log_system_message('error', f"Failed to run group: {e}")
            return []
    
    def get_group_folder_path(self, group_id, base_path, reference_date=None, job_folder_name=None):
        """Get the organized folder path for a group with optional job folder"""
        try:
            group = JobGroup.query.get(group_id)
            if not group:
                return base_path
            
            folder_path = base_path
            
            # Add date organization if enabled
            if group.enable_date_organization:
                if not reference_date:
                    reference_date = datetime.now()
                
                # Format date folder based on group settings
                date_folder = self._format_date_folder(reference_date, group.date_folder_format)
                folder_path = os.path.join(folder_path, date_folder)
            
            # Add group folder only if group_folder_name is provided and not empty
            if group.group_folder_name and group.group_folder_name.strip():
                folder_path = os.path.join(folder_path, group.group_folder_name)
            
            # Add job folder if provided: base_path/YYYY-MM/group_folder_name/job_folder_name
            if job_folder_name:
                folder_path = os.path.join(folder_path, job_folder_name)
            
            return folder_path
            
        except Exception as e:
            log_system_message('error', f"Failed to get group folder path: {e}")
            return base_path
    
    def _format_date_folder(self, date, format_string):
        """Format date according to group settings"""
        format_map = {
            'YYYY-MM': date.strftime('%Y-%m'),
            'YYYY-MM-DD': date.strftime('%Y-%m-%d'),
            'YYYY_MM': date.strftime('%Y_%m'),
            'YYYY': date.strftime('%Y'),
            'MM-YYYY': date.strftime('%m-%Y'),
            'Month_YYYY': date.strftime('%B_%Y'),
            'YYYY-Q': f"{date.year}-Q{((date.month-1)//3)+1}"
        }
        
        return format_map.get(format_string, date.strftime('%Y-%m'))
    
    def ensure_group_folder(self, group_id, base_path, reference_date=None, job_folder_name=None):
        """Ensure group folder structure exists with optional job folder"""
        try:
            group_path = self.get_group_folder_path(group_id, base_path, reference_date, job_folder_name)
            ensure_directory_exists(group_path)
            
            log_system_message('info', f"Ensured group folder exists: {group_path}")
            return group_path
            
        except Exception as e:
            log_system_message('error', f"Failed to ensure group folder: {e}")
            return base_path
    
    def get_group_stats(self, group_id):
        """Get statistics for a job group"""
        try:
            group = JobGroup.query.get(group_id)
            if not group:
                return None
            
            jobs = self.get_group_jobs(group_id)
            
            stats = {
                'group_name': group.name,
                'total_jobs': len(jobs),
                'pending_jobs': len([j for j in jobs if j.status == 'pending']),
                'running_jobs': len([j for j in jobs if j.status == 'running']),
                'completed_jobs': len([j for j in jobs if j.status == 'completed']),
                'failed_jobs': len([j for j in jobs if j.status == 'failed']),
                'last_run': max([j.last_run for j in jobs if j.last_run], default=None),
                'next_run': min([j.next_run for j in jobs if j.next_run], default=None)
            }
            
            return stats
            
        except Exception as e:
            log_system_message('error', f"Failed to get group stats: {e}")
            return None
    
    def get_all_groups(self):
        """Get all job groups"""
        try:
            return JobGroup.query.order_by(JobGroup.execution_order, JobGroup.name).all()
        except Exception as e:
            log_system_message('error', f"Failed to get all groups: {e}")
            return []