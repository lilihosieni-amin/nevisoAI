// Common utilities (NO MOCK DATA - uses API calls)

// --- Utility Functions ---
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function setupSidebarToggle() {
    const toggleBtn = document.getElementById('sidebar-toggle');
    const appContainer = document.querySelector('.app-container');
    if (!toggleBtn || !appContainer) return;

    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        appContainer.classList.add('sidebar-collapsed');
    }

    toggleBtn.addEventListener('click', () => {
        appContainer.classList.toggle('sidebar-collapsed');
        const isCollapsed = appContainer.classList.contains('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
    });
}

function setupThemeSwitcher() {
    // Apply saved theme on page load
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.dataset.theme = savedTheme;

    // Setup theme toggle if exists (for pages with theme switcher)
    const themeToggle = document.getElementById('theme-toggle-checkbox');
    if (themeToggle) {
        themeToggle.checked = (savedTheme === 'dark');

        themeToggle.addEventListener('change', () => {
            const newTheme = themeToggle.checked ? 'dark' : 'light';
            localStorage.setItem('theme', newTheme);
            document.body.dataset.theme = newTheme;
        });
    }

    // Setup theme switcher button if exists (sidebar button)
    const themeSwitcher = document.getElementById('theme-switcher');
    if (themeSwitcher) {
        themeSwitcher.addEventListener('click', () => {
            const currentTheme = document.body.dataset.theme;
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', newTheme);
            document.body.dataset.theme = newTheme;
        });
    }
}

// Date formatting - return date as-is (Jalali date stored in YYYY/MM/DD format)
function formatDate(dateString) {
    if (!dateString) return '';
    return dateString;  // Return as-is, no conversion
}

// Show loading state
function showLoading(element, text = 'در حال بارگذاری...') {
    if (!element) return;
    element.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-secondary);">${text}</div>`;
}

// Show error message
function showError(element, message = 'خطایی رخ داده است') {
    if (!element) return;
    element.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--error);">${message}</div>`;
}

// Download blob as file
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// Toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 16px 24px;
        background: var(--bg-card);
        border: var(--border-width) solid var(--border-color);
        border-radius: var(--radius-sm);
        box-shadow: var(--shadow-hard);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;

    if (type === 'error') {
        toast.style.borderColor = 'var(--error)';
        toast.style.color = 'var(--error)';
    } else if (type === 'success') {
        toast.style.borderColor = 'var(--success)';
        toast.style.color = 'var(--success)';
    }

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// Add animation keyframes if not already present
if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}
