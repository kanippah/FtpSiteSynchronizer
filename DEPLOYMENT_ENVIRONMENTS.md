# Deployment Environment Guide

## Container vs Server Deployment

This FTP/SFTP/NFS Manager application can be deployed in different environments with varying capabilities:

### Containerized Environment (Current Replit Environment)

**Limitations:**
- Network mounting utilities (cifs-utils, nfs-common) may not be available
- Read-only filesystem prevents traditional mount operations
- Sudo privileges may be restricted
- System utilities like ping, nc may be missing

**Network Drive Behavior:**
- Creates demonstration folder structures for testing
- Shows connection test results with environment warnings
- Provides full web interface functionality
- File browser works with local demonstration files

**Best For:**
- Development and testing
- Demonstrating the application interface
- Configuration validation
- Learning the system features

### Standard Ubuntu Server Environment

**Full Capabilities:**
- Complete network mounting support
- Full CIFS/SMB and NFS functionality
- Real network drive access
- Proper sudo privileges for mount operations

**Requirements:**
```bash
# Install required packages
sudo apt update
sudo apt install cifs-utils nfs-common

# Verify installation
dpkg -l | grep cifs-utils
dpkg -l | grep nfs-common
showmount -e YOUR_NFS_SERVER
```

**Network Drive Behavior:**
- Real network mounting to remote servers
- Actual file access from network shares
- Full browsing capabilities
- Production-ready file operations

## Your Current Server Configuration

Based on your Ubuntu 24.04 server output:

✅ **cifs-utils**: Installed (version 2:7.0-2ubuntu0.2)
✅ **nfs-common**: Installed (version 1:2.6.4-3ubuntu5.1)
✅ **NFS Exports**: Visible via showmount command

Your server shows:
- `/volume1/VeeamBackup` - accessible from specific IPs
- `/volume1/VMware` - accessible from specific IPs

## Deployment Recommendations

### For Production Use
Deploy on your Ubuntu 24.04 server where:
- All required packages are installed
- Network mounting works properly
- Full sudo access is available
- Real network drives can be mounted

### For Development/Testing
Use the containerized environment for:
- Interface development
- Configuration testing
- Feature demonstration
- User training

## Connection Testing Commands

On your Ubuntu server, test network drives manually:

```bash
# Test NFS mount
sudo mkdir -p /mnt/test_nfs
sudo mount -t nfs 10.10.10.28:/volume1/VeeamBackup /mnt/test_nfs
ls -la /mnt/test_nfs
sudo umount /mnt/test_nfs

# Test CIFS mount (if applicable)
sudo mkdir -p /mnt/test_cifs
sudo mount -t cifs //10.10.10.28/ShareName /mnt/test_cifs -o username=yourusername
ls -la /mnt/test_cifs
sudo umount /mnt/test_cifs
```

## Environment Detection

The application automatically detects the environment and:
- Shows appropriate warnings in the web interface
- Creates demonstration folders in containerized environments
- Enables full mounting in server environments
- Provides relevant error messages and guidance

This ensures the application works in both environments while setting appropriate expectations for users.