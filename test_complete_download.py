#!/usr/bin/env python3
"""
Test complete download to see all available folders
"""
import ftplib
import sys

def test_complete_structure():
    try:
        print("=== Testing Complete FTP Structure ===")
        ftp = ftplib.FTP()
        ftp.connect('ftp.dlptest.com', 21, timeout=15)
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        ftp.set_pasv(False)  # Use active mode
        
        def list_directory(path=".", level=0):
            """Recursively list directory structure"""
            try:
                ftp.cwd(path)
                print(f"{'  ' * level}📁 {path}")
                
                lines = []
                ftp.retrlines('LIST', lines.append)
                
                directories = []
                files = []
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]
                        filename = ' '.join(parts[8:])
                        
                        if filename not in ['.', '..']:
                            if permissions.startswith('d'):
                                directories.append(filename)
                            else:
                                files.append(filename)
                
                # Print files first
                for file in files[:3]:  # Show first 3 files
                    print(f"{'  ' * (level+1)}📄 {file}")
                if len(files) > 3:
                    print(f"{'  ' * (level+1)}... and {len(files)-3} more files")
                
                # Recurse into directories
                for directory in directories:
                    if level < 2:  # Limit depth to avoid infinite recursion
                        try:
                            list_directory(f"{path}/{directory}" if path != "." else directory, level + 1)
                            ftp.cwd(path)  # Return to current directory
                        except Exception as e:
                            print(f"{'  ' * (level+1)}❌ Error accessing {directory}: {e}")
                
            except Exception as e:
                print(f"{'  ' * level}❌ Error in {path}: {e}")
        
        # Start from root
        list_directory(".")
        
        ftp.quit()
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    test_complete_structure()