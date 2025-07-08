import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from utils import get_setting

logger = logging.getLogger(__name__)

def send_notification(subject, body, is_success=True):
    """Send email notification"""
    try:
        # Get SMTP settings
        smtp_server = get_setting('smtp_server')
        smtp_port = int(get_setting('smtp_port', '587'))
        smtp_use_tls = get_setting('smtp_use_tls', 'true').lower() == 'true'
        smtp_username = get_setting('smtp_username')
        smtp_password = get_setting('smtp_password', encrypted=True)
        smtp_from_email = get_setting('smtp_from_email')
        notification_email = get_setting('notification_email')
        
        # Check if all required settings are available
        if not all([smtp_server, smtp_username, smtp_password, smtp_from_email, notification_email]):
            logger.warning("SMTP settings not configured, skipping email notification")
            return {'success': False, 'error': 'SMTP settings not configured'}
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = smtp_from_email
        msg['To'] = notification_email
        msg['Subject'] = subject
        
        # Add timestamp to body
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_body = f"{body}\n\n---\nTimestamp: {timestamp}"
        
        # Add body to email
        msg.attach(MIMEText(full_body, 'plain'))
        
        # Connect to server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email notification sent successfully: {subject}")
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        return {'success': False, 'error': str(e)}

def send_test_email():
    """Send test email to verify SMTP configuration"""
    try:
        subject = "FTP/SFTP Manager - Test Email"
        body = "This is a test email to verify your SMTP configuration is working correctly."
        
        result = send_notification(subject, body, is_success=True)
        
        if result['success']:
            logger.info("Test email sent successfully")
        else:
            logger.error(f"Test email failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        return {'success': False, 'error': str(e)}

def format_job_completion_email(job_name, success, files_processed=0, bytes_transferred=0, error_message=None):
    """Format job completion email"""
    if success:
        subject = f"✅ Job '{job_name}' completed successfully"
        body = f"""
Job '{job_name}' has been completed successfully.

Details:
- Files processed: {files_processed}
- Bytes transferred: {bytes_transferred:,}
- Status: Completed

This is an automated notification from your FTP/SFTP Management System.
"""
    else:
        subject = f"❌ Job '{job_name}' failed"
        body = f"""
Job '{job_name}' has failed to complete.

Details:
- Status: Failed
- Error: {error_message or 'Unknown error'}

Please check the system logs for more details.

This is an automated notification from your FTP/SFTP Management System.
"""
    
    return subject, body

def send_job_notification(job_name, success, files_processed=0, bytes_transferred=0, error_message=None):
    """Send job completion notification"""
    try:
        subject, body = format_job_completion_email(
            job_name, success, files_processed, bytes_transferred, error_message
        )
        
        return send_notification(subject, body, is_success=success)
        
    except Exception as e:
        logger.error(f"Error sending job notification: {str(e)}")
        return {'success': False, 'error': str(e)}
