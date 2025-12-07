// Update unread notifications badge
async function updateNotificationBadge() {
    try {
        const response = await fetch('/api/v1/notifications/unread-count', {
            credentials: 'include'
        });

        if (response.ok) {
            const data = await response.json();
            const badge = document.getElementById('unread-badge');

            if (badge) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count > 9 ? '9+' : data.unread_count;
                    badge.style.display = 'block';
                } else {
                    badge.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('Error updating notification badge:', error);
    }
}

// Update on page load
document.addEventListener('DOMContentLoaded', updateNotificationBadge);

// Update every 30 seconds
setInterval(updateNotificationBadge, 30000);
