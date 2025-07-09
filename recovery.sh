#!/bin/bash

# FTP/SFTP Manager - Recovery Script for Ubuntu 24.04
# Use this script to fix a partial deployment

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run this script as root (use sudo)"
    exit 1
fi

# Configuration
APP_NAME="ftpmanager"
APP_USER="ftpmanager"
APP_DIR="/home/$APP_USER/$APP_NAME"
DB_NAME="ftpmanager_db"
DB_USER="ftpmanager_user"
DOMAIN="localhost"

print_status "Starting recovery process..."

# Get GitHub repository URL
echo -n "Enter GitHub repository URL: "
read GITHUB_REPO
if [ -z "$GITHUB_REPO" ]; then
    print_error "GitHub repository URL is required"
    exit 1
fi

# Generate new secure credentials
print_status "Generating secure credentials..."
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
SESSION_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
ENCRYPTION_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Install cryptography globally for key generation
print_status "Installing cryptography for key generation..."
pip3 install --break-system-packages cryptography

# Generate proper Fernet key
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

print_success "Secure credentials generated"

# Install missing dependencies
print_status "Installing missing system dependencies..."
apt update
apt install -y supervisor python3-venv python3-dev libpq-dev postgresql postgresql-contrib

# Ensure PostgreSQL is running
systemctl start postgresql
systemctl enable postgresql

# Create application user if not exists
if ! id "$APP_USER" &>/dev/null; then
    print_status "Creating application user..."
    useradd -m -s /bin/bash $APP_USER
    usermod -aG www-data $APP_USER
    print_success "User $APP_USER created"
fi

# Create application directory
print_status "Setting up application directory..."
sudo -u $APP_USER mkdir -p $APP_DIR
cd $APP_DIR

# Clone repository if not exists
if [ ! -f "$APP_DIR/main.py" ]; then
    print_status "Cloning repository..."
    sudo -u $APP_USER git clone $GITHUB_REPO .
fi

# Create required directories
sudo -u $APP_USER mkdir -p logs downloads static/uploads
sudo -u $APP_USER chmod 755 logs downloads static/uploads

# Setup Python virtual environment
print_status "Setting up Python environment..."
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install flask flask-sqlalchemy gunicorn psycopg2-binary apscheduler cryptography paramiko pytz werkzeug email-validator"

# Create environment file
print_status "Creating environment configuration..."
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$SESSION_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENCRYPTION_PASSWORD=$ENCRYPTION_PASSWORD
FLASK_ENV=production
EOF

sudo -u $APP_USER chmod 600 $APP_DIR/.env

# Setup database if not exists
print_status "Setting up database..."
sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME || {
    sudo -u postgres psql <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
\q
EOF
}

# Grant proper database permissions
sudo -u postgres psql -d $DB_NAME <<EOF
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
\q
EOF

# Initialize database
print_status "Initializing database..."
sudo -u $APP_USER bash -c "cd $APP_DIR && source venv/bin/activate && export \$(cat .env | xargs) && python3 -c \"
from main import app
from models import db
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
\""

# Create SSL certificate
print_status "Creating SSL certificate..."
SSL_DIR="/etc/ssl/certs/ftpmanager"
mkdir -p $SSL_DIR

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $SSL_DIR/ftpmanager.key \
    -out $SSL_DIR/ftpmanager.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$DOMAIN"

chmod 600 $SSL_DIR/ftpmanager.key
chmod 644 $SSL_DIR/ftpmanager.crt

# Create supervisor configuration
print_status "Creating supervisor configuration..."
mkdir -p /etc/supervisor/conf.d

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

# Start supervisor service
systemctl start supervisor
systemctl enable supervisor

# Update and start application
supervisorctl reread
supervisorctl update
supervisorctl start ftpmanager

# Configure Nginx
print_status "Configuring Nginx..."
tee /etc/nginx/sites-available/ftpmanager > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate $SSL_DIR/ftpmanager.crt;
    ssl_certificate_key $SSL_DIR/ftpmanager.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

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

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/ftpmanager /etc/nginx/sites-enabled/

nginx -t
systemctl restart nginx
systemctl enable nginx

# Configure firewall
print_status "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# Set proper permissions
chown -R $APP_USER:www-data $APP_DIR
chmod -R 750 $APP_DIR
chmod 600 $APP_DIR/.env

# Final status check
print_status "Checking services..."
echo "Supervisor status: $(supervisorctl status ftpmanager)"
echo "Nginx status: $(systemctl is-active nginx)"
echo "PostgreSQL status: $(systemctl is-active postgresql)"

# Test application
if curl -k -s -o /dev/null -w "%{http_code}" https://localhost | grep -q "200\|302\|301"; then
    print_success "Application is responding!"
else
    print_warning "Application may not be responding correctly"
fi

print_success "=== RECOVERY COMPLETED ==="
echo ""
echo "Application URL: https://$DOMAIN"
echo "Database: $DB_NAME"
echo "Database User: $DB_USER"
echo "Database Password: $DB_PASSWORD"
echo ""
echo "Application logs: tail -f $APP_DIR/logs/gunicorn.log"
echo "Restart application: supervisorctl restart ftpmanager"
echo ""
print_warning "Save the database password above!"
echo ""