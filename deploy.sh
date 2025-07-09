#!/bin/bash

# FTP/SFTP Manager - Ubuntu 24.04 Deployment Script
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

# Function to generate Fernet encryption key
generate_fernet_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run this script as root (use sudo)"
    exit 1
fi

print_status "Starting FTP/SFTP Manager deployment on Ubuntu 24.04"

# Get GitHub repository URL
if [ -z "$GITHUB_REPO" ]; then
    echo -n "Enter GitHub repository URL: "
    read GITHUB_REPO
    if [ -z "$GITHUB_REPO" ]; then
        print_error "GitHub repository URL is required"
        exit 1
    fi
fi

# Generate secure passwords
DB_PASSWORD=$(generate_password)
SESSION_SECRET=$(generate_password)$(generate_password)
ENCRYPTION_KEY=$(generate_fernet_key)
ENCRYPTION_PASSWORD=$(generate_password)

print_status "Generated secure passwords for database and application"

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
    nginx \
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
    libpq-dev

# Install cryptography for key generation
pip3 install cryptography

print_success "System dependencies installed"

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

# Connect to the specific database and grant schema permissions
sudo -u postgres psql -d $DB_NAME <<EOF
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
\q
EOF

print_success "PostgreSQL configured with database: $DB_NAME"

# Step 3: Create application user
print_status "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    usermod -aG www-data $APP_USER
    print_success "User $APP_USER created"
else
    print_warning "User $APP_USER already exists"
fi

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
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$SESSION_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENCRYPTION_PASSWORD=$ENCRYPTION_PASSWORD
FLASK_ENV=production
EOF

sudo -u $APP_USER chmod 600 $APP_DIR/.env
print_success "Environment configuration created"

# Step 7: Initialize database
print_status "Initializing application database..."
sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && export \$(cat .env | xargs) && python3 -c \"
from main import app
from models import db
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
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
tee /etc/supervisor/conf.d/ftpmanager.conf > /dev/null <<EOF
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

supervisorctl reread
supervisorctl update
supervisorctl start ftpmanager

print_success "Supervisor configured and application started"

# Step 10: Nginx configuration with SSL
print_status "Configuring Nginx with SSL..."
tee /etc/nginx/sites-available/ftpmanager > /dev/null <<EOF
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL Configuration
    ssl_certificate $SSL_DIR/ftpmanager.crt;
    ssl_certificate_key $SSL_DIR/ftpmanager.key;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Remove default nginx site and enable our site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/ftpmanager /etc/nginx/sites-enabled/

# Test nginx configuration
nginx -t

# Restart nginx
systemctl restart nginx
systemctl enable nginx

print_success "Nginx configured with SSL"

# Step 11: Firewall configuration
print_status "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
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

print_success "File permissions set"

# Step 15: Create status check script
print_status "Creating status check script..."
tee /usr/local/bin/ftpmanager-status > /dev/null <<EOF
#!/bin/bash
echo "=== FTP Manager Status ==="
echo "Application: \$(supervisorctl status ftpmanager)"
echo "Nginx: \$(systemctl is-active nginx)"
echo "PostgreSQL: \$(systemctl is-active postgresql)"
echo "Disk Usage: \$(df -h $APP_DIR | tail -1)"
echo "Last Backup: \$(ls -la /home/$APP_USER/backups/ 2>/dev/null | tail -1 || echo 'No backups found')"
echo "==========================="
EOF

chmod +x /usr/local/bin/ftpmanager-status

print_success "Status check script created"

# Final verification
print_status "Performing final verification..."
sleep 5

# Check services
SUPERVISOR_STATUS=$(supervisorctl status ftpmanager | grep RUNNING || echo "FAILED")
NGINX_STATUS=$(systemctl is-active nginx)
POSTGRES_STATUS=$(systemctl is-active postgresql)

print_status "Service Status Check:"
echo "  - Supervisor (ftpmanager): $SUPERVISOR_STATUS"
echo "  - Nginx: $NGINX_STATUS"
echo "  - PostgreSQL: $POSTGRES_STATUS"

# Test HTTP response
if curl -k -s -o /dev/null -w "%{http_code}" https://localhost | grep -q "200\|302\|301"; then
    print_success "Application is responding to HTTPS requests"
else
    print_warning "Application may not be responding correctly"
fi

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
echo "  - Nginx Config: /etc/nginx/sites-available/ftpmanager"
echo "  - Supervisor Config: /etc/supervisor/conf.d/ftpmanager.conf"
echo ""
echo "Management Commands:"
echo "  - Check Status: ftpmanager-status"
echo "  - Restart App: supervisorctl restart ftpmanager"
echo "  - View Logs: tail -f $APP_DIR/logs/gunicorn.log"
echo "  - Manual Backup: /home/$APP_USER/backup.sh"
echo ""
echo "Database Credentials:"
echo "  - Database: $DB_NAME"
echo "  - Username: $DB_USER"
echo "  - Password: $DB_PASSWORD"
echo ""
print_warning "IMPORTANT: Save the database password above!"
print_warning "Browser will show SSL warning due to self-signed certificate"
echo ""
print_success "Access your application at: https://$DOMAIN"
echo ""