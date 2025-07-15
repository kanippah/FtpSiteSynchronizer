# Network Drive Troubleshooting Guide

## Common Permission Issues and Solutions

### Issue 1: "Permission denied" when downloading to network drives

**Symptoms:**
- Job fails with "Permission denied: Cannot create directory /mnt/drive_name/..."
- Error mentions uid/gid permission problems

**Solutions:**

1. **Check Mount Options**
   ```bash
   # Verify current mount options
   mount | grep /mnt/your_drive_name
   
   # Should include uid=1000,gid=1000 for proper permissions
   ```

2. **Proper CIFS Mount Options**
   - Use: `uid=1000,gid=1000,file_mode=0666,dir_mode=0777,iocharset=utf8`
   - For older servers add: `vers=2.0` or `vers=1.0`

3. **Proper NFS Mount Options**
   - Use: `vers=4,rsize=8192,wsize=8192,uid=1000,gid=1000`
   - For older servers: `vers=3,nolock`

### Issue 2: "Network drive not found" errors

**Symptoms:**
- Jobs fail with "Network drive not found for path /mnt/..."
- System can't match job path to configured drives

**Solutions:**

1. **Configure Network Drive First**
   - Go to Network Drives section
   - Create drive with exact mount point path
   - Test connection before using in jobs

2. **Path Matching**
   - Job local path: `/mnt/company_share/downloads`
   - Network drive mount point: `/mnt/company_share`
   - ✓ Path matches correctly

### Issue 3: Drive not mounting automatically

**Symptoms:**
- Manual mount works but jobs fail
- Drive shows as "not mounted" in interface

**Solutions:**

1. **Auto-mount Configuration**
   - Enable "Auto Mount" in network drive settings
   - System will mount before each job execution

2. **Mount Status Check**
   - Use "Test Connection" to verify mounting
   - Check system logs for mount errors

### Issue 4: Environment lacks network utilities

**Symptoms:**
- Error: "mount.cifs utility not found"
- Error: "NFS utilities not found"

**Solutions:**

1. **Install Required Utilities (Ubuntu/Debian)**
   ```bash
   # For CIFS/SMB support
   sudo apt install cifs-utils samba-common-bin
   
   # For NFS support
   sudo apt install nfs-common
   ```

2. **Use Deployment Script**
   ```bash
   ./deploy_network_drives.sh
   ```

### Issue 5: Sudo permission errors

**Symptoms:**
- Error: "Mount failed: Operation not permitted"
- Cannot create mount points

**Solutions:**

1. **Configure Sudo Permissions**
   ```bash
   # Add to /etc/sudoers.d/network-drives
   runner ALL=(ALL) NOPASSWD: /bin/mount
   runner ALL=(ALL) NOPASSWD: /bin/umount
   runner ALL=(ALL) NOPASSWD: /bin/mkdir -p /mnt/*
   ```

## Deployment Checklist

### Before Deploying to Production:

1. **Install Network Utilities**
   ```bash
   ./deploy_network_drives.sh
   ```

2. **Test Network Connectivity**
   ```bash
   # Test CIFS server
   smbclient -L //server_ip -U username
   
   # Test NFS server
   showmount -e server_ip
   ```

3. **Configure Network Drives**
   - Create drives in web interface
   - Test connections
   - Verify mount permissions

4. **Update Job Paths**
   - Change local paths from `./downloads` to `/mnt/drive_name/path`
   - Test with simple jobs first

5. **Monitor Logs**
   - Check job logs for permission errors
   - Verify file transfers complete successfully

## Environment Differences

### Replit Environment (Current)
- Limited network mounting capabilities
- Demo mode for network drives
- All jobs use local `./downloads` paths

### Production Ubuntu Server
- Full CIFS/NFS mounting support
- Real network drive integration
- Jobs can use `/mnt/` paths

## Testing Network Drive Setup

1. **Create Test Drive**
   - Name: "Test Network Drive"
   - Type: CIFS or NFS
   - Server Path: Your network share
   - Mount Point: `/mnt/test_drive`

2. **Test Connection**
   - Use "Test Connection" button
   - Should show "Server reachable" message

3. **Create Test Job**
   - Set local path: `/mnt/test_drive/downloads`
   - Run job and check logs

4. **Verify Results**
   - Files should appear in network share
   - No permission errors in logs