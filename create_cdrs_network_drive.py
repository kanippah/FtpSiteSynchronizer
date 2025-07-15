#!/usr/bin/env python3
"""
Create Network Drive Configuration for /mnt/cdrs
This script creates a network drive configuration for the existing /mnt/cdrs mount
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, '.')

def create_cdrs_network_drive():
    """Create network drive configuration for /mnt/cdrs"""
    try:
        # Set up environment
        os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/ftpmanager_db')
        os.environ['SESSION_SECRET'] = os.environ.get('SESSION_SECRET', 'development-secret-key')
        os.environ['ENCRYPTION_KEY'] = os.environ.get('ENCRYPTION_KEY', 'development-encryption-key')
        
        # Import after setting environment
        from main import app
        from models import db, NetworkDrive
        from network_drive_manager import NetworkDriveManager
        from crypto_utils import encrypt_password
        
        with app.app_context():
            # Check if cdrs drive already exists
            existing_drive = NetworkDrive.query.filter_by(mount_point='/mnt/cdrs').first()
            if existing_drive:
                print(f"Network drive already exists: {existing_drive.name}")
                return existing_drive.id
            
            # Create network drive configuration
            drive_manager = NetworkDriveManager()
            
            # Determine server path from mount information
            try:
                result = subprocess.run(['mount'], capture_output=True, text=True)
                mount_lines = result.stdout.split('\n')
                
                server_path = None
                drive_type = None
                
                for line in mount_lines:
                    if '/mnt/cdrs' in line:
                        parts = line.split()
                        if len(parts) >= 6:
                            server_path = parts[0]
                            mount_info = parts[5]
                            
                            if 'cifs' in mount_info or 'smb' in mount_info:
                                drive_type = 'cifs'
                            elif 'nfs' in mount_info:
                                drive_type = 'nfs'
                            break
                
                if not server_path or not drive_type:
                    print("Could not determine server path and type from mount info")
                    print("Please check mount output:")
                    print(result.stdout)
                    return None
                
                print(f"Detected {drive_type.upper()} drive: {server_path} -> /mnt/cdrs")
                
                # Create network drive
                drive_id = drive_manager.create_drive(
                    name="CDRS Network Drive",
                    drive_type=drive_type,
                    server_path=server_path,
                    mount_point="/mnt/cdrs",
                    username="ftpmanager",  # Default username
                    password="",  # Empty password - will be managed externally
                    mount_options=f"uid={os.getuid()},gid={os.getgid()},file_mode=0666,dir_mode=0777,rw",
                    auto_mount=True
                )
                
                print(f"Created network drive configuration with ID: {drive_id}")
                
                # Mark as mounted since it's already mounted
                drive = NetworkDrive.query.get(drive_id)
                drive.is_mounted = True
                db.session.commit()
                
                print("Marked drive as mounted")
                
                # Test permissions
                permission_check = drive_manager.check_drive_permissions(drive_id)
                if permission_check['success']:
                    print("✓ Drive permissions are working correctly")
                else:
                    print(f"✗ Drive permission issue: {permission_check.get('error', 'Unknown error')}")
                    print("Run: python3 fix_network_drive_permissions.py /mnt/cdrs")
                
                return drive_id
                
            except Exception as e:
                print(f"Error analyzing mount: {e}")
                return None
                
    except Exception as e:
        print(f"Error creating network drive: {e}")
        return None

if __name__ == '__main__':
    print("Creating network drive configuration for /mnt/cdrs...")
    drive_id = create_cdrs_network_drive()
    
    if drive_id:
        print(f"✓ Success! Network drive created with ID: {drive_id}")
        print("\nNext steps:")
        print("1. Update job local paths to use /mnt/cdrs/your_subfolder")
        print("2. Test the Upload to MANAGEMENT job")
        print("3. If permission issues persist, run: python3 fix_network_drive_permissions.py /mnt/cdrs")
    else:
        print("✗ Failed to create network drive configuration")
        print("Please check mount status and try again")