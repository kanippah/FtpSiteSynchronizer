#!/usr/bin/env python3
"""
Network Drive Permission Fix Script
This script helps fix permission issues with network drives
"""

import os
import sys
import subprocess
import pwd
from pathlib import Path

def fix_mount_permissions(mount_path):
    """Fix permissions for a mounted network drive"""
    try:
        # Get current user info
        current_user = pwd.getpwuid(os.getuid())
        uid = current_user.pw_uid
        gid = current_user.pw_gid
        
        print(f"Fixing permissions for {mount_path}")
        print(f"Current user: {current_user.pw_name} (uid={uid}, gid={gid})")
        
        # Check if mount path exists
        if not os.path.exists(mount_path):
            print(f"Error: Mount path {mount_path} does not exist")
            return False
        
        # Try to fix permissions with sudo
        commands = [
            f"sudo chown -R {uid}:{gid} {mount_path}",
            f"sudo chmod -R u+rwx {mount_path}",
            f"sudo find {mount_path} -type d -exec chmod 777 {{}} \\;",
            f"sudo find {mount_path} -type f -exec chmod 666 {{}} \\;"
        ]
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: Command failed: {result.stderr}")
            else:
                print(f"Success: {cmd}")
        
        # Test write permissions
        test_file = os.path.join(mount_path, '.permission_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✓ Write test successful for {mount_path}")
            return True
        except Exception as e:
            print(f"✗ Write test failed: {e}")
            return False
            
    except Exception as e:
        print(f"Error fixing permissions: {e}")
        return False

def check_network_drives():
    """Check all network drives in /mnt/"""
    mnt_path = Path('/mnt')
    if not mnt_path.exists():
        print("No /mnt directory found")
        return
    
    print("Checking network drives in /mnt/:")
    for item in mnt_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            print(f"\nFound potential network drive: {item}")
            
            # Check if it's mounted
            result = subprocess.run(['mount'], capture_output=True, text=True)
            if str(item) in result.stdout:
                print(f"  ✓ {item} is mounted")
                # Try to fix permissions
                if fix_mount_permissions(str(item)):
                    print(f"  ✓ Permissions fixed for {item}")
                else:
                    print(f"  ✗ Could not fix permissions for {item}")
            else:
                print(f"  - {item} is not mounted")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Fix specific mount path
        mount_path = sys.argv[1]
        fix_mount_permissions(mount_path)
    else:
        # Check all network drives
        check_network_drives()