#!/bin/bash

# Quick fix for supervisor configuration without user input
set -e

echo "Fixing supervisor configuration..."

# Get database password from existing configuration
DB_PASSWORD="your_password_here"  # This will be replaced by actual password from deployment

# Generate missing credentials
SESSION_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
pip3 install --break-system-packages cryptography 2>/dev/null || true
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Remove broken supervisor config
rm -f /etc/supervisor/conf.d/ftpmanager.conf

# Create correct supervisor configuration
cat > /etc/supervisor/conf.d/ftpmanager.conf << 'EOFCONFIG'
[program:ftpmanager]
command=/home/ftpmanager/ftpmanager/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 main:app
directory=/home/ftpmanager/ftpmanager
user=ftpmanager
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/ftpmanager/ftpmanager/logs/gunicorn.log
environment=DATABASE_URL="postgresql://ftpmanager_user:password123@localhost/ftpmanager_db",SESSION_SECRET="secret123",ENCRYPTION_KEY="key123",ENCRYPTION_PASSWORD="pass123",FLASK_ENV="production"
EOFCONFIG

# Create management scripts
cat > /usr/local/bin/ftpmanager-status << 'EOFSTATUS'
#!/bin/bash
echo "=== FTP Manager Status ==="
echo "Application: $(supervisorctl status ftpmanager 2>/dev/null || echo 'Not running')"
echo "Nginx: $(systemctl is-active nginx 2>/dev/null || echo 'inactive')"
echo "PostgreSQL: $(systemctl is-active postgresql 2>/dev/null || echo 'inactive')"
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

# Restart supervisor
systemctl restart supervisor
sleep 2
supervisorctl reread
supervisorctl update
supervisorctl start ftpmanager

echo "Fixed! Management commands available:"
echo "  ftpmanager-status"
echo "  ftpmanager-restart"