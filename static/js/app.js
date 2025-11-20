// ====================================
// Twitch Stream Downloader - App.js
// Utilities and Common Functions
// ====================================

// Theme Management
const ThemeManager = {
    // Initialize theme from localStorage or system preference
    init() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (prefersDark ? 'dark' : 'light');
        this.setTheme(theme);
        
        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    },
    
    // Set theme
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.updateToggleIcon(theme);
    },
    
    // Toggle between light and dark
    toggle() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },
    
    // Update toggle button icon
    updateToggleIcon(theme) {
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            toggleBtn.innerHTML = theme === 'dark' 
                ? '<i class="fas fa-sun"></i>' 
                : '<i class="fas fa-moon"></i>';
        }
    }
};

// Notification System
const Notifications = {
    // Show a toast notification
    show(message, type = 'info') {
        const toast = $('#notificationToast');
        const toastBody = $('#toastMessage');
        const toastHeader = toast.find('.toast-header i');
        
        // Remove all previous classes
        toastHeader.removeClass().addClass('fas me-2');
        
        // Set icon based on type
        const icons = {
            'success': 'fa-check-circle text-success',
            'error': 'fa-exclamation-circle text-danger',
            'warning': 'fa-exclamation-triangle text-warning',
            'info': 'fa-info-circle text-primary'
        };
        
        toastHeader.addClass(icons[type] || icons.info);
        toastBody.text(message);
        
        const bsToast = new bootstrap.Toast(toast[0], {
            autohide: true,
            delay: type === 'error' ? 5000 : 3000
        });
        bsToast.show();
    }
};

// Formatting Utilities
const Format = {
    // Format file size in bytes to human-readable format
    fileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },
    
    // Format duration in seconds to HH:MM:SS
    duration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        const parts = [];
        if (hours > 0) parts.push(String(hours).padStart(2, '0'));
        parts.push(String(minutes).padStart(2, '0'));
        parts.push(String(secs).padStart(2, '0'));
        
        return parts.join(':');
    },
    
    // Format date to relative time (e.g., "2 hours ago")
    relativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 60) return 'À l\'instant';
        if (diffInSeconds < 3600) return `Il y a ${Math.floor(diffInSeconds / 60)} minutes`;
        if (diffInSeconds < 86400) return `Il y a ${Math.floor(diffInSeconds / 3600)} heures`;
        if (diffInSeconds < 604800) return `Il y a ${Math.floor(diffInSeconds / 86400)} jours`;
        
        return date.toLocaleDateString('fr-FR');
    },
    
    // Truncate text with ellipsis
    truncate(text, maxLength = 50) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
};

// API Helper
const API = {
    // Generic API call wrapper
    async call(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },
    
    // GET request
    async get(endpoint) {
        return this.call(endpoint, { method: 'GET' });
    },
    
    // POST request
    async post(endpoint, data) {
        return this.call(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // DELETE request
    async delete(endpoint, data) {
        return this.call(endpoint, {
            method: 'DELETE',
            body: JSON.stringify(data)
        });
    }
};

// Loading State Manager
const LoadingState = {
    // Show loading on button
    show(button, text = 'Chargement...') {
        const $btn = $(button);
        $btn.data('original-html', $btn.html());
        $btn.prop('disabled', true).html(`<i class="fas fa-spinner fa-spin"></i> ${text}`);
    },
    
    // Hide loading on button
    hide(button) {
        const $btn = $(button);
        const originalHtml = $btn.data('original-html');
        if (originalHtml) {
            $btn.prop('disabled', false).html(originalHtml);
        }
    }
};

// URL Validator
const URLValidator = {
    // Validate Twitch URL
    isTwitchURL(url) {
        const pattern = /^https?:\/\/(www\.)?twitch\.tv\/[a-zA-Z0-9_]+\/?$/;
        return pattern.test(url);
    },
    
    // Extract streamer name from Twitch URL
    extractStreamerName(url) {
        const match = url.match(/twitch\.tv\/([a-zA-Z0-9_]+)/);
        return match ? match[1] : null;
    },
    
    // Auto-complete URL
    completeURL(input) {
        // If already a full URL, return as is
        if (input.startsWith('http')) return input;
        
        // If just username, create full URL
        return `https://www.twitch.tv/${input}`;
    }
};

// Auto-refresh Manager (for polling updates)
const AutoRefresh = {
    intervals: {},
    
    // Start auto-refresh for a given key
    start(key, callback, interval = 30000) {
        this.stop(key); // Clear any existing interval
        this.intervals[key] = setInterval(callback, interval);
        callback(); // Run immediately
    },
    
    // Stop auto-refresh for a given key
    stop(key) {
        if (this.intervals[key]) {
            clearInterval(this.intervals[key]);
            delete this.intervals[key];
        }
    },
    
    // Stop all auto-refreshes
    stopAll() {
        Object.keys(this.intervals).forEach(key => this.stop(key));
    }
};

// Active Navigation Highlighter
function updateActiveNav() {
    const currentPath = window.location.pathname;
    $('.nav-link').removeClass('active');
    
    $('.nav-link').each(function() {
        const href = $(this).attr('href');
        if (href === currentPath || (currentPath === '/' && href === '/')) {
            $(this).addClass('active');
        }
    });
}

// Initialize on DOM ready
$(document).ready(function() {
    // Initialize theme
    ThemeManager.init();
    
    // Setup theme toggle button
    $('#themeToggle').on('click', function() {
        ThemeManager.toggle();
    });
    
    // Update active navigation
    updateActiveNav();
    
    // Add smooth scrolling to all links
    $('a[href^="#"]').on('click', function(e) {
        const target = $(this.getAttribute('href'));
        if (target.length) {
            e.preventDefault();
            $('html, body').stop().animate({
                scrollTop: target.offset().top - 100
            }, 500);
        }
    });
    
    // Auto-dismiss alerts after 5 seconds
    $('.alert:not(.alert-permanent)').delay(5000).fadeOut('slow');
    
    // Form validation feedback
    $('form').on('submit', function(e) {
        if (!this.checkValidity()) {
            e.preventDefault();
            e.stopPropagation();
        }
        $(this).addClass('was-validated');
    });
    
    // Add ripple effect to buttons
    $('.btn').on('click', function(e) {
        const ripple = $('<span class="ripple"></span>');
        $(this).append(ripple);
        
        const x = e.pageX - $(this).offset().left;
        const y = e.pageY - $(this).offset().top;
        
        ripple.css({
            left: x + 'px',
            top: y + 'px'
        }).addClass('active');
        
        setTimeout(() => ripple.remove(), 600);
    });
});

// Cleanup on page unload
$(window).on('beforeunload', function() {
    AutoRefresh.stopAll();
});

// Export for use in other scripts
window.TwitchDownloader = {
    ThemeManager,
    Notifications,
    Format,
    API,
    LoadingState,
    URLValidator,
    AutoRefresh
};
