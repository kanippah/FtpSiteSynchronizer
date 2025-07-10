#!/bin/bash

# FTP/SFTP/NFS Manager Deployment Script for Ubuntu 24.04
# This script installs and configures the complete application with Apache, PostgreSQL, and NFS support

set -e  # Exit on any error
exec > >(tee -a deployment.log) 2>&1  # Log all output

# Configuration
APP_NAME="ftpmanager"
APP_USER="ftpmanager"
APP_DIR="/home/$APP_USER/$APP_NAME"
DOMAIN="${DOMAIN:-$(hostname -f)}"
SSL_DIR="/etc/ssl/private"
DB_NAME="ftpmanager"
DB_USER="ftpmanager"
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Use set +e to continue on errors instead of exiting
set +e

print_status "Starting FTP/SFTP/NFS Manager deployment..."
print_status "Domain: $DOMAIN"
print_status "Application Directory: $APP_DIR"

# Step 1: System updates
print_status "Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install required packages
print_status "Installing required packages..."
apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib postgresql-client \
    apache2 apache2-dev \
    supervisor \
    git curl wget unzip \
    build-essential \
    openssl \
    ufw \
    logrotate \
    nfs-kernel-server \
    nfs-common \
    rpcbind

print_success "Required packages installed"

# Step 3: NFS Configuration
print_status "Configuring NFS services..."

# Enable and start NFS services
systemctl enable nfs-kernel-server
systemctl enable rpcbind
systemctl start rpcbind
systemctl start nfs-kernel-server

# Configure NFS exports (empty for client-only setup)
touch /etc/exports
exportfs -a

print_success "NFS services configured and started"

# Step 4: Create application user
print_status "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    print_success "User $APP_USER created"
else
    print_status "User $APP_USER already exists"
fi

# Step 5: Configure sudo permissions for NFS operations
print_status "Configuring sudo permissions for NFS operations..."
echo "$APP_USER ALL=(ALL) NOPASSWD: /bin/mount, /bin/umount, /usr/bin/showmount" > /etc/sudoers.d/$APP_USER
chmod 440 /etc/sudoers.d/$APP_USER

print_success "Sudo permissions configured for NFS operations"

# Step 6: PostgreSQL setup
print_status "Configuring PostgreSQL..."
sudo -u postgres createuser --no-createdb --no-createrole --no-superuser $DB_USER 2>/dev/null || print_warning "User may already exist"
sudo -u postgres createdb --owner=$DB_USER $DB_NAME 2>/dev/null || print_warning "Database may already exist"
sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';" || print_warning "Password update failed"

print_success "PostgreSQL configured"

# Step 7: Application setup
print_status "Setting up application..."
mkdir -p $APP_DIR
cd $APP_DIR

# Copy application files (assuming they're in current directory)
if [ -f "../app.py" ]; then
    cp ../*.py ./ 2>/dev/null || true
    cp -r ../templates ./ 2>/dev/null || true
    cp -r ../static ./ 2>/dev/null || true
    cp ../pyproject.toml ./ 2>/dev/null || true
    cp ../uv.lock ./ 2>/dev/null || true
fi

# Create directories
mkdir -p logs downloads uploads backups

# Create Python virtual environment
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip"

# Install dependencies
if [ -f "pyproject.toml" ]; then
    sudo -u $APP_USER bash -c "source venv/bin/activate && pip install -e ."
else
    sudo -u $APP_USER bash -c "source venv/bin/activate && pip install flask flask-sqlalchemy apscheduler cryptography paramiko psycopg2-binary gunicorn"
fi

print_success "Application setup completed"

# Step 8: Environment configuration
print_status "Creating environment configuration..."
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
ENCRYPTION_PASSWORD=$(openssl rand -base64 16)
FLASK_ENV=production
FLASK_APP=main.py
EOF

print_success "Environment configuration created"

# Step 9: SSL certificate generation
print_status "Generating SSL certificate..."
mkdir -p $SSL_DIR
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $SSL_DIR/ftpmanager.key \
    -out $SSL_DIR/ftpmanager.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"

chmod 600 $SSL_DIR/ftpmanager.key
chmod 644 $SSL_DIR/ftpmanager.crt

print_success "Self-signed SSL certificate created"

# Step 10: Supervisor configuration
print_status "Configuring Supervisor..."
tee /etc/supervisor/conf.d/ftpmanager.conf > /dev/null <<EOF
[program:ftpmanager]
command=$APP_DIR/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 3 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 --access-logfile $APP_DIR/logs/gunicorn_access.log --error-logfile $APP_DIR/logs/gunicorn.log --log-level info main:app
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/supervisor.log
environment=PATH="$APP_DIR/venv/bin",DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME",SESSION_SECRET="$(openssl rand -base64 32)",ENCRYPTION_KEY="$(openssl rand -base64 32)",ENCRYPTION_PASSWORD="$(openssl rand -base64 16)"
EOF

supervisorctl reread || print_warning "Supervisor configuration failed, continuing..."
supervisorctl update
sleep 2
supervisorctl start ftpmanager || print_warning "Could not start ftpmanager service"

# Wait a moment and check status
sleep 3
SUPERVISOR_STATUS=$(supervisorctl status ftpmanager)
if echo "$SUPERVISOR_STATUS" | grep -q "RUNNING"; then
    print_success "Supervisor configured and application started successfully"
else
    print_warning "Supervisor configured but application may not be running properly"
    echo "Status: $SUPERVISOR_STATUS"
    print_status "Checking logs for errors..."
    tail -20 $APP_DIR/logs/gunicorn.log 2>/dev/null || echo "No logs available"
fi

# Step 11: Apache configuration with SSL
print_status "Configuring Apache with SSL..."

# Enable required Apache modules
a2enmod ssl
a2enmod proxy
a2enmod proxy_http
a2enmod headers
a2enmod rewrite
a2enmod expires

# Create Apache virtual host configuration
tee /etc/apache2/sites-available/ftpmanager.conf > /dev/null <<EOF
# Redirect HTTP to HTTPS
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot $APP_DIR/static
    
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
</VirtualHost>

# HTTPS Virtual Host
<VirtualHost *:443>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot $APP_DIR/static

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile $SSL_DIR/ftpmanager.crt
    SSLCertificateKeyFile $SSL_DIR/ftpmanager.key
    
    # Modern SSL configuration
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
    SSLHonorCipherOrder off
    SSLSessionTickets off
    
    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"

    # File upload size limit (100MB)
    LimitRequestBody 104857600

    # Proxy configuration for Flask application
    ProxyPreserveHost On
    ProxyRequests Off
    
    ProxyPass /static/ !
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    
    # Set proxy headers
    ProxyPassReverse / http://127.0.0.1:5000/
    ProxyPreserveHost On
    ProxyAddHeaders On
    
    # Static files
    Alias /static $APP_DIR/static
    <Directory "$APP_DIR/static">
        Require all granted
        ExpiresActive On
        ExpiresDefault "access plus 1 year"
    </Directory>
    
    # Logs
    ErrorLog \${APACHE_LOG_DIR}/ftpmanager_error.log
    CustomLog \${APACHE_LOG_DIR}/ftpmanager_access.log combined
</VirtualHost>
EOF

# Disable default Apache site and enable our site
a2dissite 000-default
a2ensite ftpmanager

# Test Apache configuration
apache2ctl configtest || print_warning "Apache configuration test failed"

# Restart Apache
systemctl restart apache2
systemctl enable apache2

print_success "Apache configured with SSL"

# Step 12: Firewall configuration
print_status "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Apache Full'
ufw --force enable

print_success "Firewall configured"

# Step 13: Log rotation
print_status "Setting up log rotation..."
tee /etc/logrotate.d/ftpmanager > /dev/null <<EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        supervisorctl restart ftpmanager
    endscript
}
EOF

print_success "Log rotation configured"

# Step 14: Backup script
print_status "Creating backup script..."
tee /home/$APP_USER/backup.sh > /dev/null <<EOF
#!/bin/bash
BACKUP_DIR="/home/$APP_USER/backups"
DATE=\$(date +%Y%m%d_%H%M%S)

mkdir -p \$BACKUP_DIR

# Database backup
PGPASSWORD="$DB_PASSWORD" pg_dump -U $DB_USER -h localhost $DB_NAME > \$BACKUP_DIR/${DB_NAME}_\$DATE.sql

# Application backup
tar -czf \$BACKUP_DIR/${APP_NAME}_\$DATE.tar.gz $APP_DIR --exclude=venv --exclude=logs

# Keep only last 7 days of backups
find \$BACKUP_DIR -name "*.sql" -mtime +7 -delete
find \$BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: \$DATE"
EOF

chmod +x /home/$APP_USER/backup.sh
chown $APP_USER:$APP_USER /home/$APP_USER/backup.sh

# Add daily backup to crontab
echo "0 2 * * * /home/$APP_USER/backup.sh >> /home/$APP_USER/backup.log 2>&1" | crontab -u $APP_USER -

print_success "Backup script created and scheduled"

# Step 15: Set proper permissions
print_status "Setting file permissions..."
chown -R $APP_USER:www-data $APP_DIR
chmod -R 750 $APP_DIR
chmod 600 $APP_DIR/.env

# Fix Apache static file access permissions
print_status "Configuring Apache static file permissions..."
chmod 755 /home/$APP_USER
chmod 755 $APP_DIR
chmod 755 $APP_DIR/static
chmod 755 $APP_DIR/static/css 2>/dev/null || true
chmod 755 $APP_DIR/static/js 2>/dev/null || true
chmod 644 $APP_DIR/static/css/*.css 2>/dev/null || true
chmod 644 $APP_DIR/static/js/*.js 2>/dev/null || true

print_success "File permissions set"

# Step 16: Final verification
print_status "Performing final verification..."
sleep 5

# Check services
SUPERVISOR_STATUS=$(supervisorctl status ftpmanager 2>/dev/null || echo "Not running")
APACHE_STATUS=$(systemctl is-active apache2 2>/dev/null || echo "inactive")
POSTGRES_STATUS=$(systemctl is-active postgresql 2>/dev/null || echo "inactive")
NFS_STATUS=$(systemctl is-active nfs-kernel-server 2>/dev/null || echo "inactive")
RPCBIND_STATUS=$(systemctl is-active rpcbind 2>/dev/null || echo "inactive")

print_status "Service Status Check:"
echo "  - Supervisor (ftpmanager): $SUPERVISOR_STATUS"
echo "  - Apache: $APACHE_STATUS"
echo "  - PostgreSQL: $POSTGRES_STATUS"
echo "  - NFS Server: $NFS_STATUS"
echo "  - RPC Bind: $RPCBIND_STATUS"

# Test HTTP response
HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://localhost 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" =~ ^(200|302|301)$ ]]; then
    print_success "Application is responding to HTTPS requests (HTTP $HTTP_CODE)"
else
    print_warning "Application may not be responding correctly (HTTP $HTTP_CODE)"
    print_status "Checking application logs..."
    tail -10 $APP_DIR/logs/gunicorn.log 2>/dev/null || echo "No logs available yet"
fi

# Final NFS verification
print_status "Performing final NFS verification..."
sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && python3 -c \"
import sys
sys.path.append('.')
from nfs_client import NFSClient

# Test NFS client initialization
try:
    client = NFSClient('127.0.0.1', '/test', '4', '', 'sys')
    status = client._check_nfs_support()
    if status:
        print('✓ NFS support verification successful')
    else:
        print('⚠ NFS support verification failed - check logs for details')
except Exception as e:
    print(f'⚠ NFS client test failed: {e}')
\"" 2>/dev/null || print_warning "NFS verification script failed"

# Create management scripts
print_status "Creating management scripts..."
cat > /usr/local/bin/ftpmanager-status << 'EOFSTATUS'
#!/bin/bash
echo "=== FTP/SFTP/NFS Manager Status ==="
echo "Application: $(supervisorctl status ftpmanager 2>/dev/null || echo 'Not running')"
echo "Apache: $(systemctl is-active apache2 2>/dev/null || echo 'inactive')"
echo "PostgreSQL: $(systemctl is-active postgresql 2>/dev/null || echo 'inactive')"
echo "NFS Server: $(systemctl is-active nfs-kernel-server 2>/dev/null || echo 'inactive')"
echo "RPC Bind: $(systemctl is-active rpcbind 2>/dev/null || echo 'inactive')"
echo "Disk Usage: $(df -h /home/ftpmanager/ftpmanager 2>/dev/null | tail -1 || echo 'N/A')"
echo "Last Backup: $(ls -la /home/ftpmanager/backups/ 2>/dev/null | tail -1 || echo 'No backups found')"
echo "Recent Logs:"
tail -5 /home/ftpmanager/ftpmanager/logs/gunicorn.log 2>/dev/null || echo "No logs available"
echo "==========================="
EOFSTATUS

chmod +x /usr/local/bin/ftpmanager-status

cat > /usr/local/bin/ftpmanager-restart << 'EOFRESTART'
#!/bin/bash
echo "Restarting FTP/SFTP/NFS Manager..."
supervisorctl restart ftpmanager
sleep 3
supervisorctl status ftpmanager
EOFRESTART

chmod +x /usr/local/bin/ftpmanager-restart

# Display final information
print_success "=== DEPLOYMENT COMPLETED ==="
echo ""
echo "Application Details:"
echo "  - URL: https://$DOMAIN"
echo "  - Application User: $APP_USER"
echo "  - Application Directory: $APP_DIR"
echo "  - Database: $DB_NAME"
echo "  - SSL Certificate: Self-signed (valid for 365 days)"
echo ""
echo "Important Files:"
echo "  - Environment Config: $APP_DIR/.env"
echo "  - Application Logs: $APP_DIR/logs/gunicorn.log"
echo "  - Apache Config: /etc/apache2/sites-available/ftpmanager.conf"
echo "  - Supervisor Config: /etc/supervisor/conf.d/ftpmanager.conf"
echo ""
echo "Management Commands:"
echo "  - Check Status: ftpmanager-status"
echo "  - Restart App: ftpmanager-restart (or supervisorctl restart ftpmanager)"
echo "  - View Logs: tail -f $APP_DIR/logs/gunicorn.log"
echo "  - Manual Backup: /home/$APP_USER/backup.sh"
echo ""
echo "Protocol Support:"
echo "  - FTP: Standard File Transfer Protocol"
echo "  - SFTP: SSH File Transfer Protocol"
echo "  - NFS: Network File System (v3, v4, v4.1, v4.2)"
echo ""
echo "NFS Configuration:"
echo "  - NFS Services: Enabled and running"
echo "  - Sudo Permissions: Configured for mount/umount operations"
echo "  - Temporary Mounts: /tmp/nfs_* (auto-cleanup enabled)"
echo "  - Supported Auth: AUTH_SYS, Kerberos v5 (krb5, krb5i, krb5p)"
echo ""
echo "Database Credentials:"
echo "  - Database: $DB_NAME"
echo "  - Username: $DB_USER"
echo "  - Password: $DB_PASSWORD"
echo ""
print_warning "IMPORTANT: Save the database password above!"
print_warning "Browser will show SSL warning due to self-signed certificate"
print_warning "For NFS operations, ensure target servers have proper export configurations"
echo ""
print_success "Access your FTP/SFTP/NFS Manager at: https://$DOMAIN"
echo ""