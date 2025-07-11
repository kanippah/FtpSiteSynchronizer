"""
Network Drive Manager for Ubuntu 24.04
Handles mounting and unmounting of CIFS/SMB and NFS network drives
"""

import os
import subprocess
import logging
from datetime import datetime
from models import NetworkDrive, db
from crypto_utils import encrypt_password, decrypt_password
from utils import log_system_message

class NetworkDriveManager:
    """Manager for network drive operations on Ubuntu"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def mount_drive(self, drive_id):
        """Mount a network drive by ID"""
        try:
            drive = NetworkDrive.query.get(drive_id)
            if not drive:
                raise Exception(f"Network drive with ID {drive_id} not found")
            
            if self.is_mounted(drive.mount_point):
                log_system_message('info', f"Drive {drive.name} already mounted at {drive.mount_point}")
                drive.is_mounted = True
                drive.last_mount_check = datetime.utcnow()
                db.session.commit()
                return True
            
            # Create mount point if it doesn't exist
            os.makedirs(drive.mount_point, exist_ok=True)
            
            if drive.drive_type == 'cifs':
                return self._mount_cifs(drive)
            elif drive.drive_type == 'nfs':
                return self._mount_nfs(drive)
            else:
                raise Exception(f"Unsupported drive type: {drive.drive_type}")
                
        except Exception as e:
            error_msg = str(e)
            log_system_message('error', f"Failed to mount drive {drive.name}: {error_msg}", 'network_drives')
            self.logger.error(f"Mount error details for drive {drive_id}: {error_msg}")
            return False
    
    def unmount_drive(self, drive_id):
        """Unmount a network drive by ID"""
        try:
            drive = NetworkDrive.query.get(drive_id)
            if not drive:
                raise Exception(f"Network drive with ID {drive_id} not found")
            
            if not self.is_mounted(drive.mount_point):
                log_system_message('info', f"Drive {drive.name} not mounted")
                drive.is_mounted = False
                db.session.commit()
                return True
            
            # Unmount the drive
            result = subprocess.run([
                'sudo', 'umount', drive.mount_point
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                drive.is_mounted = False
                drive.last_mount_check = datetime.utcnow()
                db.session.commit()
                log_system_message('info', f"Successfully unmounted drive {drive.name}")
                return True
            else:
                raise Exception(f"Unmount failed: {result.stderr}")
                
        except Exception as e:
            log_system_message('error', f"Failed to unmount drive {drive.name}: {e}")
            return False
    
    def _mount_cifs(self, drive):
        """Mount a CIFS/SMB drive"""
        creds_file = None
        try:
            log_system_message('info', f"Starting CIFS mount for drive {drive.name} to {drive.mount_point}", 'network_drives')
            
            # Check if mount.cifs is available
            cifs_check = subprocess.run(['which', 'mount.cifs'], capture_output=True, text=True)
            if cifs_check.returncode != 0:
                raise Exception("mount.cifs utility not found. Install cifs-utils package: sudo apt install cifs-utils")
            
            # Prepare credentials
            username = drive.username or 'guest'
            password = ''
            if drive.password_encrypted:
                password = decrypt_password(drive.password_encrypted)
            
            log_system_message('info', f"Using username: {username} for CIFS mount", 'network_drives')
            
            # Create credentials file
            creds_file = f"/tmp/cifs_creds_{drive.id}"
            with open(creds_file, 'w') as f:
                f.write(f"username={username}\n")
                f.write(f"password={password}\n")
            os.chmod(creds_file, 0o600)
            
            # Mount command
            mount_options = drive.mount_options or 'uid=1000,gid=1000,iocharset=utf8,file_mode=0777,dir_mode=0777'
            cmd = [
                'sudo', 'mount', '-t', 'cifs',
                drive.server_path, drive.mount_point,
                '-o', f"credentials={creds_file},{mount_options}"
            ]
            
            log_system_message('info', f"Executing mount command: {' '.join(cmd[:-2])} -o [credentials]", 'network_drives')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up credentials file
            if creds_file and os.path.exists(creds_file):
                os.remove(creds_file)
                creds_file = None
            
            if result.returncode == 0:
                drive.is_mounted = True
                drive.last_mount_check = datetime.utcnow()
                db.session.commit()
                log_system_message('info', f"Successfully mounted CIFS drive {drive.name}", 'network_drives')
                return True
            else:
                error_output = result.stderr.strip() or result.stdout.strip()
                raise Exception(f"CIFS mount failed (exit code {result.returncode}): {error_output}")
                
        except Exception as e:
            # Clean up credentials file if it exists
            if creds_file and os.path.exists(creds_file):
                os.remove(creds_file)
            raise e
    
    def _mount_nfs(self, drive):
        """Mount an NFS drive"""
        try:
            log_system_message('info', f"Starting NFS mount for drive {drive.name} to {drive.mount_point}", 'network_drives')
            
            # Check if NFS utilities are available
            nfs_check = subprocess.run(['which', 'mount.nfs'], capture_output=True, text=True)
            if nfs_check.returncode != 0:
                nfs_check = subprocess.run(['which', 'mount.nfs4'], capture_output=True, text=True)
                if nfs_check.returncode != 0:
                    raise Exception("NFS mount utilities not found. Install nfs-common package: sudo apt install nfs-common")
            
            # Mount command
            mount_options = drive.mount_options or 'defaults'
            cmd = [
                'sudo', 'mount', '-t', 'nfs',
                drive.server_path, drive.mount_point,
                '-o', mount_options
            ]
            
            log_system_message('info', f"Executing NFS mount command: {' '.join(cmd)}", 'network_drives')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                drive.is_mounted = True
                drive.last_mount_check = datetime.utcnow()
                db.session.commit()
                log_system_message('info', f"Successfully mounted NFS drive {drive.name}", 'network_drives')
                return True
            else:
                error_output = result.stderr.strip() or result.stdout.strip()
                raise Exception(f"NFS mount failed (exit code {result.returncode}): {error_output}")
                
        except Exception as e:
            raise e
    
    def is_mounted(self, mount_point):
        """Check if a mount point is currently mounted"""
        try:
            result = subprocess.run(['mountpoint', '-q', mount_point], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_mount_status(self, drive_id):
        """Get detailed mount status for a drive"""
        try:
            drive = NetworkDrive.query.get(drive_id)
            if not drive:
                return {'error': 'Drive not found'}
            
            is_mounted = self.is_mounted(drive.mount_point)
            
            # Update database status
            if drive.is_mounted != is_mounted:
                drive.is_mounted = is_mounted
                drive.last_mount_check = datetime.utcnow()
                db.session.commit()
            
            return {
                'mounted': is_mounted,
                'mount_point': drive.mount_point,
                'server_path': drive.server_path,
                'drive_type': drive.drive_type,
                'last_check': drive.last_mount_check
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def mount_all_auto_drives(self):
        """Mount all drives marked for auto-mounting"""
        auto_drives = NetworkDrive.query.filter_by(auto_mount=True).all()
        results = []
        
        for drive in auto_drives:
            success = self.mount_drive(drive.id)
            results.append({
                'drive_name': drive.name,
                'success': success,
                'mount_point': drive.mount_point
            })
        
        return results
    
    def create_drive(self, name, drive_type, server_path, mount_point, 
                    username=None, password=None, mount_options=None, auto_mount=True):
        """Create a new network drive configuration"""
        try:
            # Encrypt password if provided
            password_encrypted = None
            if password:
                password_encrypted = encrypt_password(password)
            
            drive = NetworkDrive(
                name=name,
                drive_type=drive_type,
                server_path=server_path,
                mount_point=mount_point,
                username=username,
                password_encrypted=password_encrypted,
                mount_options=mount_options,
                auto_mount=auto_mount
            )
            
            db.session.add(drive)
            db.session.commit()
            
            log_system_message('info', f"Created network drive configuration: {name}")
            return drive.id
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to create network drive {name}: {e}")
            raise e
    
    def delete_drive(self, drive_id):
        """Delete a network drive configuration"""
        try:
            drive = NetworkDrive.query.get(drive_id)
            if not drive:
                raise Exception("Drive not found")
            
            # Unmount if currently mounted
            if drive.is_mounted:
                self.unmount_drive(drive_id)
            
            db.session.delete(drive)
            db.session.commit()
            
            log_system_message('info', f"Deleted network drive: {drive.name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            log_system_message('error', f"Failed to delete network drive: {e}")
            return False
    
    def test_connection(self, drive_id):
        """Test connection to a network drive"""
        try:
            drive = NetworkDrive.query.get(drive_id)
            if not drive:
                return {'success': False, 'message': 'Drive not found'}
            
            log_system_message('info', f"Testing connection to drive {drive.name}", 'network_drives')
            
            if drive.drive_type == 'cifs':
                return self._test_cifs_connection(drive)
            elif drive.drive_type == 'nfs':
                return self._test_nfs_connection(drive)
            else:
                return {'success': False, 'message': f'Unsupported drive type: {drive.drive_type}'}
                
        except Exception as e:
            error_msg = str(e)
            log_system_message('error', f"Connection test failed for drive: {error_msg}", 'network_drives')
            return {'success': False, 'message': error_msg}
    
    def _test_cifs_connection(self, drive):
        """Test CIFS connection"""
        try:
            # Check if mount.cifs is available
            cifs_check = subprocess.run(['which', 'mount.cifs'], capture_output=True, text=True)
            if cifs_check.returncode != 0:
                return {'success': False, 'message': 'mount.cifs utility not found. Install with: sudo apt install cifs-utils'}
            
            # Try to list shares or ping the server
            if drive.server_path.startswith('//'):
                server = drive.server_path.split('/')[2]
                # Test server connectivity
                ping_result = subprocess.run(['ping', '-c', '1', '-W', '3', server], capture_output=True, text=True)
                if ping_result.returncode != 0:
                    return {'success': False, 'message': f'Cannot reach server {server}. Check network connectivity.'}
                
                return {'success': True, 'message': f'Server {server} is reachable. Mount configuration appears valid.'}
            else:
                return {'success': False, 'message': 'Invalid CIFS server path. Use format: //server/share'}
                
        except Exception as e:
            return {'success': False, 'message': f'CIFS test failed: {str(e)}'}
    
    def _test_nfs_connection(self, drive):
        """Test NFS connection"""
        try:
            # Check if NFS utilities are available
            nfs_check = subprocess.run(['which', 'showmount'], capture_output=True, text=True)
            if nfs_check.returncode != 0:
                return {'success': False, 'message': 'NFS utilities not found. Install with: sudo apt install nfs-common'}
            
            # Extract server from server_path
            if ':' in drive.server_path:
                server = drive.server_path.split(':')[0]
                export_path = drive.server_path.split(':', 1)[1]
                
                # Test server connectivity
                ping_result = subprocess.run(['ping', '-c', '1', '-W', '3', server], capture_output=True, text=True)
                if ping_result.returncode != 0:
                    return {'success': False, 'message': f'Cannot reach NFS server {server}. Check network connectivity.'}
                
                # Try to list exports
                showmount_result = subprocess.run(['showmount', '-e', server], capture_output=True, text=True)
                if showmount_result.returncode == 0:
                    exports = showmount_result.stdout
                    if export_path in exports:
                        return {'success': True, 'message': f'NFS export {export_path} found on server {server}'}
                    else:
                        return {'success': False, 'message': f'Export {export_path} not found on server {server}. Available exports:\n{exports}'}
                else:
                    return {'success': False, 'message': f'Cannot list exports from {server}: {showmount_result.stderr}'}
            else:
                return {'success': False, 'message': 'Invalid NFS server path. Use format: server:/export/path'}
                
        except Exception as e:
            return {'success': False, 'message': f'NFS test failed: {str(e)}'}
    
    def _original_test_connection(self, drive_id):
        """Original test connection method"""
        try:
            success = self.mount_drive(drive_id)
            if success:
                # Test by creating a test file
                drive = NetworkDrive.query.get(drive_id)
                test_file = os.path.join(drive.mount_point, '.ftpmanager_test')
                
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    return {'success': True, 'message': 'Connection test successful'}
                except Exception as e:
                    return {'success': False, 'message': f'Mount successful but write test failed: {e}'}
            else:
                return {'success': False, 'message': 'Failed to mount drive'}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}