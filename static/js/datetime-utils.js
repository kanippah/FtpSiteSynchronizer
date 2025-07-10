/**
 * DateTime utilities for converting server timestamps to local browser time
 */

// Function to format datetime in local timezone
function formatLocalDateTime(utcDateString, options = {}) {
    if (!utcDateString || utcDateString === '') return '-';
    
    try {
        // Parse the UTC date string - handle different formats
        let utcDate;
        if (utcDateString.includes('T')) {
            // ISO format: 2024-01-01T12:00:00 or 2024-01-01T12:00:00Z
            utcDate = new Date(utcDateString.endsWith('Z') ? utcDateString : utcDateString + 'Z');
        } else {
            // Space format: 2024-01-01 12:00:00
            utcDate = new Date(utcDateString + ' UTC');
        }
        
        // Check if date is valid
        if (isNaN(utcDate.getTime())) {
            return utcDateString; // Return original if can't parse
        }
        
        // Default formatting options
        const defaultOptions = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZoneName: 'short'
        };
        
        const formatOptions = { ...defaultOptions, ...options };
        
        // Format in user's local timezone
        return utcDate.toLocaleString(navigator.language || 'en-US', formatOptions);
    } catch (error) {
        console.error('Error formatting date:', error, 'Input:', utcDateString);
        return utcDateString; // Fallback to original string
    }
}

// Function to format just the date
function formatLocalDate(utcDateString) {
    if (!utcDateString || utcDateString === '') return '-';
    
    try {
        let utcDate;
        if (utcDateString.includes('T')) {
            utcDate = new Date(utcDateString.endsWith('Z') ? utcDateString : utcDateString + 'Z');
        } else {
            utcDate = new Date(utcDateString + ' UTC');
        }
        
        if (isNaN(utcDate.getTime())) {
            return utcDateString;
        }
        
        return utcDate.toLocaleDateString('en-CA'); // YYYY-MM-DD format
    } catch (error) {
        return utcDateString;
    }
}

// Function to format just the time
function formatLocalTime(utcDateString) {
    if (!utcDateString || utcDateString === '') return '-';
    
    try {
        let utcDate;
        if (utcDateString.includes('T')) {
            utcDate = new Date(utcDateString.endsWith('Z') ? utcDateString : utcDateString + 'Z');
        } else {
            utcDate = new Date(utcDateString + ' UTC');
        }
        
        if (isNaN(utcDate.getTime())) {
            return utcDateString;
        }
        
        return utcDate.toLocaleTimeString('en-GB', { hour12: false }); // HH:MM:SS format
    } catch (error) {
        return utcDateString;
    }
}

// Function to get user's timezone
function getUserTimezone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch (error) {
        return 'UTC';
    }
}

// Function to convert all datetime elements on page
function convertAllDateTimes() {
    // Convert elements with data-utc-datetime attribute
    document.querySelectorAll('[data-utc-datetime]').forEach(element => {
        const utcDateTime = element.getAttribute('data-utc-datetime');
        if (utcDateTime && utcDateTime !== '') {
            const formatType = element.getAttribute('data-format-type') || 'full';
            
            let formattedDateTime;
            switch (formatType) {
                case 'date':
                    formattedDateTime = formatLocalDate(utcDateTime);
                    break;
                case 'time':
                    formattedDateTime = formatLocalTime(utcDateTime);
                    break;
                case 'full':
                default:
                    formattedDateTime = formatLocalDateTime(utcDateTime, {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                    break;
            }
            
            element.textContent = formattedDateTime;
            element.setAttribute('title', `Local time: ${formattedDateTime}`);
        }
    });
    
    // Convert elements with data-utc-date attribute (date only)
    document.querySelectorAll('[data-utc-date]').forEach(element => {
        const utcDate = element.getAttribute('data-utc-date');
        if (utcDate && utcDate !== '') {
            const formattedDate = formatLocalDate(utcDate);
            element.textContent = formattedDate;
            element.setAttribute('title', `Local date: ${formattedDate}`);
        }
    });
    
    // Convert elements with data-utc-time attribute (time only)
    document.querySelectorAll('[data-utc-time]').forEach(element => {
        const utcTime = element.getAttribute('data-utc-time');
        if (utcTime && utcTime !== '') {
            const formattedTime = formatLocalTime(utcTime);
            element.textContent = formattedTime;
            element.setAttribute('title', `Local time: ${formattedTime}`);
        }
    });
}

// Function to show timezone info
function displayTimezoneInfo() {
    const timezone = getUserTimezone();
    const timezoneElements = document.querySelectorAll('.user-timezone');
    timezoneElements.forEach(element => {
        element.textContent = timezone;
    });
}

// Auto-convert on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DateTime utils loading...');
    // Wait a bit for content to load then convert
    setTimeout(function() {
        console.log('Converting datetime elements...');
        convertAllDateTimes();
        displayTimezoneInfo();
        console.log('DateTime conversion complete');
    }, 100);
});

// Export functions for global use
window.DateTimeUtils = {
    formatLocalDateTime,
    formatLocalDate,
    formatLocalTime,
    getUserTimezone,
    convertAllDateTimes,
    displayTimezoneInfo
};