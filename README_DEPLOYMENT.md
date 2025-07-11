# FTP/SFTP/NFS Manager - Deployment Guide

## Overview

This application provides comprehensive file transfer management with support for FTP, SFTP, and NFS protocols. It includes advanced features like job scheduling, network drive mounting, and file browsing capabilities.

## Deployment Options

### Option 1: Full Ubuntu Server 24.04 Deployment (Recommended for Production)

Use the enhanced deployment script for complete Ubuntu 24.04 setup with all network tools:

```bash
# Download and run the complete deployment script
sudo bash deploy_ubuntu.sh
```

**What this installs:**
- All network diagnostic tools (ping, netcat, traceroute, nmap)
- CIFS/SMB support (cifs-utils, samba-common-bin, smbclient)
- NFS support (nfs-common, showmount, mount.nfs)
- Security tools (fail2ban, ufw firewall)
- Monitoring tools (htop, iotop, nethogs)
- SSL certificate support (certbot for Let's Encrypt)
- PostgreSQL database with optimized configuration
- Nginx reverse proxy with production settings
- Python virtual environment with all dependencies
- Systemd service for automatic startup
- Proper sudo permissions for network mounting

### Option 2: Standard Deployment with Network Tools

Use the updated existing deployment script:

```bash
# Download and run the standard deployment script
sudo bash deploy.sh
```

**What this includes:**
- Core network tools (ping, netcat, traceroute, dnsutils)
- CIFS/SMB and NFS mounting support
- Basic monitoring tools
- Standard PostgreSQL and web server setup
- Network drive mount point preparation
- Sudo permissions for mounting operations

## Network Tools Verification

Both deployment scripts include automatic verification of network tools:

```bash
Testing network tools:
  ✓ Ping: Working
  ✓ Netcat: Available  
  ✓ CIFS mount: Available
  ✓ NFS showmount: Available
  ✓ SMB client: Available
```

## Network Drive Testing

After deployment, test network mounting with these commands:

### NFS Testing
```bash
# Test NFS mount
sudo mkdir -p /mnt/test_nfs
sudo mount -t nfs 10.10.10.28:/volume1/VeeamBackup /mnt/test_nfs
ls -la /mnt/test_nfs
sudo umount /mnt/test_nfs
```

### CIFS/SMB Testing
```bash
# Test CIFS mount
sudo mkdir -p /mnt/test_cifs  
sudo mount -t cifs //10.10.10.28/ShareName /mnt/test_cifs -o username=yourusername,password=yourpassword
ls -la /mnt/test_cifs
sudo umount /mnt/test_cifs
```

## Post-Deployment Configuration

### 1. Configure Network Drives
- Access the web interface: `http://your-server-ip`
- Navigate to "Network Drives" 
- Add your NFS/CIFS servers with proper credentials
- Test connections using the built-in test feature

### 2. Set Up SSL (Production)
```bash
# Install SSL certificate for your domain
sudo certbot --nginx -d yourdomain.com
```

### 3. Configure Email Notifications
- Go to Settings in the web interface
- Configure SMTP settings for job notifications
- Test email configuration

### 4. Create FTP/SFTP Sites
- Add your FTP/SFTP/NFS servers in the "Sites" section
- Configure connection parameters and credentials
- Test connections

### 5. Schedule Transfer Jobs
- Create download/upload jobs with scheduling
- Use job groups for organized file management
- Enable advanced features like recursive download and date-based folders

## Environment Detection

The application automatically detects the deployment environment:

- **Ubuntu Server**: Full network mounting capabilities
- **Container Environment**: Demonstration mode with simulated folders

## File Structure After Deployment

```
/home/ftpmanager/
├── ftpmanager/              # Application directory
│   ├── venv/                # Python virtual environment
│   ├── logs/                # Application logs
│   ├── downloads/           # Downloaded files
│   ├── uploads/             # Upload staging area
│   └── .env                 # Environment configuration
├── backup.sh                # Database backup script
└── restore.sh               # Database restore script

/mnt/
├── network_drives/          # Network drive mount points
├── cifs/                    # CIFS mount points
└── nfs/                     # NFS mount points
```

## Service Management

```bash
# Service control
sudo systemctl start ftpmanager
sudo systemctl stop ftpmanager  
sudo systemctl restart ftpmanager
sudo systemctl status ftpmanager

# View logs
sudo journalctl -u ftpmanager -f
tail -f /home/ftpmanager/ftpmanager/logs/gunicorn.log
```

## Troubleshooting Network Issues

### Check Network Tools
```bash
# Verify all tools are installed
ping -c 1 8.8.8.8
nc -zv your-server 22
showmount -e your-nfs-server
smbclient -L //your-smb-server -U username
```

### Check Mount Permissions
```bash
# Verify sudo permissions
sudo -l | grep mount
cat /etc/sudoers.d/ftpmanager-mount
```

### Check Services
```bash
# Verify NFS services
systemctl status rpcbind
systemctl status nfs-kernel-server

# Check network connectivity
netstat -tuln | grep :2049  # NFS
netstat -tuln | grep :445   # SMB
```

## Security Considerations

1. **Firewall Configuration**: UFW is configured with basic rules
2. **SSH Protection**: Fail2Ban monitors SSH access attempts  
3. **SSL/TLS**: Certbot ready for Let's Encrypt certificates
4. **Database Security**: PostgreSQL with user-specific access
5. **File Permissions**: Proper ownership and permissions on all directories
6. **Network Mounting**: Secure sudo configuration for mount operations

## Support and Documentation

- Configuration Guide: See `DEPLOYMENT_ENVIRONMENTS.md`
- Project Architecture: See `replit.md`
- Network Setup: Refer to deployment script output
- Issue Tracking: Check application logs and system journals

This deployment guide ensures your FTP/SFTP/NFS Manager is properly configured with all necessary network tools and security measures for production use on Ubuntu Server 24.04.