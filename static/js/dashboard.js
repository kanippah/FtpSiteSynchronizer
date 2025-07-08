// Dashboard JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initializeDashboard();
    
    // Auto-refresh every 30 seconds
    setInterval(refreshDashboard, 30000);
});

function initializeDashboard() {
    // Load dashboard statistics
    loadDashboardStats();
    
    // Initialize charts
    initializeCharts();
    
    // Load recent activity
    loadRecentActivity();
}

function loadDashboardStats() {
    fetch('/api/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error loading dashboard stats:', data.error);
                return;
            }
            
            updateJobStatsChart(data.job_stats);
            updateActivityChart(data.daily_stats);
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
        });
}

function initializeCharts() {
    // Job Status Chart
    const jobStatusCtx = document.getElementById('jobStatusChart');
    if (jobStatusCtx) {
        window.jobStatusChart = new Chart(jobStatusCtx, {
            type: 'doughnut',
            data: {
                labels: ['Pending', 'Running', 'Completed', 'Failed'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#ffc107', // warning
                        '#0dcaf0', // info
                        '#198754', // success
                        '#dc3545'  // danger
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    // Activity Chart
    const activityCtx = document.getElementById('activityChart');
    if (activityCtx) {
        window.activityChart = new Chart(activityCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Completed',
                    data: [],
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.1)',
                    tension: 0.1
                }, {
                    label: 'Failed',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

function updateJobStatsChart(stats) {
    if (window.jobStatusChart) {
        window.jobStatusChart.data.datasets[0].data = [
            stats.pending || 0,
            stats.running || 0,
            stats.completed || 0,
            stats.failed || 0
        ];
        window.jobStatusChart.update();
    }
}

function updateActivityChart(dailyStats) {
    if (window.activityChart) {
        const labels = [];
        const completedData = [];
        const failedData = [];
        
        // Get last 7 days
        const today = new Date();
        for (let i = 6; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            const dateString = date.toISOString().split('T')[0];
            
            labels.push(dateString);
            
            if (dailyStats[dateString]) {
                completedData.push(dailyStats[dateString].completed || 0);
                failedData.push(dailyStats[dateString].failed || 0);
            } else {
                completedData.push(0);
                failedData.push(0);
            }
        }
        
        window.activityChart.data.labels = labels;
        window.activityChart.data.datasets[0].data = completedData;
        window.activityChart.data.datasets[1].data = failedData;
        window.activityChart.update();
    }
}

function loadRecentActivity() {
    // This would typically load recent activity from an API
    // For now, we'll just update the existing content
    const activityList = document.getElementById('recentActivity');
    if (activityList) {
        // Activity is already loaded from the server
        // We could add real-time updates here
    }
}

function refreshDashboard() {
    // Refresh dashboard data
    loadDashboardStats();
    
    // Update timestamp
    const lastUpdated = document.getElementById('lastUpdated');
    if (lastUpdated) {
        lastUpdated.textContent = new Date().toLocaleString();
    }
}

// Helper functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function getStatusBadgeClass(status) {
    const statusClasses = {
        'pending': 'status-pending',
        'running': 'status-running',
        'completed': 'status-completed',
        'failed': 'status-failed'
    };
    
    return statusClasses[status] || 'status-pending';
}

// Export functions for use in other scripts
window.dashboardUtils = {
    formatBytes,
    formatDateTime,
    getStatusBadgeClass,
    refreshDashboard
};
