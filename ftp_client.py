import ftplib
import paramiko
import os
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import stat
from nfs_client import NFSClient

logger = logging.getLogger(__name__)

class FTPClient:
    """Unified FTP/SFTP/NFS client"""
    
    def __init__(self, protocol, host, port, username, password, **kwargs):
        self.protocol = protocol.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
        self.transport = None
        
        # NFS-specific attributes
        self.nfs_export_path = kwargs.get('nfs_export_path', '/')
        self.nfs_version = kwargs.get('nfs_version', '4')
        self.nfs_mount_options = kwargs.get('nfs_mount_options', '')
        self.nfs_auth_method = kwargs.get('nfs_auth_method', 'sys')
        self.nfs_client = None
        
    def connect(self):
        """Establish connection"""
        try:
            if self.protocol == 'ftp':
                self.connection = ftplib.FTP()
                # Set timeout for FTP connections (increased for better reliability)
                self.connection.connect(self.host, self.port, timeout=30)
                self.connection.login(self.username, self.password)
                # Set passive mode for better firewall compatibility
                self.connection.set_pasv(True)
            elif self.protocol == 'sftp':
                transport = paramiko.Transport((self.host, self.port))
                # Set timeout for SFTP connections (increased for better reliability)
                transport.set_keepalive(30)
                transport.connect(username=self.username, password=self.password, timeout=30)
                self.connection = paramiko.SFTPClient.from_transport(transport)
                self.transport = transport  # Keep reference for cleanup
            elif self.protocol == 'nfs':
                self.nfs_client = NFSClient(
                    host=self.host,
                    export_path=self.nfs_export_path,
                    nfs_version=self.nfs_version,
                    mount_options=self.nfs_mount_options,
                    auth_method=self.nfs_auth_method
                )
                return self.nfs_client.mount()
            else:
                raise ValueError(f"Unsupported protocol: {self.protocol}")
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connection"""
        try:
            if self.connection:
                if self.protocol == 'ftp':
                    self.connection.quit()
                elif self.protocol == 'sftp':
                    self.connection.close()
                    if hasattr(self, 'transport') and self.transport:
                        self.transport.close()
            elif self.protocol == 'nfs' and self.nfs_client:
                self.nfs_client.unmount()
                self.nfs_client = None
            self.connection = None
        except Exception as e:
            logger.error(f"Error disconnecting: {str(e)}")
    
    def test_connection(self):
        """Test connection to server"""
        try:
            if self.connect():
                self.disconnect()
                return {'success': True}
            else:
                return {'success': False, 'error': 'Connection failed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_files(self, remote_path='.'):
        """List files in remote directory"""
        try:
            if self.protocol == 'nfs':
                if not self.nfs_client:
                    return {'success': False, 'error': 'NFS client not initialized'}
                return self.nfs_client.list_files(remote_path)
            
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            files = []
            
            if self.protocol == 'ftp':
                try:
                    self.connection.cwd(remote_path)
                    file_list = self.connection.nlst()
                    
                    for filename in file_list:
                        try:
                            # Get file details with timeout protection
                            self.connection.voidcmd('NOOP')  # Keep connection alive
                            file_info = list(self.connection.mlsd(filename))
                            for name, facts in file_info:
                                if name == filename:
                                    files.append({
                                        'name': name,
                                        'size': int(facts.get('size', 0)),
                                        'modify': facts.get('modify', ''),
                                        'type': 'directory' if facts.get('type') == 'dir' else 'file'
                                    })
                                    break
                        except:
                            # Fallback for servers that don't support MLSD
                            files.append({
                                'name': filename,
                                'size': 0,
                                'modify': '',
                                'type': 'file'
                            })
                            
                except Exception as e:
                    return {'success': False, 'error': str(e)}
                    
            elif self.protocol == 'sftp':
                try:
                    file_list = self.connection.listdir_attr(remote_path)
                    
                    for file_attr in file_list:
                        files.append({
                            'name': file_attr.filename,
                            'size': file_attr.st_size or 0,
                            'modify': datetime.fromtimestamp(file_attr.st_mtime).isoformat() if file_attr.st_mtime else '',
                            'type': 'directory' if stat.S_ISDIR(file_attr.st_mode) else 'file'
                        })
                        
                except Exception as e:
                    return {'success': False, 'error': str(e)}
            
            self.disconnect()
            return {'success': True, 'files': files}
            
        except Exception as e:
            self.disconnect()
            return {'success': False, 'error': str(e)}
    
    def download_file(self, remote_path, local_path):
        """Download a single file"""
        try:
            if self.protocol == 'nfs':
                if not self.nfs_client:
                    return {'success': False, 'error': 'NFS client not initialized'}
                return self.nfs_client.download_file(remote_path, local_path)
            
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            # Create local directory if it doesn't exist
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
            
            if self.protocol == 'ftp':
                try:
                    with open(local_path, 'wb') as local_file:
                        self.connection.retrbinary(f'RETR {remote_path}', local_file.write)
                except Exception as e:
                    self.disconnect()
                    # Try to provide more specific error information
                    if "550" in str(e):
                        return {'success': False, 'error': f'File not found or access denied: {remote_path}'}
                    elif "426" in str(e):
                        return {'success': False, 'error': f'Connection closed during transfer: {remote_path}'}
                    else:
                        return {'success': False, 'error': f'Failed to download {remote_path}: {str(e)}'}
                        
            elif self.protocol == 'sftp':
                try:
                    self.connection.get(remote_path, local_path)
                except Exception as e:
                    self.disconnect()
                    return {'success': False, 'error': f'Failed to download {remote_path}: {str(e)}'}
            
            self.disconnect()
            
            # Check if file was actually downloaded
            if not os.path.exists(local_path):
                return {'success': False, 'error': f'Download failed - file not created locally'}
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            return {
                'success': True,
                'bytes_transferred': file_size
            }
            
        except Exception as e:
            self.disconnect()
            return {'success': False, 'error': str(e)}
    
    def upload_file(self, local_path, remote_path):
        """Upload a single file"""
        try:
            if self.protocol == 'nfs':
                if not self.nfs_client:
                    return {'success': False, 'error': 'NFS client not initialized'}
                return self.nfs_client.upload_file(local_path, remote_path)
            
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            # Create remote directory recursively if needed
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and remote_dir != '.':
                self._create_remote_directory(remote_dir)
            
            if self.protocol == 'ftp':
                with open(local_path, 'rb') as local_file:
                    self.connection.storbinary(f'STOR {remote_path}', local_file)
            elif self.protocol == 'sftp':
                self.connection.put(local_path, remote_path)
            
            self.disconnect()
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            return {
                'success': True,
                'bytes_transferred': file_size
            }
            
        except Exception as e:
            self.disconnect()
            return {'success': False, 'error': str(e)}
    
    def _create_remote_directory(self, remote_path):
        """Create remote directory recursively"""
        try:
            if self.protocol == 'ftp':
                # Split path and create directories one by one
                path_parts = remote_path.strip('/').split('/')
                current_path = ''
                
                for part in path_parts:
                    if not part:
                        continue
                    current_path = f"{current_path}/{part}" if current_path else part
                    
                    try:
                        self.connection.mkd(current_path)
                    except Exception:
                        # Directory might already exist, check if we can change to it
                        try:
                            self.connection.cwd(current_path)
                            self.connection.cwd('/')  # Go back to root
                        except:
                            # If we can't change to it, it probably doesn't exist and creation failed
                            pass
                            
            elif self.protocol == 'sftp':
                # SFTP doesn't have recursive mkdir, so we need to do it manually
                path_parts = remote_path.strip('/').split('/')
                current_path = ''
                
                for part in path_parts:
                    if not part:
                        continue
                    current_path = f"{current_path}/{part}" if current_path else part
                    
                    try:
                        self.connection.mkdir(current_path)
                    except Exception:
                        # Directory might already exist
                        pass
                        
        except Exception:
            # Ignore directory creation errors - upload might still work
            pass
    
    def download_files(self, remote_path, local_path):
        """Download all files from remote directory"""
        try:
            files_list = self.list_files(remote_path)
            if not files_list['success']:
                return files_list
            
            files_processed = 0
            bytes_transferred = 0
            log_messages = []
            
            for file_info in files_list['files']:
                if file_info['type'] == 'file':
                    remote_file_path = os.path.join(remote_path, file_info['name']).replace('\\', '/')
                    local_file_path = os.path.join(local_path, file_info['name'])
                    
                    result = self.download_file(remote_file_path, local_file_path)
                    
                    if result['success']:
                        files_processed += 1
                        bytes_transferred += result['bytes_transferred']
                        log_messages.append(f"Downloaded: {file_info['name']}")
                    else:
                        log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
            
            return {
                'success': True,
                'files_processed': files_processed,
                'bytes_transferred': bytes_transferred,
                'log': log_messages
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_folder(self, remote_path, local_path):
        """Download entire folder structure recursively"""
        try:
            files_processed = 0
            bytes_transferred = 0
            log_messages = []
            
            def download_recursive(remote_dir, local_dir):
                """Recursively download all files and folders"""
                nonlocal files_processed, bytes_transferred
                
                files_list = self.list_files(remote_dir)
                if not files_list['success']:
                    return files_list
                
                # Create local directory
                os.makedirs(local_dir, exist_ok=True)
                
                for file_info in files_list['files']:
                    if file_info['type'] == 'file':
                        # Download file
                        remote_file_path = os.path.join(remote_dir, file_info['name']).replace('\\', '/')
                        local_file_path = os.path.join(local_dir, file_info['name'])
                        
                        result = self.download_file(remote_file_path, local_file_path)
                        
                        if result['success']:
                            files_processed += 1
                            bytes_transferred += result['bytes_transferred']
                            log_messages.append(f"Downloaded: {os.path.relpath(local_file_path, local_path)}")
                        else:
                            log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
                    
                    elif file_info['type'] == 'directory':
                        # Recursively download subdirectory
                        subdir_remote = os.path.join(remote_dir, file_info['name']).replace('\\', '/')
                        subdir_local = os.path.join(local_dir, file_info['name'])
                        
                        log_messages.append(f"Entering directory: {os.path.relpath(subdir_local, local_path)}")
                        download_recursive(subdir_remote, subdir_local)
                
                return {'success': True}
            
            # Start recursive download
            result = download_recursive(remote_path, local_path)
            
            if result['success']:
                return {
                    'success': True,
                    'files_processed': files_processed,
                    'bytes_transferred': bytes_transferred,
                    'log': log_messages
                }
            else:
                return result
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_all_files(self, remote_path, local_path):
        """Download all files and folders with retry logic"""
        try:
            import ftplib
            import time
            
            files_processed = 0
            bytes_transferred = 0
            log_messages = []
            
            # Create local directory
            os.makedirs(local_path, exist_ok=True)
            
            # Multiple attempts with fresh connections
            for attempt in range(3):
                try:
                    log_messages.append(f"Connection attempt {attempt + 1}")
                    
                    ftp = ftplib.FTP()
                    ftp.connect(self.host, self.port, timeout=60)
                    ftp.login(self.username, self.password)
                    ftp.set_pasv(True)
                    
                    # Get directory listing
                    ftp.cwd(remote_path)
                    lines = []
                    ftp.retrlines('LIST', lines.append)
                    
                    files_to_download = []
                    folders_to_process = []
                    
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            filename = ' '.join(parts[8:])
                            
                            if filename not in ['.', '..']:
                                if permissions.startswith('d'):
                                    folders_to_process.append(filename)
                                else:
                                    files_to_download.append(filename)
                    
                    log_messages.append(f"Found {len(files_to_download)} files, {len(folders_to_process)} folders")
                    
                    # Download files in batches of 10
                    batch_size = 10
                    for i in range(0, len(files_to_download), batch_size):
                        batch = files_to_download[i:i+batch_size]
                        
                        for filename in batch:
                            local_file_path = os.path.join(local_path, filename)
                            
                            # Skip if already downloaded
                            if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
                                continue
                            
                            try:
                                with open(local_file_path, 'wb') as local_file:
                                    ftp.retrbinary(f'RETR {filename}', local_file.write)
                                
                                file_size = os.path.getsize(local_file_path)
                                if file_size > 0:
                                    files_processed += 1
                                    bytes_transferred += file_size
                                    log_messages.append(f"Downloaded: {filename} ({file_size} bytes)")
                                else:
                                    if os.path.exists(local_file_path):
                                        os.remove(local_file_path)
                                    log_messages.append(f"Failed: {filename} (0 bytes)")
                                
                            except Exception as e:
                                log_messages.append(f"Error downloading {filename}: {str(e)}")
                                if os.path.exists(local_file_path):
                                    os.remove(local_file_path)
                                continue
                            
                            # Small delay between files
                            time.sleep(0.1)
                        
                        # Re-establish connection every batch to prevent timeouts
                        if i + batch_size < len(files_to_download):
                            try:
                                ftp.quit()
                                ftp = ftplib.FTP()
                                ftp.connect(self.host, self.port, timeout=60)
                                ftp.login(self.username, self.password)
                                ftp.set_pasv(True)
                                ftp.cwd(remote_path)
                            except:
                                log_messages.append(f"Connection refresh failed at batch {i//batch_size + 1}")
                                break
                    
                    # Download from subdirectories
                    for folder_name in folders_to_process:
                        try:
                            ftp.cwd(f"{remote_path}/{folder_name}")
                            folder_lines = []
                            ftp.retrlines('LIST', folder_lines.append)
                            
                            for line in folder_lines:
                                parts = line.split()
                                if len(parts) >= 9:
                                    permissions = parts[0]
                                    filename = ' '.join(parts[8:])
                                    
                                    if filename not in ['.', '..'] and not permissions.startswith('d'):
                                        local_file_path = os.path.join(local_path, filename)
                                        
                                        # Skip if already downloaded
                                        if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
                                            continue
                                        
                                        try:
                                            with open(local_file_path, 'wb') as local_file:
                                                ftp.retrbinary(f'RETR {filename}', local_file.write)
                                            
                                            file_size = os.path.getsize(local_file_path)
                                            if file_size > 0:
                                                files_processed += 1
                                                bytes_transferred += file_size
                                                log_messages.append(f"Downloaded from {folder_name}: {filename} ({file_size} bytes)")
                                            else:
                                                if os.path.exists(local_file_path):
                                                    os.remove(local_file_path)
                                        
                                        except Exception as e:
                                            log_messages.append(f"Error downloading {folder_name}/{filename}: {str(e)}")
                                            if os.path.exists(local_file_path):
                                                os.remove(local_file_path)
                            
                            ftp.cwd(remote_path)
                            
                        except Exception as e:
                            log_messages.append(f"Error processing folder {folder_name}: {str(e)}")
                    
                    ftp.quit()
                    break  # Success - exit retry loop
                    
                except Exception as e:
                    log_messages.append(f"Attempt {attempt + 1} failed: {str(e)}")
                    try:
                        ftp.quit()
                    except:
                        pass
                    
                    if attempt < 2:
                        time.sleep(2)  # Wait before retry
                    continue
            
            return {
                'success': True,
                'files_processed': files_processed,
                'bytes_transferred': bytes_transferred,
                'log': log_messages
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_files_by_date_range(self, remote_path, local_path, date_from, date_to):
        """Download files within date range"""
        try:
            files_list = self.list_files(remote_path)
            if not files_list['success']:
                return files_list
            
            files_processed = 0
            bytes_transferred = 0
            log_messages = []
            
            for file_info in files_list['files']:
                if file_info['type'] == 'file' and file_info['modify']:
                    try:
                        # Parse file modification time
                        if self.protocol == 'ftp':
                            # FTP MLSD format: YYYYMMDDHHMMSS
                            if len(file_info['modify']) >= 14:
                                file_date = datetime.strptime(file_info['modify'][:14], '%Y%m%d%H%M%S')
                            else:
                                continue
                        else:
                            # SFTP format: ISO format
                            file_date = datetime.fromisoformat(file_info['modify'].replace('Z', '+00:00'))
                        
                        # Check if file is within date range
                        if date_from <= file_date <= date_to:
                            remote_file_path = os.path.join(remote_path, file_info['name']).replace('\\', '/')
                            local_file_path = os.path.join(local_path, file_info['name'])
                            
                            result = self.download_file(remote_file_path, local_file_path)
                            
                            if result['success']:
                                files_processed += 1
                                bytes_transferred += result['bytes_transferred']
                                log_messages.append(f"Downloaded: {file_info['name']} (modified: {file_date})")
                            else:
                                log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
                        
                    except Exception as e:
                        log_messages.append(f"Error processing file {file_info['name']}: {str(e)}")
                        continue
            
            return {
                'success': True,
                'files_processed': files_processed,
                'bytes_transferred': bytes_transferred,
                'log': log_messages
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_files_enhanced(self, remote_path, local_path, job=None):
        """Enhanced download with advanced options from job configuration"""
        log_messages = []
        files_processed = 0
        bytes_transferred = 0
        
        try:
            import ftplib
            from datetime import datetime
            
            # Use enhanced options if job is provided (moved from site-level to job-level)
            enable_recursive = job.enable_recursive_download if job else False
            preserve_folder_structure = job.preserve_folder_structure if job else False
            enable_duplicate_renaming = job.enable_duplicate_renaming if job else False
            use_date_folders = job.use_date_folders if job else False
            date_folder_format = job.date_folder_format if job else 'YYYY-MM-DD'
            
            # Connect to FTP server with improved connection handling
            ftp = ftplib.FTP()
            ftp.connect(self.host, self.port, timeout=30)
            ftp.login(self.username, self.password)
            
            # Try passive mode first, fallback to active if needed
            try:
                ftp.set_pasv(True)
                # Test passive mode with a quick command
                ftp.pwd()
                log_messages.append("Using passive FTP mode")
            except Exception as e:
                log_messages.append(f"Passive mode failed ({e}), trying active mode")
                try:
                    ftp.set_pasv(False)
                    ftp.pwd()
                    log_messages.append("Using active FTP mode")
                except Exception as e2:
                    log_messages.append(f"Both FTP modes failed: passive={e}, active={e2}")
                    raise Exception(f"FTP connection failed in both modes: {e2}")
            
            def get_unique_filename(file_path):
                """Generate unique filename if duplicate renaming is enabled"""
                if not enable_duplicate_renaming:
                    return file_path
                
                base_path = os.path.dirname(file_path)
                base_name = os.path.basename(file_path)
                name, ext = os.path.splitext(base_name)
                
                counter = 1
                while os.path.exists(file_path):
                    new_name = f"{name}_{counter}{ext}"
                    file_path = os.path.join(base_path, new_name)
                    counter += 1
                
                return file_path
            
            def get_date_folder_path(base_path):
                """Generate date-based folder path if enabled"""
                if not use_date_folders:
                    return base_path
                
                now = datetime.now()
                
                # Format date folder based on job settings
                if date_folder_format == 'YYYY-MM-DD':
                    date_folder = now.strftime('%Y-%m-%d')
                elif date_folder_format == 'YYYY-MM':
                    date_folder = now.strftime('%Y-%m')
                elif date_folder_format == 'YYYY':
                    date_folder = now.strftime('%Y')
                else:
                    date_folder = now.strftime('%Y-%m-%d')
                
                return os.path.join(base_path, date_folder)
            
            def download_recursive(remote_dir, local_base_dir, current_relative_path=""):
                """Recursively download files from directory with proper folder structure"""
                nonlocal files_processed, bytes_transferred
                
                try:
                    # Change to remote directory
                    ftp.cwd(remote_dir)
                    lines = []
                    ftp.retrlines('LIST', lines.append)
                    
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            filename = ' '.join(parts[8:])
                            
                            if filename not in ['.', '..']:
                                if permissions.startswith('d'):
                                    # Directory - recurse into it
                                    if preserve_folder_structure:
                                        # Build the new relative path for folder structure
                                        new_relative_path = os.path.join(current_relative_path, filename) if current_relative_path else filename
                                    else:
                                        # Flattened - keep empty relative path
                                        new_relative_path = ""
                                    
                                    # Recursive call
                                    download_recursive(f"{remote_dir}/{filename}", local_base_dir, new_relative_path)
                                    
                                    # Always return to current directory after recursion
                                    ftp.cwd(remote_dir)
                                
                                else:
                                    # File - download it to appropriate location
                                    if preserve_folder_structure and current_relative_path:
                                        # Create folder structure and download to it
                                        target_local_dir = os.path.join(local_base_dir, current_relative_path)
                                    else:
                                        # Download to base directory (flattened)
                                        target_local_dir = local_base_dir
                                    
                                    # Apply date folder if enabled
                                    target_local_dir = get_date_folder_path(target_local_dir)
                                    os.makedirs(target_local_dir, exist_ok=True)
                                    
                                    local_file_path = os.path.join(target_local_dir, filename)
                                    local_file_path = get_unique_filename(local_file_path)
                                    
                                    try:
                                        with open(local_file_path, 'wb') as local_file:
                                            ftp.retrbinary(f'RETR {filename}', local_file.write)
                                        
                                        file_size = os.path.getsize(local_file_path)
                                        if file_size > 0:
                                            files_processed += 1
                                            bytes_transferred += file_size
                                            folder_info = f" in {current_relative_path}/" if current_relative_path else ""
                                            log_messages.append(f"Downloaded: {filename}{folder_info} ({file_size} bytes)")
                                        else:
                                            log_messages.append(f"Failed: {filename} (0 bytes)")
                                            if os.path.exists(local_file_path):
                                                os.remove(local_file_path)
                                        
                                    except Exception as e:
                                        log_messages.append(f"Failed to download {filename}: {str(e)}")
                                        if os.path.exists(local_file_path):
                                            os.remove(local_file_path)
                
                except Exception as e:
                    log_messages.append(f"Error processing directory {remote_dir}: {str(e)}")
            
            # Job group folder organization is handled in scheduler.py
            # Don't apply it again here to avoid duplication
            
            # Start download process - download ALL files with advanced features
            log_messages.append("Starting enhanced download with all advanced features")
            
            # Get date-based folder path
            final_local_path = get_date_folder_path(local_path)
            os.makedirs(final_local_path, exist_ok=True)
            
            try:
                # Get complete directory listing
                ftp.cwd(remote_path)
                lines = []
                ftp.retrlines('LIST', lines.append)
                
                files_found = []
                directories_found = []
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]
                        filename = ' '.join(parts[8:])
                        
                        if filename not in ['.', '..']:
                            if permissions.startswith('d'):
                                directories_found.append(filename)
                            else:
                                files_found.append(filename)
                
                log_messages.append(f"Found {len(files_found)} files and {len(directories_found)} directories")
                
                # Download all files from root directory
                for filename in files_found:
                    local_file_path = os.path.join(final_local_path, filename)
                    local_file_path = get_unique_filename(local_file_path)
                    
                    try:
                        with open(local_file_path, 'wb') as local_file:
                            ftp.retrbinary(f'RETR {filename}', local_file.write)
                        
                        file_size = os.path.getsize(local_file_path)
                        if file_size > 0:
                            files_processed += 1
                            bytes_transferred += file_size
                            log_messages.append(f"Downloaded: {filename} ({file_size} bytes)")
                        else:
                            log_messages.append(f"Failed: {filename} (0 bytes)")
                            if os.path.exists(local_file_path):
                                os.remove(local_file_path)
                    
                    except Exception as e:
                        log_messages.append(f"Error downloading {filename}: {str(e)}")
                        if os.path.exists(local_file_path):
                            os.remove(local_file_path)
                
                # Download files from subdirectories if recursive is enabled
                if enable_recursive:
                    for dir_name in directories_found:
                        try:
                            log_messages.append(f"Processing directory: {dir_name}")
                            
                            if preserve_folder_structure:
                                # Create subdirectory in local path and download to it
                                download_recursive(f"{remote_path}/{dir_name}", final_local_path, dir_name)
                            else:
                                # Flatten structure - download all files to main directory
                                download_recursive(f"{remote_path}/{dir_name}", final_local_path, "")
                            
                        except Exception as e:
                            log_messages.append(f"Error processing directory {dir_name}: {str(e)}")
                            continue
                
                log_messages.append(f"Download complete: {files_processed} files, {bytes_transferred} bytes")
                
            except Exception as e:
                log_messages.append(f"Error during download process: {str(e)}")
            
            try:
                ftp.quit()
            except:
                pass
            
            return {
                'success': True,
                'files_processed': files_processed,
                'bytes_transferred': bytes_transferred,
                'log': log_messages
            }
            
            def get_unique_filename(file_path):
                """Generate unique filename if duplicate renaming is enabled"""
                if not enable_duplicate_renaming:
                    return file_path
                
                # Check if file already exists on disk
                if not os.path.exists(file_path):
                    processed_files.add(file_path)
                    return file_path
                
                # Generate numbered variants
                directory = os.path.dirname(file_path)
                filename = os.path.basename(file_path)
                base_name, ext = os.path.splitext(filename)
                counter = 1
                
                while True:
                    new_filename = f"{base_name}_{counter}{ext}"
                    new_path = os.path.join(directory, new_filename)
                    
                    if not os.path.exists(new_path) and new_path not in processed_files:
                        processed_files.add(new_path)
                        return new_path
                    counter += 1
            
            def get_date_folder_path(base_path):
                """Generate date-based folder path if enabled"""
                if not use_date_folders:
                    return base_path
                
                from datetime import datetime
                today = datetime.now()
                
                # Convert format string to Python strftime
                format_map = {
                    'YYYY': '%Y',
                    'MM': '%m', 
                    'DD': '%d',
                    'YY': '%y'
                }
                
                python_format = date_folder_format
                for old, new in format_map.items():
                    python_format = python_format.replace(old, new)
                
                date_folder = today.strftime(python_format)
                return os.path.join(base_path, date_folder)
            
            def download_from_directory(remote_dir, local_dir, is_recursive=False):
                """Recursively download files from directory"""
                files_list = self.list_files(remote_dir)
                if not files_list['success']:
                    return files_list
                
                nonlocal files_processed, bytes_transferred
                
                for file_info in files_list['files']:
                    if file_info['type'] == 'file':
                        # Handle file downloads
                        remote_file_path = os.path.join(remote_dir, file_info['name']).replace('\\', '/')
                        
                        # Apply date folder if enabled (only at the root level to avoid nested date folders)
                        if remote_dir == remote_path:  # Only apply date folders at root level
                            target_local_dir = get_date_folder_path(local_dir)
                        else:
                            target_local_dir = local_dir
                        
                        # Create target directory
                        os.makedirs(target_local_dir, exist_ok=True)
                        
                        # Handle duplicates
                        local_file_path = os.path.join(target_local_dir, file_info['name'])
                        local_file_path = get_unique_filename(local_file_path)
                        
                        try:
                            result = self.download_file(remote_file_path, local_file_path)
                            
                            if result['success']:
                                files_processed += 1
                                bytes_transferred += result['bytes_transferred']
                                log_messages.append(f"Downloaded: {file_info['name']} -> {os.path.relpath(local_file_path, local_path)}")
                            else:
                                log_messages.append(f"Failed to download: {file_info['name']} - {result['error']}")
                        except Exception as e:
                            log_messages.append(f"Error downloading {file_info['name']}: {str(e)}")
                    
                    elif file_info['type'] == 'directory' and is_recursive:
                        # Recursively download from subdirectories (preserve structure)
                        subdir_remote = os.path.join(remote_dir, file_info['name']).replace('\\', '/')
                        
                        # Preserve original folder structure
                        subdir_local = os.path.join(local_dir, file_info['name'])
                        os.makedirs(subdir_local, exist_ok=True)
                        
                        log_messages.append(f"Entering directory: {file_info['name']}")
                        subdir_result = download_from_directory(subdir_remote, subdir_local, True)
                        if not subdir_result['success']:
                            log_messages.append(f"Warning: Failed to download directory {file_info['name']}: {subdir_result.get('error', 'Unknown error')}")
                
                return {'success': True}
            
            # Start the download process with proper recursive flag
            result = download_from_directory(remote_path, local_path, enable_recursive)
            
            if result['success']:
                return {
                    'success': True,
                    'files_processed': files_processed,
                    'bytes_transferred': bytes_transferred,
                    'log': log_messages
                }
            else:
                return result
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
