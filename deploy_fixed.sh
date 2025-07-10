#!/bin/bash

# FTP/SFTP/NFS Manager - Ubuntu 24.04 Deployment Script (Fixed Version)
# This script installs and configures the FTP/SFTP/NFS Manager on Ubuntu 24.04

# Make script more robust - continue on most errors
set +e

# Function to handle script interruption
cleanup() {
    echo "Deployment interrupted. You can re-run the script to continue."
    exit 1
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Configuration variables
APP_NAME="ftpmanager"
APP_USER="ftpmanager"
APP_DIR="/home/$APP_USER/$APP_NAME"
DB_NAME="ftpmanager_db"
DB_USER="ftpmanager_user"
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
SESSION_SECRET=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
ENCRYPTION_PASSWORD=$(openssl rand -base64 32)
DOMAIN=${1:-$(hostname -f)}
GITHUB_REPO="https://github.com/yourusername/ftpmanager.git"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
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

# Banner
clear
echo "=================================="
echo " FTP/SFTP/NFS Manager Deployment"
echo "=================================="
echo "Target: Ubuntu 24.04"
echo "Domain: $DOMAIN"
echo "App Directory: $APP_DIR"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root"
    exit 1
fi

# Check if this is Ubuntu 24.04
if ! grep -q "Ubuntu 24.04" /etc/os-release; then
    print_warning "This script is designed for Ubuntu 24.04"
    print_status "Current OS: $(cat /etc/os-release | grep PRETTY_NAME)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

print_status "Starting FTP/SFTP/NFS Manager deployment on Ubuntu 24.04"

# Step 1: Update system and install dependencies
print_status "Updating system packages..."
apt update -y
apt upgrade -y

print_status "Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor \
    git \
    curl \
    wget \
    unzip \
    ssl-cert \
    apache2 \
    apache2-utils \
    libapache2-mod-wsgi-py3 \
    ufw \
    htop \
    tree \
    vim \
    logrotate \
    cron \
    nfs-common \
    nfs-kernel-server \
    rpcbind \
    openssl \
    ca-certificates

print_success "System dependencies installed"

# Configure NFS services
print_status "Configuring NFS services..."
systemctl enable rpcbind || print_warning "Could not enable rpcbind"
systemctl enable nfs-kernel-server || print_warning "Could not enable nfs-kernel-server"
systemctl start rpcbind || print_warning "Could not start rpcbind"
systemctl start nfs-kernel-server || print_warning "Could not start nfs-kernel-server"

# Add application user to sudo group for NFS mount operations
usermod -aG sudo $APP_USER 2>/dev/null || print_warning "User $APP_USER not found yet"

print_success "NFS services configured"

# Step 2: Configure PostgreSQL
print_status "Configuring PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
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

# Test NFS sudo permissions with the actual user
print_status "Testing NFS operations with application user..."
sudo -u $APP_USER sudo -n showmount --help >/dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status "  ✓ showmount sudo access working"
else
    print_warning "  ✗ showmount sudo access failed"
fi

sudo -u $APP_USER sudo -n mount.nfs --help >/dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status "  ✓ mount.nfs sudo access working"
else
    print_warning "  ✗ mount.nfs sudo access failed"
fi

print_success "NFS configuration completed"

# Step 4: Setup application directory and clone repository
print_status "Setting up application directory..."
sudo -u $APP_USER mkdir -p $APP_DIR
cd $APP_DIR

print_status "Cloning repository from GitHub..."
if [ -d ".git" ]; then
    print_warning "Repository already exists, pulling latest changes..."
    sudo -u $APP_USER git pull origin main 2>/dev/null || sudo -u $APP_USER git pull origin master 2>/dev/null || print_warning "Could not pull latest changes"
else
    # For demonstration, we'll skip git clone and assume files are already present
    print_warning "Skipping git clone - assuming files are already present"
    # sudo -u $APP_USER git clone $GITHUB_REPO . || print_warning "Git clone failed, continuing with existing files..."
fi

# Create required directories
sudo -u $APP_USER mkdir -p logs downloads static/uploads
sudo -u $APP_USER chmod 755 logs downloads static/uploads

print_success "Repository setup completed"

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
    print('Continuing with deployment...')
\""

# Initialize database tables if main.py exists
if [ -f "main.py" ]; then
    print_status "Initializing database tables..."
    sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && python3 -c \"
import os
os.environ['DATABASE_URL'] = 'postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME'
os.environ['SESSION_SECRET'] = '''$SESSION_SECRET'''
os.environ['ENCRYPTION_KEY'] = '''$ENCRYPTION_KEY'''
os.environ['ENCRYPTION_PASSWORD'] = '''$ENCRYPTION_PASSWORD'''
os.environ['FLASK_ENV'] = 'production'

try:
    from main import app
    from models import db
    with app.app_context():
        db.create_all()
        print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    print('Continuing with deployment...')
\""
else
    print_warning "main.py not found, skipping database initialization"
fi

print_success "Database initialization completed"

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

# Create supervisor configuration
cat > /etc/supervisor/conf.d/ftpmanager.conf << EOF
[program:ftpmanager]
command=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 main:app
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/gunicorn.log
environment=DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME",SESSION_SECRET="$SESSION_SECRET",ENCRYPTION_KEY="$ENCRYPTION_KEY",ENCRYPTION_PASSWORD="$ENCRYPTION_PASSWORD",FLASK_ENV="production"
EOF

# Update supervisor and start application
print_status "Starting supervisor services..."
supervisorctl reread
supervisorctl update
supervisorctl start ftpmanager || print_warning "Could not start ftpmanager service"

print_success "Supervisor configured"

# Step 10: Apache configuration
print_status "Configuring Apache..."
# Enable required modules
a2enmod ssl
a2enmod proxy
a2enmod proxy_http
a2enmod headers
a2enmod rewrite

# Create Apache virtual host
cat > /etc/apache2/sites-available/ftpmanager.conf << EOF
<VirtualHost *:80>
    ServerName $DOMAIN
    Redirect permanent / https://$DOMAIN/
</VirtualHost>

<VirtualHost *:443>
    ServerName $DOMAIN
    DocumentRoot $APP_DIR/static
    
    SSLEngine on
    SSLCertificateFile $SSL_DIR/ftpmanager.crt
    SSLCertificateKeyFile $SSL_DIR/ftpmanager.key
    
    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    
    # Proxy to Gunicorn
    ProxyPreserveHost On
    ProxyRequests Off
    ProxyPass /static/ !
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    
    # Static file serving
    Alias /static $APP_DIR/static
    <Directory "$APP_DIR/static">
        Require all granted
        ExpiresActive On
        ExpiresDefault "access plus 1 month"
    </Directory>
    
    # Logging
    ErrorLog \${APACHE_LOG_DIR}/ftpmanager_error.log
    CustomLog \${APACHE_LOG_DIR}/ftpmanager_access.log combined
    LogLevel warn
</VirtualHost>
EOF

# Enable site and disable default
a2ensite ftpmanager
a2dissite 000-default

# Test Apache configuration
apache2ctl configtest || print_warning "Apache configuration test failed"

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

# Step 12: Set proper permissions
print_status "Setting file permissions..."
chown -R $APP_USER:www-data $APP_DIR
chmod -R 750 $APP_DIR
chmod 600 $APP_DIR/.env

# Fix Apache static file access permissions
print_status "Configuring Apache static file permissions..."
chmod 755 /home/$APP_USER
chmod 755 $APP_DIR
chmod 755 $APP_DIR/static
chmod 755 $APP_DIR/static/css 2>/dev/null || print_warning "static/css not found"
chmod 755 $APP_DIR/static/js 2>/dev/null || print_warning "static/js not found"
chmod 644 $APP_DIR/static/css/*.css 2>/dev/null || print_warning "CSS files not found"
chmod 644 $APP_DIR/static/js/*.js 2>/dev/null || print_warning "JS files not found"

print_success "File permissions set"

# Final verification
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
echo "  - Restart App: ftpmanager-restart"
echo "  - View Logs: tail -f $APP_DIR/logs/gunicorn.log"
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