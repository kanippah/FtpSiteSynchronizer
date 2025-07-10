#!/bin/bash

# FTP/SFTP/NFS Manager - Ubuntu 24.04 Deployment Script
# This script deploys the application on a fresh Ubuntu 24.04 server

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
APP_NAME="ftpmanager"
APP_USER="ftpmanager"
APP_DIR="/home/$APP_USER/$APP_NAME"
DB_NAME="ftpmanager_db"
DB_USER="ftpmanager_user"
DOMAIN="localhost"  # Change this to your domain
GITHUB_REPO=""  # Will be prompted

# Function to print colored output
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

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Function to generate Fernet encryption key (will install cryptography if needed)
generate_fernet_key() {
    # Install cryptography if not available
    if ! python3 -c "import cryptography" 2>/dev/null; then
        pip3 install --break-system-packages cryptography
    fi
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run this script as root (use sudo)"
    exit 1
fi

print_status "Starting FTP/SFTP/NFS Manager deployment on Ubuntu 24.04"

# Get GitHub repository URL
if [ -z "$GITHUB_REPO" ]; then
    echo -n "Enter GitHub repository URL: "
    read GITHUB_REPO
    if [ -z "$GITHUB_REPO" ]; then
        print_error "GitHub repository URL is required"
        exit 1
    fi
fi

# Generate secure passwords and keys
print_status "Generating secure credentials..."
DB_PASSWORD=$(generate_password)
SESSION_SECRET=$(openssl rand -base64 64 | tr -d "=+/\n" | cut -c1-50)
ENCRYPTION_KEY=$(generate_fernet_key)
ENCRYPTION_PASSWORD=$(generate_password)

# Validate Fernet key format
if [ ${#ENCRYPTION_KEY} -ne 44 ]; then
    print_error "Invalid Fernet key generated. Expected 44 characters, got ${#ENCRYPTION_KEY}"
    exit 1
fi

print_success "Generated secure passwords for database and application"
print_status "Encryption key length: ${#ENCRYPTION_KEY} characters"

# Step 1: System updates and basic packages
print_status "Updating system packages..."
apt update && apt upgrade -y

print_status "Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    apache2 \
    supervisor \
    curl \
    wget \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    openssl \
    postgresql \
    postgresql-contrib \
    postgresql-server-dev-all \
    libpq-dev \
    cron \
    nfs-common \
    nfs-kernel-server \
    rpcbind \
    sudo

print_success "System dependencies installed"

# Configure NFS services
print_status "Configuring NFS services..."
systemctl enable rpcbind
systemctl enable nfs-kernel-server
systemctl start rpcbind
systemctl start nfs-kernel-server

# Add application user to sudo group for NFS mount operations
usermod -aG sudo $APP_USER || true  # Don't fail if user doesn't exist yet

print_success "NFS services configured"

# Step 2: PostgreSQL setup
print_status "Configuring PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
\q
EOF

# Connect to the specific database and grant comprehensive schema permissions
sudo -u postgres psql -d $DB_NAME <<EOF
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $DB_USER;
\q
EOF

print_success "PostgreSQL configured with database: $DB_NAME"

# Step 3: Create application user
print_status "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    usermod -aG www-data $APP_USER
    usermod -aG sudo $APP_USER
    print_success "User $APP_USER created"
else
    print_warning "User $APP_USER already exists"
    usermod -aG www-data $APP_USER
    usermod -aG sudo $APP_USER
fi

# Configure sudo permissions for NFS operations
print_status "Configuring sudo permissions for NFS operations..."
cat > /etc/sudoers.d/ftpmanager-nfs << EOF
# Allow ftpmanager user to mount/unmount NFS shares without password
$APP_USER ALL=(ALL) NOPASSWD: /bin/mount
$APP_USER ALL=(ALL) NOPASSWD: /bin/umount
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/mount
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/umount
$APP_USER ALL=(ALL) NOPASSWD: /sbin/mount.nfs
$APP_USER ALL=(ALL) NOPASSWD: /sbin/mount.nfs4
$APP_USER ALL=(ALL) NOPASSWD: /sbin/umount.nfs
$APP_USER ALL=(ALL) NOPASSWD: /sbin/umount.nfs4
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/mount.nfs
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/mount.nfs4
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/umount.nfs
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/umount.nfs4
$APP_USER ALL=(ALL) NOPASSWD: /bin/mkdir -p /tmp/nfs_*
$APP_USER ALL=(ALL) NOPASSWD: /bin/rmdir /tmp/nfs_*
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/showmount
$APP_USER ALL=(ALL) NOPASSWD: /sbin/showmount
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/showmount
EOF

chmod 440 /etc/sudoers.d/ftpmanager-nfs

# Test sudo configuration
print_status "Testing NFS sudo configuration..."
sudo -u $APP_USER sudo -n mount --help >/dev/null 2>&1
if [ $? -eq 0 ]; then
    print_success "Sudo permissions configured for NFS operations"
else
    print_warning "Sudo permissions may not be working correctly"
fi

# Test NFS utilities availability
print_status "Checking NFS client utilities..."
for util in mount.nfs mount.nfs4 showmount; do
    if which $util >/dev/null 2>&1; then
        print_status "  ✓ $util found at $(which $util)"
    else
        print_warning "  ✗ $util not found"
    fi
done

# Step 4: Setup application directory and clone repository
print_status "Setting up application directory..."
sudo -u $APP_USER mkdir -p $APP_DIR
cd $APP_DIR

print_status "Cloning repository from GitHub..."
sudo -u $APP_USER git clone $GITHUB_REPO .

# Create required directories
sudo -u $APP_USER mkdir -p logs downloads static/uploads
sudo -u $APP_USER chmod 755 logs downloads static/uploads

print_success "Repository cloned and directories created"

# Step 5: Python virtual environment and dependencies
print_status "Setting up Python virtual environment..."
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip"

print_status "Installing Python dependencies..."
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install \
    flask \
    flask-sqlalchemy \
    gunicorn \
    psycopg2-binary \
    apscheduler \
    cryptography \
    paramiko \
    pytz \
    werkzeug \
    email-validator"

print_success "Python environment configured"

# Step 6: Environment configuration
print_status "Creating environment configuration..."
# Create .env file using printf to properly handle special characters
sudo -u $APP_USER bash -c "
cat > $APP_DIR/.env << 'ENVEOF'
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$SESSION_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENCRYPTION_PASSWORD=$ENCRYPTION_PASSWORD
FLASK_ENV=production
ENVEOF
"

sudo -u $APP_USER chmod 600 $APP_DIR/.env
print_success "Environment configuration created"

# Step 7: Initialize database
print_status "Initializing application database..."
# Test database connection first
sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && python3 -c \"
import psycopg2
import os
os.environ['DATABASE_URL'] = 'postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME'
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('Database connection test successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
\""

# Initialize database tables
sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && python3 -c \"
import os
os.environ['DATABASE_URL'] = 'postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME'
os.environ['SESSION_SECRET'] = '''$SESSION_SECRET'''
os.environ['ENCRYPTION_KEY'] = '''$ENCRYPTION_KEY'''
os.environ['ENCRYPTION_PASSWORD'] = '''$ENCRYPTION_PASSWORD'''
os.environ['FLASK_ENV'] = 'production'

from main import app
from models import db
with app.app_context():
    try:
        db.create_all()
        print('Database initialized successfully')
    except Exception as e:
        print(f'Database initialization failed: {e}')
        exit(1)
\""

print_success "Database initialized"

# Step 8: Create self-signed SSL certificate
print_status "Creating self-signed SSL certificate..."
SSL_DIR="/etc/ssl/certs/ftpmanager"
mkdir -p $SSL_DIR

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $SSL_DIR/ftpmanager.key \
    -out $SSL_DIR/ftpmanager.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$DOMAIN"

chmod 600 $SSL_DIR/ftpmanager.key
chmod 644 $SSL_DIR/ftpmanager.crt

print_success "Self-signed SSL certificate created"

# Step 9: Supervisor configuration
print_status "Configuring Supervisor..."
# Ensure supervisor directories exist
mkdir -p /etc/supervisor/conf.d
mkdir -p /var/log/supervisor

# Start supervisor service
systemctl start supervisor
systemctl enable supervisor

# Create supervisor configuration using printf to avoid quote issues
printf '[program:ftpmanager]\n' > /etc/supervisor/conf.d/ftpmanager.conf
printf 'command=%s/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 main:app\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'directory=%s\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'user=%s\n' "$APP_USER" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'autostart=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'autorestart=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'redirect_stderr=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'stdout_logfile=%s/logs/gunicorn.log\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'environment=DATABASE_URL="postgresql://%s:%s@localhost/%s",SESSION_SECRET="%s",ENCRYPTION_KEY="%s",ENCRYPTION_PASSWORD="%s",FLASK_ENV="production"\n' "$DB_USER" "$DB_PASSWORD" "$DB_NAME" "$SESSION_SECRET" "$ENCRYPTION_KEY" "$ENCRYPTION_PASSWORD" >> /etc/supervisor/conf.d/ftpmanager.conf

# Update supervisor and start application
print_status "Starting supervisor services..."
supervisorctl reread
if [ $? -ne 0 ]; then
    print_error "Supervisor configuration error. Checking config file..."
    cat /etc/supervisor/conf.d/ftpmanager.conf
    exit 1
fi

supervisorctl update
sleep 2
supervisorctl start ftpmanager

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

# Step 10: Apache configuration with SSL
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
apache2ctl configtest

# Restart Apache
systemctl restart apache2
systemctl enable apache2

print_success "Apache configured with SSL"

# Step 11: Firewall configuration
print_status "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Apache Full'
ufw --force enable

print_success "Firewall configured"

# Step 12: Log rotation
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

# Step 13: Backup script
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

# Step 14: Set proper permissions
print_status "Setting file permissions..."
chown -R $APP_USER:www-data $APP_DIR
chmod -R 750 $APP_DIR
chmod 600 $APP_DIR/.env

# Fix Apache static file access permissions
print_status "Configuring Apache static file permissions..."
chmod 755 /home/$APP_USER
chmod 755 $APP_DIR
chmod 755 $APP_DIR/static
chmod 755 $APP_DIR/static/css
chmod 755 $APP_DIR/static/js
chmod 644 $APP_DIR/static/css/*.css
chmod 644 $APP_DIR/static/js/*.js

print_success "File permissions set"

# Step 15: Create backup script
print_status "Setting up backup script..."

# Final verification
print_status "Performing final verification..."
sleep 5

# Check services
SUPERVISOR_STATUS=$(supervisorctl status ftpmanager)
APACHE_STATUS=$(systemctl is-active apache2)
POSTGRES_STATUS=$(systemctl is-active postgresql)
NFS_STATUS=$(systemctl is-active nfs-kernel-server)
RPCBIND_STATUS=$(systemctl is-active rpcbind)

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
    tail -10 $APP_DIR/logs/gunicorn.log || echo "No logs available yet"
fi

# Create management scripts with proper escaping
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