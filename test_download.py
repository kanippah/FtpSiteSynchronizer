#!/usr/bin/env python3
"""
Test what's actually available on the FTP server vs what we downloaded
"""
import ftplib
import os

def compare_ftp_vs_local():
    print("=== FTP Server vs Local Downloads Comparison ===")
    
    # Check local downloads
    print("\n🏠 LOCAL DOWNLOADS:")
    for root, dirs, files in os.walk("downloads/"):
        level = root.replace("downloads/", "").count(os.sep)
        indent = "  " * level
        print(f"{indent}📁 {os.path.basename(root)}/")
        subindent = "  " * (level + 1)
        for file in files[:5]:  # Show first 5 files
            print(f"{subindent}📄 {file}")
        if len(files) > 5:
            print(f"{subindent}... and {len(files)-5} more files")
    
    # Check FTP server structure
    print("\n🌐 FTP SERVER STRUCTURE:")
    try:
        ftp = ftplib.FTP()
        ftp.connect('ftp.dlptest.com', 21, timeout=15)
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        ftp.set_pasv(False)
        
        def list_ftp_dir(path=".", level=0):
            try:
                ftp.cwd(path)
                lines = []
                ftp.retrlines('LIST', lines.append)
                
                indent = "  " * level
                print(f"{indent}📁 {path}")
                
                dirs = []
                files = []
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]
                        filename = ' '.join(parts[8:])
                        
                        if filename not in ['.', '..']:
                            if permissions.startswith('d'):
                                dirs.append(filename)
                            else:
                                files.append(filename)
                
                subindent = "  " * (level + 1)
                for file in files[:3]:
                    print(f"{subindent}📄 {file}")
                if len(files) > 3:
                    print(f"{subindent}... and {len(files)-3} more files")
                
                # Recurse into directories (limit depth)
                if level < 2:
                    for dirname in dirs:
                        try:
                            list_ftp_dir(f"{path}/{dirname}" if path != "." else dirname, level + 1)
                            ftp.cwd(path)
                        except Exception as e:
                            print(f"{subindent}❌ Error accessing {dirname}: {e}")
                            
            except Exception as e:
                print(f"❌ Error listing {path}: {e}")
        
        list_ftp_dir(".")
        ftp.quit()
        
    except Exception as e:
        print(f"❌ FTP connection failed: {e}")

if __name__ == "__main__":
    compare_ftp_vs_local()