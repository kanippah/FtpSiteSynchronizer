#!/bin/bash

# Quick deployment verification script
# Run this after deploy.sh to verify everything is working

echo "=== FTP/SFTP/NFS Manager Deployment Verification ==="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_service() {
    local service_name=$1
    if systemctl is-active --quiet $service_name; then
        echo -e "  ✓ $service_name: ${GREEN}Running${NC}"
    else
        echo -e "  ✗ $service_name: ${RED}Not running${NC}"
    fi
}

check_command() {
    local cmd=$1
    if command -v $cmd > /dev/null; then
        echo -e "  ✓ $cmd: ${GREEN}Available${NC}"
    else
        echo -e "  ✗ $cmd: ${RED}Not found${NC}"
    fi
}

echo "1. System Services:"
check_service postgresql
check_service apache2
check_service supervisor

echo ""
echo "2. Network Tools:"
check_command ping
check_command nc
check_command mount.cifs
check_command showmount
check_command smbclient

echo ""
echo "3. Application Status:"
if [ -f "/home/ftpmanager/ftpmanager/main.py" ]; then
    echo -e "  ✓ Application files: ${GREEN}Present${NC}"
else
    echo -e "  ✗ Application files: ${RED}Missing${NC}"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -q "200\|302"; then
    echo -e "  ✓ Web interface: ${GREEN}Responding${NC}"
else
    echo -e "  ✗ Web interface: ${RED}Not responding${NC}"
fi

echo ""
echo "4. Database Connection:"
sudo -u ftpmanager bash -c "cd /home/ftpmanager/ftpmanager && source venv/bin/activate && python3 -c \"
import psycopg2
import os
try:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                os.environ['DATABASE_URL'] = line.split('=', 1)[1].strip()
                break
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('  ✓ Database: Connected')
except Exception as e:
    print(f'  ✗ Database: {e}')
\"" 2>/dev/null || echo -e "  ✗ Database: ${RED}Connection failed${NC}"

echo ""
echo "5. Network Drive Testing Commands:"
echo "  # Test NFS mount:"
echo "  sudo mkdir -p /mnt/test_nfs"
echo "  sudo mount -t nfs YOUR_NFS_SERVER:/export/path /mnt/test_nfs"
echo "  ls /mnt/test_nfs"
echo "  sudo umount /mnt/test_nfs"
echo ""
echo "  # Test CIFS mount:"
echo "  sudo mkdir -p /mnt/test_cifs"
echo "  sudo mount -t cifs //YOUR_SERVER/share /mnt/test_cifs -o username=user"
echo "  ls /mnt/test_cifs"
echo "  sudo umount /mnt/test_cifs"

echo ""
echo "=== Verification Complete ==="
echo ""
echo "If all checks show green checkmarks, your deployment is successful!"
echo "Access your FTP Manager at: http://$(hostname -I | awk '{print $1}')"
echo ""