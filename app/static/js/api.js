// API Client for Neviso

const API_BASE_URL = '/api/v1';

// این تابع دیگر برای لاگین نیاز نیست، فقط برای خروج استفاده می‌شود
function clearAuthToken() {
    document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
}

// تابع اصلی برای ارسال درخواست‌ها
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    // **نکته**: مرورگر به صورت خودکار کوکی HttpOnly را ارسال می‌کند
    // نیازی به تنظیم هدر Authorization در اینجا نیست.

    const config = { ...options, headers };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

        if (response.status === 401) {
            clearAuthToken();
            window.location.href = '/login';
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }

        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

// Auth API
const authAPI = {
    requestOTP(phone_number) {
        return apiRequest('/auth/request-otp', {
            method: 'POST',
            body: JSON.stringify({ phone_number }),
        });
    },

    verifyOTP(phone_number, otp_code) {
        return apiRequest('/auth/verify-otp', {
            method: 'POST',
            body: JSON.stringify({ phone_number, otp_code }),
        });
    },

    requestEmailOTP(email) {
        return apiRequest('/auth/request-email-otp', {
            method: 'POST',
            body: JSON.stringify({ email }),
        });
    },

    verifyEmailOTP(email, otp_code) {
        return apiRequest('/auth/verify-email-otp', {
            method: 'POST',
            body: JSON.stringify({ email, otp_code }),
        });
    },

    logout() {
        clearAuthToken();
        window.location.href = '/login';
    }
};

// ... (بقیه توابع API بدون تغییر باقی می‌مانند) ...

// Plans API
const plansAPI = {
    async getAll() {
        return apiRequest('/plans/');
    }
};

// Payments API
const paymentsAPI = {
    async createCheckout(plan_id) {
        return apiRequest('/payments/create-checkout', {
            method: 'POST',
            body: JSON.stringify({ plan_id })
        });
    }
};

// Notebooks API
const notebooksAPI = {
    async getAll() {
        return apiRequest('/notebooks/');
    },
    async getById(id) {
        return apiRequest(`/notebooks/${id}`);
    },
    async create(title) {
        return apiRequest('/notebooks/', {
            method: 'POST',
            body: JSON.stringify({ title })
        });
    },
    async update(id, title) {
        return apiRequest(`/notebooks/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ title })
        });
    },
    async delete(id) {
        return apiRequest(`/notebooks/${id}`, {
            method: 'DELETE'
        });
    },
    async exportPDF(id) {
        // مرورگر کوکی را خودکار ارسال می‌کند
        const response = await fetch(`${API_BASE_URL}/export/notebooks/${id}/pdf`);
        if (!response.ok) throw new Error('Export failed');
        return response.blob();
    }
};

// Notes API
const notesAPI = {
    async getAll(notebook_id = null) {
        const query = notebook_id ? `?notebook_id=${notebook_id}` : '';
        return apiRequest(`/notes/${query}`);
    },
    async getById(id) {
        return apiRequest(`/notes/${id}`);
    },
    async create(formData, onProgress = null) {
        // Use XMLHttpRequest to support upload progress tracking
        console.log('[API] Sending POST request to /notes/');
        console.log('[API] FormData entries:');
        for (let pair of formData.entries()) {
            if (pair[1] instanceof File) {
                console.log(`[API]   ${pair[0]}: File(${pair[1].name}, ${pair[1].size} bytes)`);
            } else {
                console.log(`[API]   ${pair[0]}: ${pair[1]}`);
            }
        }

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            // Track upload progress
            if (onProgress) {
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable) {
                        const percentComplete = Math.round((event.loaded / event.total) * 100);
                        onProgress(percentComplete, event.loaded, event.total);
                    }
                });
            }

            // Handle completion
            xhr.addEventListener('load', () => {
                console.log('[API] Response status:', xhr.status);

                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const result = JSON.parse(xhr.responseText);
                        console.log('[API] Success response:', result);
                        resolve(result);
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        console.error('[API] Error response:', error);
                        reject(new Error(error.detail || 'Request failed'));
                    } catch (e) {
                        reject(new Error('Request failed'));
                    }
                }
            });

            // Handle network errors
            xhr.addEventListener('error', () => {
                console.error('[API] Network error');
                reject(new Error('Network error'));
            });

            // Handle timeout
            xhr.addEventListener('timeout', () => {
                console.error('[API] Request timeout');
                reject(new Error('Request timeout'));
            });

            // Send request
            xhr.open('POST', `${API_BASE_URL}/notes/`);
            xhr.send(formData);
        });
    },
    async update(id, data) {
        return apiRequest(`/notes/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    async delete(id) {
        return apiRequest(`/notes/${id}`, {
            method: 'DELETE'
        });
    },
    async exportPDF(id) {
        const response = await fetch(`${API_BASE_URL}/notes/${id}/export/pdf`);
        if (!response.ok) throw new Error('Export failed');
        return response.blob();
    }
};

// Users API
const usersAPI = {
    async getMe() {
        return apiRequest('/users/me');
    },
    async updateMe(data) {
        return apiRequest('/users/me', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    async getSubscription() {
        return apiRequest('/users/me/subscription');
    }
};