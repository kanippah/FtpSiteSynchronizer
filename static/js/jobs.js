// Jobs management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initializeJobsPage();
});

function initializeJobsPage() {
    // Initialize form validation
    initializeJobFormValidation();
    
    // Initialize schedule type handlers
    initializeScheduleHandlers();
    
    // Initialize job type handlers
    initializeJobTypeHandlers();
    
    // Initialize run job handlers
    initializeRunJobHandlers();
    
    // Initialize delete confirmations
    initializeDeleteConfirmations();
    
    // Initialize date range handlers
    initializeDateRangeHandlers();
}

function initializeJobFormValidation() {
    const jobForm = document.getElementById('jobForm');
    if (jobForm) {
        jobForm.addEventListener('submit', function(e) {
            if (!validateJobForm()) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }
}

function validateJobForm() {
    let isValid = true;
    
    // Validate required fields
    const requiredFields = ['name', 'site_id', 'job_type', 'schedule_type'];
    requiredFields.forEach(field => {
        const input = document.getElementById(field);
        if (input && !input.value.trim()) {
            showFieldError(input, `${field.replace('_', ' ').charAt(0).toUpperCase() + field.slice(1)} is required`);
            isValid = false;
        } else {
            clearFieldError(input);
        }
    });
    
    // Validate schedule-specific fields
    const scheduleType = document.getElementById('schedule_type');
    if (scheduleType) {
        if (scheduleType.value === 'one_time') {
            const scheduleDateTime = document.getElementById('schedule_datetime');
            if (scheduleDateTime && !scheduleDateTime.value) {
                showFieldError(scheduleDateTime, 'Schedule date and time is required');
                isValid = false;
            } else {
                clearFieldError(scheduleDateTime);
            }
        } else if (scheduleType.value === 'recurring') {
            const cronExpression = document.getElementById('cron_expression');
            if (cronExpression && !cronExpression.value.trim()) {
                showFieldError(cronExpression, 'Cron expression is required');
                isValid = false;
            } else if (cronExpression && !validateCronExpression(cronExpression.value)) {
                showFieldError(cronExpression, 'Invalid cron expression format');
                isValid = false;
            } else {
                clearFieldError(cronExpression);
            }
        }
    }
    
    // Validate date range if enabled
    const useDateRange = document.getElementById('use_date_range');
    const useRollingDateRange = document.getElementById('use_rolling_date_range');
    
    if (useDateRange && useDateRange.checked) {
        const dateFrom = document.getElementById('date_from');
        const dateTo = document.getElementById('date_to');
        
        if (dateFrom && !dateFrom.value) {
            showFieldError(dateFrom, 'From date is required');
            isValid = false;
        } else {
            clearFieldError(dateFrom);
        }
        
        if (dateTo && !dateTo.value) {
            showFieldError(dateTo, 'To date is required');
            isValid = false;
        } else {
            clearFieldError(dateTo);
        }
        
        // Validate date range
        if (dateFrom && dateTo && dateFrom.value && dateTo.value) {
            const fromDate = new Date(dateFrom.value);
            const toDate = new Date(dateTo.value);
            
            if (fromDate > toDate) {
                showFieldError(dateTo, 'To date must be after from date');
                isValid = false;
            }
        }
    }
    
    // Validate rolling date range if enabled
    if (useRollingDateRange && useRollingDateRange.checked) {
        const rollingPattern = document.getElementById('rolling_pattern');
        if (rollingPattern && !rollingPattern.value) {
            showFieldError(rollingPattern, 'Rolling pattern is required');
            isValid = false;
        } else {
            clearFieldError(rollingPattern);
            
            // Validate custom rolling pattern fields if selected
            if (rollingPattern && rollingPattern.value === 'custom') {
                const dateOffsetFrom = document.getElementById('date_offset_from');
                const dateOffsetTo = document.getElementById('date_offset_to');
                
                if (dateOffsetFrom && !dateOffsetFrom.value) {
                    showFieldError(dateOffsetFrom, 'Previous month day is required');
                    isValid = false;
                } else {
                    clearFieldError(dateOffsetFrom);
                }
                
                if (dateOffsetTo && !dateOffsetTo.value) {
                    showFieldError(dateOffsetTo, 'Current month day is required');
                    isValid = false;
                } else {
                    clearFieldError(dateOffsetTo);
                }
            }
        }
    }
    
    // Validate upload job specific fields
    const jobType = document.getElementById('job_type');
    if (jobType && jobType.value === 'upload') {
        const targetSiteId = document.getElementById('target_site_id');
        if (targetSiteId && !targetSiteId.value) {
            showFieldError(targetSiteId, 'Target site is required for upload jobs');
            isValid = false;
        } else {
            clearFieldError(targetSiteId);
        }
    }
    
    return isValid;
}

function validateCronExpression(expression) {
    // Basic cron validation (5 parts separated by spaces)
    const parts = expression.trim().split(/\s+/);
    if (parts.length !== 5) {
        return false;
    }
    
    // Check each part
    const ranges = [
        [0, 59],  // minute
        [0, 23],  // hour
        [1, 31],  // day
        [1, 12],  // month
        [0, 6]    // day of week
    ];
    
    for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        
        if (part === '*') {
            continue;
        }
        
        // Handle ranges (e.g., 1-5)
        if (part.includes('-')) {
            const [start, end] = part.split('-');
            if (isNaN(start) || isNaN(end) || start < ranges[i][0] || end > ranges[i][1]) {
                return false;
            }
        }
        // Handle lists (e.g., 1,3,5)
        else if (part.includes(',')) {
            const values = part.split(',');
            for (const value of values) {
                if (isNaN(value) || value < ranges[i][0] || value > ranges[i][1]) {
                    return false;
                }
            }
        }
        // Handle single values
        else {
            if (isNaN(part) || part < ranges[i][0] || part > ranges[i][1]) {
                return false;
            }
        }
    }
    
    return true;
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

function initializeScheduleHandlers() {
    const scheduleType = document.getElementById('schedule_type');
    const oneTimeFields = document.getElementById('one_time_fields');
    const recurringFields = document.getElementById('recurring_fields');
    
    if (scheduleType) {
        scheduleType.addEventListener('change', function() {
            if (oneTimeFields) {
                oneTimeFields.style.display = this.value === 'one_time' ? 'block' : 'none';
            }
            if (recurringFields) {
                recurringFields.style.display = this.value === 'recurring' ? 'block' : 'none';
            }
        });
        
        // Trigger change event on load
        scheduleType.dispatchEvent(new Event('change'));
    }
}

function initializeJobTypeHandlers() {
    const jobType = document.getElementById('job_type');
    const uploadFields = document.getElementById('upload_fields');
    const downloadAllField = document.getElementById('download_all_field');
    const useDateRange = document.getElementById('use_date_range');
    
    if (jobType) {
        jobType.addEventListener('change', function() {
            if (uploadFields) {
                uploadFields.style.display = this.value === 'upload' ? 'block' : 'none';
            }
            
            // Show download all field only for download jobs and when date range is not enabled
            if (downloadAllField) {
                if (this.value === 'download') {
                    if (useDateRange && !useDateRange.checked) {
                        downloadAllField.style.display = 'block';
                    } else {
                        downloadAllField.style.display = 'none';
                    }
                } else {
                    downloadAllField.style.display = 'none';
                }
            }
        });
        
        // Trigger change event on load
        jobType.dispatchEvent(new Event('change'));
    }
}

function initializeDateRangeHandlers() {
    const useDateRange = document.getElementById('use_date_range');
    const useRollingDateRange = document.getElementById('use_rolling_date_range');
    const dateRangeFields = document.getElementById('date_range_fields');
    const rollingDateRangeFields = document.getElementById('rolling_date_range_fields');
    const downloadAllField = document.getElementById('download_all_field');
    const downloadAll = document.getElementById('download_all');
    
    if (useDateRange) {
        useDateRange.addEventListener('change', function() {
            if (dateRangeFields) {
                dateRangeFields.style.display = this.checked ? 'block' : 'none';
            }
            // Clear rolling date range when static date range is enabled
            if (this.checked && useRollingDateRange) {
                useRollingDateRange.checked = false;
                if (rollingDateRangeFields) {
                    rollingDateRangeFields.style.display = 'none';
                }
            }
            updateDownloadAllVisibility();
            // Clear download all when date range is enabled
            if (this.checked && downloadAll) {
                downloadAll.checked = false;
            }
        });
        
        // Trigger change event on load
        useDateRange.dispatchEvent(new Event('change'));
    }
    
    if (useRollingDateRange) {
        useRollingDateRange.addEventListener('change', function() {
            if (rollingDateRangeFields) {
                rollingDateRangeFields.style.display = this.checked ? 'block' : 'none';
            }
            // Clear static date range when rolling date range is enabled
            if (this.checked && useDateRange) {
                useDateRange.checked = false;
                if (dateRangeFields) {
                    dateRangeFields.style.display = 'none';
                }
            }
            updateDownloadAllVisibility();
            // Clear download all when rolling date range is enabled
            if (this.checked && downloadAll) {
                downloadAll.checked = false;
            }
        });
        
        // Trigger change event on load
        useRollingDateRange.dispatchEvent(new Event('change'));
    }
    
    // Handle rolling pattern change to show/hide custom fields
    const rollingPattern = document.getElementById('rolling_pattern');
    const customRollingFields = document.getElementById('custom_rolling_fields');
    
    if (rollingPattern) {
        rollingPattern.addEventListener('change', function() {
            if (customRollingFields) {
                customRollingFields.style.display = this.value === 'custom' ? 'block' : 'none';
            }
        });
        
        // Trigger change event on load
        rollingPattern.dispatchEvent(new Event('change'));
    }
    
    // Handle download all checkbox
    if (downloadAll) {
        downloadAll.addEventListener('change', function() {
            // If download all is checked, disable both date range options
            if (this.checked) {
                if (useDateRange) {
                    useDateRange.checked = false;
                    useDateRange.dispatchEvent(new Event('change'));
                }
                if (useRollingDateRange) {
                    useRollingDateRange.checked = false;
                    useRollingDateRange.dispatchEvent(new Event('change'));
                }
            }
        });
    }
    
    function updateDownloadAllVisibility() {
        if (downloadAllField) {
            const jobType = document.getElementById('job_type');
            const hasDateFilter = (useDateRange && useDateRange.checked) || (useRollingDateRange && useRollingDateRange.checked);
            
            if (jobType && jobType.value === 'download' && !hasDateFilter) {
                downloadAllField.style.display = 'block';
            } else {
                downloadAllField.style.display = 'none';
            }
        }
    }
    
    // Set default date range to previous month to current month
    setDefaultDateRange();
}

function setDefaultDateRange() {
    const dateFrom = document.getElementById('date_from');
    const dateTo = document.getElementById('date_to');
    
    if (dateFrom && dateTo && !dateFrom.value && !dateTo.value) {
        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();
        
        // From date: 26th of previous month
        const fromDate = new Date(currentYear, currentMonth - 1, 26);
        
        // To date: 25th of current month
        const toDate = new Date(currentYear, currentMonth, 25);
        
        // Format dates as YYYY-MM-DD
        dateFrom.value = fromDate.toISOString().split('T')[0];
        dateTo.value = toDate.toISOString().split('T')[0];
    }
}

function initializeRunJobHandlers() {
    const runButtons = document.querySelectorAll('.run-job');
    
    runButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const jobId = this.dataset.jobId;
            const jobName = this.dataset.jobName;
            
            if (confirm(`Are you sure you want to run the job "${jobName}" now?`)) {
                runJob(jobId, this);
            }
        });
    });
}

function runJob(jobId, button) {
    const originalText = button.textContent;
    const originalDisabled = button.disabled;
    
    // Show loading state
    button.innerHTML = '<span class="loading-spinner me-2"></span>Running...';
    button.disabled = true;
    
    fetch(`/jobs/${jobId}/run`)
        .then(response => {
            if (response.ok) {
                // The server handles the flash message
                location.reload();
            } else {
                throw new Error('Network response was not ok');
            }
        })
        .catch(error => {
            console.error('Error running job:', error);
            showAlert('Error running job. Please try again.', 'danger');
        })
        .finally(() => {
            // Restore button state
            button.textContent = originalText;
            button.disabled = originalDisabled;
        });
}

function initializeDeleteConfirmations() {
    const deleteButtons = document.querySelectorAll('.delete-job');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const jobName = this.dataset.jobName;
            const jobId = this.dataset.jobId;
            
            if (confirm(`Are you sure you want to delete the job "${jobName}"? This action cannot be undone.`)) {
                deleteJob(jobId);
            }
        });
    });
}

function deleteJob(jobId) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/jobs/${jobId}/delete`;
    
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

// Cron expression helper
function insertCronExpression(expression) {
    const cronInput = document.getElementById('cron_expression');
    if (cronInput) {
        cronInput.value = expression;
        clearFieldError(cronInput);
    }
}

// Common cron expressions
const commonCronExpressions = {
    'Every minute': '* * * * *',
    'Every hour': '0 * * * *',
    'Every day at midnight': '0 0 * * *',
    'Every day at 6 AM': '0 6 * * *',
    'Every Monday at 9 AM': '0 9 * * 1',
    'Every month on the 1st at midnight': '0 0 1 * *',
    'Every weekday at 9 AM': '0 9 * * 1-5'
};

// Add cron helper buttons if form exists
document.addEventListener('DOMContentLoaded', function() {
    const cronInput = document.getElementById('cron_expression');
    if (cronInput) {
        const helperDiv = document.createElement('div');
        helperDiv.className = 'mt-2';
        helperDiv.innerHTML = '<small class="text-muted">Quick options:</small><br>';
        
        Object.entries(commonCronExpressions).forEach(([name, expression]) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-sm btn-outline-secondary me-1 mb-1';
            button.textContent = name;
            button.onclick = () => insertCronExpression(expression);
            helperDiv.appendChild(button);
        });
        
        cronInput.parentNode.appendChild(helperDiv);
    }
});
