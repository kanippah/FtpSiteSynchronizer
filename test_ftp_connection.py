#!/usr/bin/env python3
"""
Test FTP connection and list files
"""
import ftplib
import socket

def test_ftp_connection():
    """Test FTP connection with detailed debugging"""
    try:
        print("Testing FTP connection to ftp.dlptest.com...")
        
        # Create FTP connection with timeout
        ftp = ftplib.FTP()
        ftp.set_debuglevel(1)  # Enable debug output
        
        print("Connecting...")
        ftp.connect('ftp.dlptest.com', 21, timeout=30)
        
        print("Logging in...")
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        
        print("Setting passive mode...")
        ftp.set_pasv(True)
        
        print("Getting directory listing...")
        files = []
        ftp.retrlines('LIST', files.append)
        
        print(f"Found {len(files)} items:")
        for item in files:
            print(f"  {item}")
        
        print("Getting PWD...")
        current_dir = ftp.pwd()
        print(f"Current directory: {current_dir}")
        
        # Try to download a test file if any exist
        print("\nLooking for files to download...")
        for item in files:
            parts = item.split()
            if len(parts) >= 9 and not parts[0].startswith('d'):
                filename = ' '.join(parts[8:])
                print(f"Found file: {filename}")
                try:
                    print(f"Attempting to download {filename}...")
                    with open(f"test_{filename}", 'wb') as f:
                        ftp.retrbinary(f'RETR {filename}', f.write)
                    print(f"Successfully downloaded {filename}")
                    break
                except Exception as e:
                    print(f"Failed to download {filename}: {e}")
        
        ftp.quit()
        print("FTP connection test completed successfully")
        return True
        
    except socket.timeout:
        print("ERROR: Connection timeout - FTP server is not responding")
        return False
    except ftplib.error_perm as e:
        print(f"ERROR: Permission denied - {e}")
        return False
    except Exception as e:
        print(f"ERROR: FTP connection failed - {e}")
        return False

if __name__ == "__main__":
    test_ftp_connection()