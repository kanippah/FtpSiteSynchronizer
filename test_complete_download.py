#!/usr/bin/env python3
"""
Test script to download ALL files from FTP server with advanced features
"""
import os
import ftplib
from datetime import datetime

def download_all_files_complete():
    """Download all files with all advanced features"""
    
    # FTP connection details
    host = 'ftp.dlptest.com'
    port = 21
    username = 'dlpuser'
    password = 'rNrKYTX9g7z3RgJRmxWuGHbeu'
    
    # Advanced features
    enable_recursive = True
    enable_duplicate_renaming = True
    use_date_folders = True
    date_folder_format = 'YYYY-MM-DD'
    
    # Local path setup
    base_path = './downloads/2025-07/Job-Folder-Name'
    
    # Create date-based folder
    now = datetime.now()
    date_folder = now.strftime('%Y-%m-%d')
    final_path = os.path.join(base_path, date_folder)
    os.makedirs(final_path, exist_ok=True)
    
    print(f"Downloading to: {final_path}")
    
    # Connect to FTP
    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(username, password)
    ftp.set_pasv(True)
    
    files_processed = 0
    bytes_transferred = 0
    
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
    
    try:
        # Get root directory listing
        ftp.cwd('/')
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
        
        print(f"Found {len(files_found)} files and {len(directories_found)} directories")
        
        # Download all files from root
        for filename in files_found:
            local_file_path = os.path.join(final_path, filename)
            local_file_path = get_unique_filename(local_file_path)
            
            try:
                print(f"Downloading: {filename}")
                with open(local_file_path, 'wb') as local_file:
                    ftp.retrbinary(f'RETR {filename}', local_file.write)
                
                file_size = os.path.getsize(local_file_path)
                if file_size > 0:
                    files_processed += 1
                    bytes_transferred += file_size
                    print(f"  Success: {filename} ({file_size} bytes)")
                else:
                    print(f"  Failed: {filename} (0 bytes)")
                    os.remove(local_file_path)
            
            except Exception as e:
                print(f"  Error: {filename} - {str(e)}")
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
        
        # Download from subdirectories if recursive enabled
        if enable_recursive:
            for dir_name in directories_found:
                try:
                    print(f"Processing directory: {dir_name}")
                    ftp.cwd(f"/{dir_name}")
                    
                    subdir_lines = []
                    ftp.retrlines('LIST', subdir_lines.append)
                    
                    for line in subdir_lines:
                        parts = line.split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            filename = ' '.join(parts[8:])
                            
                            if filename not in ['.', '..'] and not permissions.startswith('d'):
                                # Download to main directory (flattened)
                                local_file_path = os.path.join(final_path, filename)
                                local_file_path = get_unique_filename(local_file_path)
                                
                                try:
                                    print(f"  Downloading: {dir_name}/{filename}")
                                    with open(local_file_path, 'wb') as local_file:
                                        ftp.retrbinary(f'RETR {filename}', local_file.write)
                                    
                                    file_size = os.path.getsize(local_file_path)
                                    if file_size > 0:
                                        files_processed += 1
                                        bytes_transferred += file_size
                                        print(f"    Success: {filename} ({file_size} bytes)")
                                    else:
                                        print(f"    Failed: {filename} (0 bytes)")
                                        os.remove(local_file_path)
                                
                                except Exception as e:
                                    print(f"    Error: {filename} - {str(e)}")
                                    if os.path.exists(local_file_path):
                                        os.remove(local_file_path)
                    
                    # Go back to root
                    ftp.cwd('/')
                
                except Exception as e:
                    print(f"Error processing directory {dir_name}: {str(e)}")
        
        print(f"\nDownload Summary:")
        print(f"Files processed: {files_processed}")
        print(f"Bytes transferred: {bytes_transferred}")
        print(f"Download location: {final_path}")
        
    except Exception as e:
        print(f"Error during download: {str(e)}")
    
    finally:
        ftp.quit()
        print("FTP connection closed")

if __name__ == "__main__":
    download_all_files_complete()