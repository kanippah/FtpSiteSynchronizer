#!/usr/bin/env python3
"""
Simple FTP test to see what files are actually available
"""
import ftplib
import sys

def test_files():
    try:
        print("=== Simple FTP Test ===")
        ftp = ftplib.FTP()
        ftp.connect('ftp.dlptest.com', 21, timeout=15)
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        
        # Use active mode to avoid passive mode issues
        ftp.set_pasv(False)
        
        print("Root directory:")
        try:
            lines = []
            ftp.retrlines('LIST', lines.append)
            for line in lines:
                print(f"  {line}")
        except Exception as e:
            print(f"LIST failed: {e}")
            return False
        
        # Try to enter Download-FTP directory
        print("\nEntering Download-FTP directory...")
        try:
            ftp.cwd('Download-FTP')
            print("Successfully changed to Download-FTP")
            
            print("Contents of Download-FTP:")
            sublines = []
            ftp.retrlines('LIST', sublines.append)
            for line in sublines:
                print(f"  {line}")
                
        except Exception as e:
            print(f"Error accessing Download-FTP: {e}")
        
        ftp.quit()
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    test_files()