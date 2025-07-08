import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Generate or load encryption key
def get_encryption_key():
    """Get or generate encryption key"""
    try:
        # Try to get key from environment
        key_env = os.environ.get('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
        # Generate key from a password (use a more secure method in production)
        password = os.environ.get('ENCRYPTION_PASSWORD', 'default-password-change-in-production').encode()
        salt = os.environ.get('ENCRYPTION_SALT', 'default-salt').encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
        
    except Exception as e:
        logger.error(f"Error getting encryption key: {str(e)}")
        # Fallback to a generated key (not recommended for production)
        return Fernet.generate_key()

# Initialize Fernet with the key
encryption_key = get_encryption_key()
fernet = Fernet(encryption_key)

def encrypt_password(password):
    """Encrypt a password"""
    try:
        if not password:
            return b''
        
        password_bytes = password.encode('utf-8')
        encrypted_password = fernet.encrypt(password_bytes)
        return encrypted_password
        
    except Exception as e:
        logger.error(f"Error encrypting password: {str(e)}")
        raise

def decrypt_password(encrypted_password):
    """Decrypt a password"""
    try:
        if not encrypted_password:
            return ''
        
        decrypted_password = fernet.decrypt(encrypted_password)
        return decrypted_password.decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error decrypting password: {str(e)}")
        raise

def encrypt_text(text):
    """Encrypt any text"""
    try:
        if not text:
            return b''
        
        text_bytes = text.encode('utf-8')
        encrypted_text = fernet.encrypt(text_bytes)
        return encrypted_text
        
    except Exception as e:
        logger.error(f"Error encrypting text: {str(e)}")
        raise

def decrypt_text(encrypted_text):
    """Decrypt any text"""
    try:
        if not encrypted_text:
            return ''
        
        decrypted_text = fernet.decrypt(encrypted_text)
        return decrypted_text.decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error decrypting text: {str(e)}")
        raise
