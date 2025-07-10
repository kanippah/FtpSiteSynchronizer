// Sites management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initializeSitesPage();
});

function initializeSitesPage() {
    // Initialize form validation
    initializeFormValidation();
    
    // Initialize protocol change handlers
    initializeProtocolHandlers();
    
    // Initialize test connection handlers
    initializeTestHandlers();
    
    // Initialize delete confirmations
    initializeDeleteConfirmations();
}

function initializeFormValidation() {
    const siteForm = document.getElementById('siteForm');
    if (siteForm) {
        siteForm.addEventListener('submit', function(e) {
            if (!validateSiteForm()) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }
}

function validateSiteForm() {
    let isValid = true;
    
    // Validate required fields
    const requiredFields = ['name', 'host', 'username', 'password'];
    requiredFields.forEach(field => {
        const input = document.getElementById(field);
        if (input && !input.value.trim()) {
            showFieldError(input, `${field.charAt(0).toUpperCase() + field.slice(1)} is required`);
            isValid = false;
        } else {
            clearFieldError(input);
        }
    });
    
    // Validate port
    const portInput = document.getElementById('port');
    if (portInput) {
        const port = parseInt(portInput.value);
        if (isNaN(port) || port < 1 || port > 65535) {
            showFieldError(portInput, 'Please enter a valid port number (1-65535)');
            isValid = false;
        } else {
            clearFieldError(portInput);
        }
    }
    
    // Validate host format
    const hostInput = document.getElementById('host');
    if (hostInput && hostInput.value.trim()) {
        const host = hostInput.value.trim();
        // Basic host validation (IP or hostname)
        const hostPattern = /^[a-zA-Z0-9.-]+$/;
        if (!hostPattern.test(host)) {
            showFieldError(hostInput, 'Please enter a valid hostname or IP address');
            isValid = false;
        } else {
            clearFieldError(hostInput);
        }
    }
    
    return isValid;
}

function showFieldError(input, message) {
    clearFieldError(input);
    
    input.classList.add('is-invalid');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback';
    errorDiv.textContent = message;
    
    input.parentNode.appendChild(errorDiv);
}

function clearFieldError(input) {
    if (input) {
        input.classList.remove('is-invalid');
        
        const errorDiv = input.parentNode.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
}

function initializeProtocolHandlers() {
    const protocolSelect = document.getElementById('protocol');
    const portInput = document.getElementById('port');
    const ftpSftpFields = document.querySelector('.ftp-sftp-fields');
    const nfsFields = document.querySelector('.nfs-fields');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const nfsExportInput = document.getElementById('nfs_export_path');
    
    if (protocolSelect) {
        // Initialize visibility based on current selection
        toggleProtocolFields(protocolSelect.value);
        
        protocolSelect.addEventListener('change', function() {
            const protocol = this.value;
            
            // Set default port based on protocol
            if (portInput) {
                if (protocol === 'ftp') {
                    portInput.value = '21';
                } else if (protocol === 'sftp') {
                    portInput.value = '22';
                } else if (protocol === 'nfs') {
                    portInput.value = '2049';
                }
            }
            
            // Toggle field visibility
            toggleProtocolFields(protocol);
        });
    }
    
    function toggleProtocolFields(protocol) {
        if (ftpSftpFields && nfsFields) {
            if (protocol === 'nfs') {
                ftpSftpFields.style.display = 'none';
                nfsFields.style.display = 'block';
                
                // Make NFS fields required, FTP/SFTP fields optional
                if (usernameInput) usernameInput.removeAttribute('required');
                if (passwordInput) passwordInput.removeAttribute('required');
                if (nfsExportInput) nfsExportInput.setAttribute('required', 'required');
            } else {
                ftpSftpFields.style.display = 'block';
                nfsFields.style.display = 'none';
                
                // Make FTP/SFTP fields required, NFS fields optional
                if (usernameInput) usernameInput.setAttribute('required', 'required');
                if (passwordInput && !passwordInput.closest('form').querySelector('input[name="site_id"]')) {
                    // Only require password for new sites, not edits
                    passwordInput.setAttribute('required', 'required');
                }
                if (nfsExportInput) nfsExportInput.removeAttribute('required');
            }
        }
    }
}

function initializeTestHandlers() {
    const testButtons = document.querySelectorAll('.test-connection');
    
    testButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const siteId = this.dataset.siteId;
            testConnection(siteId, this);
        });
    });
}

function testConnection(siteId, button) {
    const originalText = button.textContent;
    const originalDisabled = button.disabled;
    
    // Show loading state
    button.innerHTML = '<span class="loading-spinner me-2"></span>Testing...';
    button.disabled = true;
    
    fetch(`/sites/${siteId}/test`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error testing connection:', error);
            showAlert('Error testing connection. Please try again.', 'danger');
        })
        .finally(() => {
            // Restore button state
            button.textContent = originalText;
            button.disabled = originalDisabled;
        });
}

function initializeDeleteConfirmations() {
    const deleteButtons = document.querySelectorAll('.delete-site');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const siteName = this.dataset.siteName;
            const siteId = this.dataset.siteId;
            
            if (confirm(`Are you sure you want to delete the site "${siteName}"? This action cannot be undone.`)) {
                deleteSite(siteId);
            }
        });
    });
}

function deleteSite(siteId) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/sites/${siteId}/delete`;
    
    // Add CSRF token if available
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = csrfToken.content;
        form.appendChild(csrfInput);
    }
    
    document.body.appendChild(form);
    form.submit();
}

function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts-container') || document.body;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertsContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.classList.remove('show');
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 150);
        }
    }, 5000);
}

// Form auto-save functionality
function initializeAutoSave() {
    const form = document.getElementById('siteForm');
    if (form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                // Save to localStorage
                const formData = new FormData(form);
                const data = {};
                
                for (let [key, value] of formData.entries()) {
                    data[key] = value;
                }
                
                localStorage.setItem('siteForm', JSON.stringify(data));
            });
        });
        
        // Restore from localStorage
        const savedData = localStorage.getItem('siteForm');
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                
                Object.keys(data).forEach(key => {
                    const input = form.querySelector(`[name="${key}"]`);
                    if (input && input.type !== 'password') {
                        input.value = data[key];
                    }
                });
            } catch (e) {
                console.error('Error restoring form data:', e);
            }
        }
        
        // Clear saved data on successful submit
        form.addEventListener('submit', function() {
            localStorage.removeItem('siteForm');
        });
    }
}

// Initialize auto-save if needed
if (document.getElementById('siteForm')) {
    initializeAutoSave();
}
