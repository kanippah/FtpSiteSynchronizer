#!/usr/bin/env python3
"""
Debug the job execution issue
"""
import os
import sys
sys.path.append('.')

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://ftpmanager_user:password@localhost/ftpmanager_db'

try:
    from main import app
    from models import db, Job, Site
    from crypto_utils import decrypt_password
    from ftp_client import FTPClient
    
    with app.app_context():
        # Get the test job
        job = Job.query.filter_by(name='TEST-DOWNLOAD').first()
        if not job:
            print("Job TEST-DOWNLOAD not found")
            sys.exit(1)
        
        site = job.site
        print(f"Job: {job.name}")
        print(f"Site: {site.name}")
        print(f"Protocol: {site.protocol}")
        print(f"Host: {site.host}:{site.port}")
        print(f"Remote path: {site.remote_path}")
        print(f"Recursive: {job.enable_recursive_download}")
        print(f"Preserve structure: {job.preserve_folder_structure}")
        print(f"Download all: {job.download_all}")
        
        # Try to connect
        try:
            password = decrypt_password(site.password_encrypted)
            client = FTPClient(site.protocol, site.host, site.port, site.username, password)
            
            print("\nTesting connection...")
            result = client.test_connection()
            print(f"Connection test: {result}")
            
            if result['success']:
                print("\nListing files...")
                files_result = client.list_files(site.remote_path)
                print(f"Files list: {files_result}")
                
                if files_result['success']:
                    print(f"Found {len(files_result['files'])} items")
                    for item in files_result['files'][:5]:  # Show first 5
                        print(f"  {item['type']}: {item['name']}")
            
        except Exception as e:
            print(f"Connection error: {e}")
        
except Exception as e:
    print(f"Script error: {e}")
    import traceback
    traceback.print_exc()