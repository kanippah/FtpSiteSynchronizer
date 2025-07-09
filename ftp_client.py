import ftplib
import paramiko
import os
import logging
from datetime import datetime
from pathlib import Path
import stat

logger = logging.getLogger(__name__)

class FTPClient:
    """Unified FTP/SFTP client"""
    
    def __init__(self, protocol, host, port, username, password):
        self.protocol = protocol.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
        self.transport = None
        
    def connect(self):
        """Establish connection"""
        try:
            if self.protocol == 'ftp':
                self.connection = ftplib.FTP()
                # Set timeout for FTP connections
                self.connection.connect(self.host, self.port, timeout=30)
                self.connection.login(self.username, self.password)
                # Set passive mode for better firewall compatibility
                self.connection.set_pasv(True)
            elif self.protocol == 'sftp':
                transport = paramiko.Transport((self.host, self.port))
                # Set timeout for SFTP connections
                transport.set_keepalive(30)
                transport.connect(username=self.username, password=self.password, timeout=30)
                self.connection = paramiko.SFTPClient.from_transport(transport)
                self.transport = transport  # Keep reference for cleanup
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
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            files = []
            
            if self.protocol == 'ftp':
                try:
                    self.connection.cwd(remote_path)
                    file_list = self.connection.nlst()
                    
                    for filename in file_list:
                        try:
                            # Get file details
                            file_info = self.connection.mlsd(filename)
                            for name, facts in file_info:
                                if name == filename:
                                    files.append({
                                        'name': name,
                                        'size': facts.get('size', 0),
                                        'modify': facts.get('modify', ''),
                                        'type': facts.get('type', 'file')
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
                            'type': 'dir' if stat.S_ISDIR(file_attr.st_mode) else 'file'
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
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            # Create remote directory if needed
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and remote_dir != '.':
                try:
                    if self.protocol == 'ftp':
                        self.connection.mkd(remote_dir)
                    elif self.protocol == 'sftp':
                        self.connection.mkdir(remote_dir)
                except:
                    pass  # Directory might already exist
            
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
        """Download entire folder structure"""
        try:
            return self.download_files(remote_path, local_path)
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def download_all_files(self, remote_path, local_path):
        """Download all files (same as download_files for now)"""
        return self.download_files(remote_path, local_path)
    
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
