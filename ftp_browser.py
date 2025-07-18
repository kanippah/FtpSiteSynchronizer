"""
Enhanced FTP client for file browsing functionality
"""
import os
import stat
import math
from datetime import datetime
from ftp_client import FTPClient


class FTPBrowser(FTPClient):
    """Extended FTP client with file browser capabilities"""
    
    def browse_directory(self, remote_path='.'):
        """Browse directory with detailed file information for web interface"""
        try:
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            items = []
            current_path = remote_path
            
            if self.protocol == 'ftp':
                # Get current directory if using relative path
                if remote_path == '.':
                    current_path = self.connection.pwd()
                elif not remote_path.startswith('/'):
                    current_path = os.path.join(self.connection.pwd(), remote_path).replace('\\', '/')
                
                # List directory contents with details
                try:
                    lines = []
                    self.connection.retrlines(f'LIST {remote_path}', lines.append)
                    
                    for line in lines:
                        parts = line.split(None, 8)
                        if len(parts) >= 9:
                            permissions = parts[0]
                            is_dir = permissions.startswith('d')
                            size = 0 if is_dir else int(parts[4])
                            name = parts[8]
                            
                            # Skip current and parent directory entries
                            if name in ['.', '..']:
                                continue
                            
                            # Parse date
                            try:
                                date_str = f"{parts[5]} {parts[6]} {parts[7]}"
                                if ':' in parts[7]:  # Recent files show time
                                    date_str = f"{parts[5]} {parts[6]} {datetime.now().year} {parts[7]}"
                                    modified = datetime.strptime(date_str, "%b %d %Y %H:%M")
                                else:  # Older files show year
                                    modified = datetime.strptime(date_str, "%b %d %Y")
                            except:
                                modified = None
                            
                            # Construct proper path
                            if current_path == '/' or current_path == '.':
                                full_path = f'/{name}'
                            else:
                                full_path = f"{current_path.rstrip('/')}/{name}"
                            
                            items.append({
                                'name': name,
                                'is_directory': is_dir,
                                'size': size,
                                'size_formatted': self._format_size(size),
                                'permissions': permissions,
                                'modified': modified.isoformat() if modified else '',
                                'modified_formatted': modified.strftime('%Y-%m-%d %H:%M') if modified else '',
                                'path': full_path,
                                'type': 'directory' if is_dir else 'file'
                            })
                except Exception as e:
                    # Fallback to basic listing
                    try:
                        file_list = self.connection.nlst(remote_path)
                        for name in file_list:
                            if name not in ['.', '..']:
                                items.append({
                                    'name': name,
                                    'is_directory': False,
                                    'size': 0,
                                    'size_formatted': '-',
                                    'permissions': '-',
                                    'modified': '',
                                    'modified_formatted': '',
                                    'path': f"{current_path.rstrip('/')}/{name}" if current_path not in ['/', '.'] else f'/{name}',
                                    'type': 'file'
                                })
                    except Exception as inner_e:
                        self.disconnect()
                        return {'success': False, 'error': f'Failed to list directory: {str(inner_e)}'}
            
            elif self.protocol == 'nfs':
                # NFS browsing using the NFS client
                from nfs_client import NFSClient
                
                # Create NFS client with the same parameters
                nfs_client = NFSClient(
                    self.host,
                    getattr(self, 'nfs_export_path', '/'),
                    getattr(self, 'nfs_version', '4'),
                    getattr(self, 'nfs_mount_options', ''),
                    getattr(self, 'nfs_auth_method', 'sys')
                )
                
                try:
                    # Mount the NFS share
                    if not nfs_client.mount():
                        return {'success': False, 'error': 'Failed to mount NFS share'}
                    
                    # List files using NFS client
                    result = nfs_client.list_files(remote_path)
                    
                    if result['success']:
                        for file_info in result['files']:
                            # Convert NFS file info to browser format
                            name = file_info['name']
                            is_dir = file_info['type'] == 'dir'
                            size = file_info['size']
                            
                            # Parse modification time
                            modified = None
                            try:
                                modified = datetime.fromisoformat(file_info['modify'])
                            except:
                                pass
                            
                            # Construct proper path
                            if current_path == '/' or current_path == '.':
                                full_path = f'/{name}'
                            else:
                                full_path = f"{current_path.rstrip('/')}/{name}"
                            
                            items.append({
                                'name': name,
                                'is_directory': is_dir,
                                'size': size,
                                'size_formatted': self._format_size(size),
                                'permissions': 'drwxr-xr-x' if is_dir else '-rw-r--r--',
                                'modified': modified.isoformat() if modified else '',
                                'modified_formatted': modified.strftime('%Y-%m-%d %H:%M') if modified else '',
                                'path': full_path,
                                'type': 'directory' if is_dir else 'file'
                            })
                    else:
                        return {'success': False, 'error': result.get('error', 'Failed to list NFS directory')}
                        
                finally:
                    # Always unmount when done
                    nfs_client.unmount()
                        
            elif self.protocol == 'sftp':
                # Get current directory if using relative path
                if remote_path == '.':
                    current_path = self.connection.getcwd() or '/'
                elif not remote_path.startswith('/'):
                    current_path = os.path.join(self.connection.getcwd() or '/', remote_path).replace('\\', '/')
                
                try:
                    file_list = self.connection.listdir_attr(remote_path)
                    
                    for file_attr in file_list:
                        name = file_attr.filename
                        
                        # Skip current and parent directory entries
                        if name in ['.', '..']:
                            continue
                            
                        is_dir = hasattr(file_attr, 'st_mode') and stat.S_ISDIR(file_attr.st_mode)
                        size = file_attr.st_size if hasattr(file_attr, 'st_size') else 0
                        if is_dir:
                            size = 0
                            
                        modified = None
                        if hasattr(file_attr, 'st_mtime'):
                            modified = datetime.fromtimestamp(file_attr.st_mtime)
                        
                        # Construct proper path
                        if current_path == '/' or current_path == '.':
                            full_path = f'/{name}'
                        else:
                            full_path = f"{current_path.rstrip('/')}/{name}"
                        
                        items.append({
                            'name': name,
                            'is_directory': is_dir,
                            'size': size,
                            'size_formatted': self._format_size(size),
                            'permissions': oct(file_attr.st_mode)[-3:] if hasattr(file_attr, 'st_mode') else '-',
                            'modified': modified.isoformat() if modified else '',
                            'modified_formatted': modified.strftime('%Y-%m-%d %H:%M') if modified else '',
                            'path': full_path,
                            'type': 'directory' if is_dir else 'file'
                        })
                        
                except Exception as e:
                    self.disconnect()
                    return {'success': False, 'error': f'Failed to list directory: {str(e)}'}
            
            # Sort directories first, then files alphabetically
            items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            
            self.disconnect()
            
            # Calculate parent path properly
            parent_path = None
            if current_path and current_path != '/' and current_path != '.':
                parent_dir = os.path.dirname(current_path)
                if parent_dir == '':
                    parent_path = '.'
                elif parent_dir == '/':
                    parent_path = ''  # Root directory
                else:
                    parent_path = parent_dir
            
            return {
                'success': True,
                'current_path': current_path,
                'parent_path': parent_path,
                'items': items
            }
            
        except Exception as e:
            self.disconnect()
            return {'success': False, 'error': str(e)}
    
    def _format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return '0 B'
        
        size_names = ['B', 'KB', 'MB', 'GB', 'TB']
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f'{s} {size_names[i]}'
    
    def get_file_content_preview(self, remote_path, max_size=1024):
        """Get a preview of text file content"""
        try:
            if self.protocol == 'nfs':
                # NFS file preview
                from nfs_client import NFSClient
                
                nfs_client = NFSClient(
                    self.host,
                    getattr(self, 'nfs_export_path', '/'),
                    getattr(self, 'nfs_version', '4'),
                    getattr(self, 'nfs_mount_options', ''),
                    getattr(self, 'nfs_auth_method', 'sys')
                )
                
                try:
                    # Mount the NFS share
                    if not nfs_client.mount():
                        return {'success': False, 'error': 'Failed to mount NFS share for preview'}
                    
                    # Convert remote path to local mount path
                    if remote_path.startswith('/'):
                        remote_path = remote_path[1:]
                    
                    full_path = os.path.join(nfs_client.mount_point, remote_path) if remote_path else nfs_client.mount_point
                    
                    if not os.path.exists(full_path):
                        return {'success': False, 'error': f'File does not exist: {remote_path}'}
                    
                    if os.path.isdir(full_path):
                        return {'success': False, 'error': 'Cannot preview directory'}
                    
                    # Check file size
                    file_size = os.path.getsize(full_path)
                    if file_size > max_size:
                        return {
                            'success': True,
                            'content': f'File too large to preview ({file_size} bytes). Maximum preview size is {max_size} bytes.',
                            'is_text': True
                        }
                    
                    # Try to read file content
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read(max_size)
                        return {'success': True, 'content': content, 'is_text': True}
                    except UnicodeDecodeError:
                        # Try other encodings
                        for encoding in ['latin1', 'ascii', 'utf-16']:
                            try:
                                with open(full_path, 'r', encoding=encoding) as f:
                                    content = f.read(max_size)
                                return {'success': True, 'content': content, 'is_text': True}
                            except:
                                continue
                        # If all encodings fail, it's likely a binary file
                        return {
                            'success': True,
                            'content': f'Binary file ({file_size} bytes). Cannot display content.',
                            'is_text': False
                        }
                        
                except Exception as e:
                    return {'success': False, 'error': str(e)}
                finally:
                    nfs_client.unmount()
            
            # Handle FTP/SFTP protocols
            if not self.connect():
                return {'success': False, 'error': 'Connection failed'}
            
            import io
            content = io.BytesIO()
            
            if self.protocol == 'ftp':
                # Download limited content
                def store_chunk(chunk):
                    if content.tell() < max_size:
                        content.write(chunk[:max_size - content.tell()])
                
                try:
                    self.connection.retrbinary(f'RETR {remote_path}', store_chunk)
                except Exception as e:
                    self.disconnect()
                    return {'success': False, 'error': f'Failed to retrieve file: {str(e)}'}
                    
            elif self.protocol == 'sftp':
                try:
                    with self.connection.open(remote_path, 'rb') as remote_file:
                        chunk = remote_file.read(max_size)
                        content.write(chunk)
                except Exception as e:
                    self.disconnect()
                    return {'success': False, 'error': f'Failed to retrieve file: {str(e)}'}
            
            self.disconnect()
            
            # Check if we got any content
            content_bytes = content.getvalue()
            if not content_bytes:
                return {'success': False, 'error': 'File is empty or could not be read'}
            
            # Try to decode as text
            try:
                text_content = content_bytes.decode('utf-8')
                return {'success': True, 'content': text_content, 'is_text': True}
            except UnicodeDecodeError:
                # Try other encodings
                for encoding in ['latin1', 'ascii', 'utf-16']:
                    try:
                        text_content = content_bytes.decode(encoding)
                        return {'success': True, 'content': text_content, 'is_text': True}
                    except:
                        continue
                # If all encodings fail, it's likely a binary file
                return {'success': True, 'content': '[Binary file - cannot preview as text]', 'is_text': False}
                
        except Exception as e:
            self.disconnect()
            return {'success': False, 'error': str(e)}