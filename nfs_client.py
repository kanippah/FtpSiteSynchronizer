import os
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

class NFSClient:
    """NFS client for network file system operations"""
    
    def __init__(self, host, export_path, nfs_version='4', mount_options='', auth_method='sys'):
        self.host = host
        self.export_path = export_path
        self.nfs_version = nfs_version
        self.mount_options = mount_options
        self.auth_method = auth_method
        self.mount_point = None
    
    def mount(self):
        """Mount NFS share"""
        try:
            # Create temporary mount point
            self.mount_point = tempfile.mkdtemp(prefix='nfs_mount_')
            
            # Build NFS mount command
            nfs_server = f"{self.host}:{self.export_path}"
            mount_options = self._build_mount_options()
            
            cmd = ['sudo', 'mount', '-t', 'nfs']
            if mount_options:
                cmd.extend(['-o', mount_options])
            cmd.extend([nfs_server, self.mount_point])
            
            # Execute mount command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"NFS mounted successfully at {self.mount_point}")
                return True
            else:
                logger.error(f"NFS mount failed: {result.stderr}")
                self._cleanup_mount_point()
                return False
                
        except Exception as e:
            logger.error(f"NFS mount error: {str(e)}")
            self._cleanup_mount_point()
            return False
    
    def unmount(self):
        """Unmount NFS share"""
        if not self.mount_point or not os.path.exists(self.mount_point):
            return
        
        try:
            # Unmount the NFS share
            cmd = ['sudo', 'umount', self.mount_point]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"NFS unmounted successfully from {self.mount_point}")
            else:
                logger.warning(f"NFS unmount warning: {result.stderr}")
                # Force unmount if normal unmount fails
                force_cmd = ['sudo', 'umount', '-f', self.mount_point]
                subprocess.run(force_cmd, capture_output=True, text=True, timeout=10)
            
        except Exception as e:
            logger.error(f"NFS unmount error: {str(e)}")
        finally:
            self._cleanup_mount_point()
    
    def _cleanup_mount_point(self):
        """Clean up temporary mount point"""
        if self.mount_point and os.path.exists(self.mount_point):
            try:
                os.rmdir(self.mount_point)
                logger.debug(f"Cleaned up mount point: {self.mount_point}")
            except Exception as e:
                logger.warning(f"Failed to cleanup mount point: {str(e)}")
            finally:
                self.mount_point = None
    
    def _build_mount_options(self):
        """Build NFS mount options string"""
        options = []
        
        # Add NFS version
        if self.nfs_version:
            if self.nfs_version in ['3', '4', '4.1', '4.2']:
                options.append(f"vers={self.nfs_version}")
        
        # Add authentication method
        if self.auth_method and self.auth_method != 'sys':
            options.append(f"sec={self.auth_method}")
        
        # Add default options for reliability
        default_options = [
            'rsize=32768',
            'wsize=32768',
            'timeo=14',
            'retrans=2'
        ]
        options.extend(default_options)
        
        # Add custom mount options if provided
        if self.mount_options:
            custom_options = [opt.strip() for opt in self.mount_options.split(',') if opt.strip()]
            options.extend(custom_options)
        
        return ','.join(options)
    
    def list_files(self, remote_path='.'):
        """List files in NFS mount using filesystem operations"""
        try:
            if not self.mount_point:
                return {'success': False, 'error': 'NFS not mounted'}
            
            # Convert remote path to local mount path
            if remote_path.startswith('/'):
                remote_path = remote_path[1:]  # Remove leading slash
            
            full_path = os.path.join(self.mount_point, remote_path) if remote_path != '.' else self.mount_point
            
            if not os.path.exists(full_path):
                return {'success': False, 'error': f'Path does not exist: {remote_path}'}
            
            files = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                stat_info = os.stat(item_path)
                
                files.append({
                    'name': item,
                    'size': stat_info.st_size if os.path.isfile(item_path) else 0,
                    'modify': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    'type': 'file' if os.path.isfile(item_path) else 'dir'
                })
            
            return {'success': True, 'files': files}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_file(self, remote_path, local_path):
        """Download file from NFS mount using filesystem copy"""
        try:
            if not self.mount_point:
                return {'success': False, 'error': 'NFS not mounted'}
            
            # Convert remote path to local mount path
            if remote_path.startswith('/'):
                remote_path = remote_path[1:]
            
            source_path = os.path.join(self.mount_point, remote_path)
            
            if not os.path.exists(source_path):
                return {'success': False, 'error': f'Source file does not exist: {remote_path}'}
            
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, local_path)
            
            # Get file size for reporting
            file_size = os.path.getsize(local_path)
            
            return {
                'success': True,
                'bytes_transferred': file_size
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def upload_file(self, local_path, remote_path):
        """Upload file to NFS mount using filesystem copy"""
        try:
            if not self.mount_point:
                return {'success': False, 'error': 'NFS not mounted'}
            
            if not os.path.exists(local_path):
                return {'success': False, 'error': f'Local file does not exist: {local_path}'}
            
            # Convert remote path to local mount path
            if remote_path.startswith('/'):
                remote_path = remote_path[1:]
            
            dest_path = os.path.join(self.mount_point, remote_path)
            
            # Ensure remote directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Copy file
            shutil.copy2(local_path, dest_path)
            
            # Get file size for reporting
            file_size = os.path.getsize(local_path)
            
            return {
                'success': True,
                'bytes_transferred': file_size
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_connection(self):
        """Test NFS connection by mounting and unmounting"""
        try:
            if self.mount():
                self.unmount()
                return {'success': True}
            else:
                return {'success': False, 'error': 'Failed to mount NFS share'}
        except Exception as e:
            return {'success': False, 'error': str(e)}