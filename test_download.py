#!/usr/bin/env python3
"""
Quick test download script to verify FTP functionality
"""

import ftplib
import os
import time

def test_download():
    """Test FTP download with proper error handling"""
    try:
        # Create target folder
        target_folder = './downloads/2025-07/Job-Folder-Name'
        os.makedirs(target_folder, exist_ok=True)
        
        print("Connecting to FTP server...")
        ftp = ftplib.FTP()
        ftp.connect('ftp.dlptest.com', 21, timeout=60)
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        ftp.set_pasv(True)
        
        print("Getting file list...")
        files = ftp.nlst()
        print(f"Found {len(files)} files")
        
        files_downloaded = 0
        bytes_downloaded = 0
        
        # Download first 3 files
        for filename in files[:3]:
            if filename not in ['.', '..'] and not filename.startswith('.'):
                local_path = os.path.join(target_folder, filename)
                
                try:
                    print(f"Downloading {filename}...")
                    with open(local_path, 'wb') as f:
                        ftp.retrbinary(f'RETR {filename}', f.write)
                    
                    file_size = os.path.getsize(local_path)
                    if file_size > 0:
                        files_downloaded += 1
                        bytes_downloaded += file_size
                        print(f"  SUCCESS: {filename} ({file_size} bytes)")
                    else:
                        print(f"  FAILED: {filename} (0 bytes)")
                        os.remove(local_path)
                        
                except Exception as e:
                    print(f"  ERROR: {filename} - {str(e)}")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                
                # Small delay between downloads
                time.sleep(1)
        
        ftp.quit()
        
        print(f"\nDownload Summary:")
        print(f"Files downloaded: {files_downloaded}")
        print(f"Bytes downloaded: {bytes_downloaded}")
        
        return {
            'success': True,
            'files_processed': files_downloaded,
            'bytes_transferred': bytes_downloaded
        }
        
    except Exception as e:
        print(f"Download failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == "__main__":
    result = test_download()
    print(f"\nResult: {result}")