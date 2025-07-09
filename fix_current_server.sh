#!/bin/bash

# Fix the current server's supervisor configuration
set -e

echo "Fixing supervisor configuration on current server..."

# Get the existing environment variables from the deployment
DB_USER="ftpmanager_user"
DB_NAME="ftpmanager_db"
APP_USER="ftpmanager"
APP_DIR="/home/ftpmanager/ftpmanager"

# Generate new secure credentials
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
SESSION_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
ENCRYPTION_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Install cryptography and generate Fernet key
pip3 install --break-system-packages cryptography 2>/dev/null || true
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Update database password
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

# Remove broken supervisor config
rm -f /etc/supervisor/conf.d/ftpmanager.conf

# Create supervisor configuration using printf method
printf '[program:ftpmanager]\n' > /etc/supervisor/conf.d/ftpmanager.conf
printf 'command=%s/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 main:app\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'directory=%s\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'user=%s\n' "$APP_USER" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'autostart=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'autorestart=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'redirect_stderr=true\n' >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'stdout_logfile=%s/logs/gunicorn.log\n' "$APP_DIR" >> /etc/supervisor/conf.d/ftpmanager.conf
printf 'environment=DATABASE_URL="postgresql://%s:%s@localhost/%s",SESSION_SECRET="%s",ENCRYPTION_KEY="%s",ENCRYPTION_PASSWORD="%s",FLASK_ENV="production"\n' "$DB_USER" "$DB_PASSWORD" "$DB_NAME" "$SESSION_SECRET" "$ENCRYPTION_KEY" "$ENCRYPTION_PASSWORD" >> /etc/supervisor/conf.d/ftpmanager.conf

# Update environment file
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
SESSION_SECRET=$SESSION_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ENCRYPTION_PASSWORD=$ENCRYPTION_PASSWORD
FLASK_ENV=production
EOF

sudo -u $APP_USER chmod 600 $APP_DIR/.env

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

# Restart supervisor and start application
echo "Restarting supervisor..."
systemctl restart supervisor
sleep 2

echo "Reading supervisor configuration..."
supervisorctl reread

echo "Updating supervisor..."
supervisorctl update

echo "Starting application..."
supervisorctl start ftpmanager

sleep 3
echo "Final status:"
supervisorctl status ftpmanager

echo ""
echo "=== CONFIGURATION COMPLETE ==="
echo "Application URL: https://localhost"
echo "Database: $DB_NAME"
echo "Database User: $DB_USER"
echo "Database Password: $DB_PASSWORD"
echo ""
echo "Management Commands:"
echo "  ftpmanager-status - Check system status"
echo "  ftpmanager-restart - Restart application"
echo ""
echo "Save the database password above!"