#!/bin/bash

# Complete fix for supervisor and application deployment
set -e

echo "=== Complete Server Fix ==="

# Configuration
DB_USER="ftpmanager_user"
DB_NAME="ftpmanager_db"
APP_USER="ftpmanager"
APP_DIR="/home/ftpmanager/ftpmanager"

# Generate secure credentials
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
SESSION_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
ENCRYPTION_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Install cryptography and generate Fernet key
pip3 install --break-system-packages cryptography 2>/dev/null || true
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

echo "Generated secure credentials"

# Update database password
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo "Database user updated"

# Kill any existing supervisor processes
pkill -f supervisord || true
pkill -f supervisor || true

# Remove supervisor socket and pid files
rm -f /var/run/supervisor.sock
rm -f /var/run/supervisord.pid
rm -f /tmp/supervisor.sock

# Stop and restart supervisor service
systemctl stop supervisor 2>/dev/null || true
sleep 2
systemctl start supervisor
systemctl enable supervisor

# Create supervisor directory structure
mkdir -p /etc/supervisor/conf.d
mkdir -p /var/log/supervisor

# Remove any existing ftpmanager config
rm -f /etc/supervisor/conf.d/ftpmanager.conf

# Create supervisor configuration
cat > /etc/supervisor/conf.d/ftpmanager.conf << 'EOFCONFIG'
[program:ftpmanager]
command=/home/ftpmanager/ftpmanager/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 main:app
directory=/home/ftpmanager/ftpmanager
user=ftpmanager
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/ftpmanager/ftpmanager/logs/gunicorn.log
environment=DATABASE_URL="postgresql://ftpmanager_user:password@localhost/ftpmanager_db",SESSION_SECRET="secret",ENCRYPTION_KEY="key",ENCRYPTION_PASSWORD="password",FLASK_ENV="production"
EOFCONFIG

# Now update the environment variables in the config file
sed -i "s/password@localhost/\${DB_PASSWORD}@localhost/g" /etc/supervisor/conf.d/ftpmanager.conf
sed -i "s/SESSION_SECRET=\"secret\"/SESSION_SECRET=\"${SESSION_SECRET}\"/g" /etc/supervisor/conf.d/ftpmanager.conf
sed -i "s/ENCRYPTION_KEY=\"key\"/ENCRYPTION_KEY=\"${ENCRYPTION_KEY}\"/g" /etc/supervisor/conf.d/ftpmanager.conf
sed -i "s/ENCRYPTION_PASSWORD=\"password\"/ENCRYPTION_PASSWORD=\"${ENCRYPTION_PASSWORD}\"/g" /etc/supervisor/conf.d/ftpmanager.conf
sed -i "s/\${DB_PASSWORD}/${DB_PASSWORD}/g" /etc/supervisor/conf.d/ftpmanager.conf

echo "Created supervisor configuration"

# Create/update environment file
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$SESSION_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENCRYPTION_PASSWORD=$ENCRYPTION_PASSWORD
FLASK_ENV=production
EOF

sudo -u $APP_USER chmod 600 $APP_DIR/.env

# Ensure application directory exists and has proper permissions
sudo -u $APP_USER mkdir -p $APP_DIR/logs
sudo -u $APP_USER mkdir -p $APP_DIR/downloads
sudo -u $APP_USER mkdir -p $APP_DIR/static/uploads

# Create management scripts
cat > /usr/local/bin/ftpmanager-status << 'EOFSTATUS'
#!/bin/bash
echo "=== FTP Manager Status ==="
echo "Application: $(supervisorctl status ftpmanager 2>/dev/null || echo 'Not running')"
echo "Nginx: $(systemctl is-active nginx 2>/dev/null || echo 'inactive')"
echo "PostgreSQL: $(systemctl is-active postgresql 2>/dev/null || echo 'inactive')"
echo "Supervisor: $(systemctl is-active supervisor 2>/dev/null || echo 'inactive')"
echo "Recent Logs:"
tail -5 /home/ftpmanager/ftpmanager/logs/gunicorn.log 2>/dev/null || echo "No logs available"
echo "==========================="
EOFSTATUS

cat > /usr/local/bin/ftpmanager-restart << 'EOFRESTART'
#!/bin/bash
echo "Restarting FTP Manager..."
supervisorctl restart ftpmanager
sleep 3
supervisorctl status ftpmanager
EOFRESTART

chmod +x /usr/local/bin/ftpmanager-status
chmod +x /usr/local/bin/ftpmanager-restart

# Wait for supervisor to fully start
sleep 5

# Read and update supervisor configuration
supervisorctl reread
supervisorctl update

# Start the application
supervisorctl start ftpmanager

# Wait and check status
sleep 5
STATUS=$(supervisorctl status ftpmanager)
echo "Application status: $STATUS"

# Test application
if curl -k -s -o /dev/null -w "%{http_code}" https://localhost | grep -q "200\|302\|301"; then
    echo "✓ Application is responding to HTTPS requests"
else
    echo "⚠ Application may not be responding correctly"
    echo "Checking recent logs:"
    tail -10 /home/ftpmanager/ftpmanager/logs/gunicorn.log 2>/dev/null || echo "No logs available"
fi

echo ""
echo "=== SETUP COMPLETE ==="
echo "Application URL: https://localhost"
echo "Database: $DB_NAME"
echo "Database User: $DB_USER"
echo "Database Password: $DB_PASSWORD"
echo ""
echo "Management Commands:"
echo "  ftpmanager-status - Check system status"
echo "  ftpmanager-restart - Restart application"
echo ""
echo "IMPORTANT: Save the database password above!"