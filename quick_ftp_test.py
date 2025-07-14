#!/usr/bin/env python3
import ftplib
import socket

def quick_test():
    try:
        # Quick connectivity test
        print("Testing basic connectivity...")
        socket.create_connection(('ftp.dlptest.com', 21), timeout=10)
        print("✓ Port 21 is reachable")
        
        # Try FTP login
        print("Testing FTP login...")
        ftp = ftplib.FTP()
        ftp.connect('ftp.dlptest.com', 21, timeout=15)
        ftp.login('dlpuser', 'rNrKYTX9g7z3RgJRmxWuGHbeu')
        print("✓ FTP login successful")
        
        # Test directory listing
        print("Testing directory listing...")
        try:
            files = []
            ftp.retrlines('LIST', files.append)
            print(f"✓ Directory listing successful: {len(files)} items")
            for i, f in enumerate(files[:3]):
                print(f"  {i+1}: {f}")
        except Exception as e:
            print(f"✗ Directory listing failed: {e}")
        
        ftp.quit()
        return True
        
    except socket.timeout:
        print("✗ Connection timeout")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    quick_test()