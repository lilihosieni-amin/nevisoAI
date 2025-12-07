-- =============================================
-- Neviso Database Complete Schema
-- =============================================
-- This file contains the complete database schema
-- Based on latest models version
-- =============================================

CREATE DATABASE IF NOT EXISTS neviso_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE neviso_db;

-- =============================================
-- Users Table
-- =============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE NULL,
    full_name VARCHAR(100) NULL,
    university VARCHAR(100) NULL,
    field_of_study VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone_number (phone_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- User OTPs Table
-- =============================================
CREATE TABLE IF NOT EXISTS user_otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Plans Table
-- =============================================
CREATE TABLE IF NOT EXISTS plans (
    id SMALLINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    price_toman DECIMAL(10, 0) NOT NULL,
    duration_days INT NOT NULL,
    max_minutes INT NOT NULL,
    max_notebooks INT NOT NULL,
    features JSON NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- User Subscriptions Table
-- =============================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plan_id SMALLINT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    minutes_consumed INT DEFAULT 0 NOT NULL,
    status ENUM('active', 'expired', 'cancelled') DEFAULT 'active' NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Payments Table
-- =============================================
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subscription_id INT NOT NULL,
    amount_toman DECIMAL(10, 0) NOT NULL,
    payment_gateway VARCHAR(50) NOT NULL,
    transaction_ref_id VARCHAR(255) NOT NULL UNIQUE,
    status ENUM('pending', 'completed', 'failed') NOT NULL,
    paid_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Notebooks Table
-- =============================================
CREATE TABLE IF NOT EXISTS notebooks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Notes Table
-- =============================================
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    notebook_id INT NOT NULL,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    session_date VARCHAR(10) NULL COMMENT 'Jalali date format: YYYY/MM/DD',
    gemini_output_text LONGTEXT NULL COMMENT 'HTML note from Gemini',
    user_edited_text LONGTEXT NULL COMMENT 'HTML note edited by user',
    status ENUM('processing', 'completed', 'failed') DEFAULT 'processing' NOT NULL,
    error_type VARCHAR(50) NULL,
    error_message VARCHAR(500) NULL,
    error_detail TEXT NULL,
    retry_count SMALLINT DEFAULT 0 NOT NULL,
    last_error_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Uploads Table
-- =============================================
CREATE TABLE IF NOT EXISTS uploads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    note_id INT NOT NULL,
    user_id INT NOT NULL,
    original_file_name VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    duration_seconds INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Notifications Table
-- =============================================
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type ENUM('note_completed', 'note_failed', 'subscription_expiring', 'quota_warning') NOT NULL,
    title VARCHAR(100) NOT NULL,
    message VARCHAR(500) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    related_note_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (related_note_id) REFERENCES notes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Activity Logs Table
-- =============================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action_type VARCHAR(50) NOT NULL,
    details JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Credit Transactions Table
-- =============================================
CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subscription_id INT NULL,
    note_id INT NULL,
    transaction_type ENUM('deduct', 'refund', 'purchase', 'bonus') NOT NULL,
    amount DECIMAL(10, 2) NOT NULL COMMENT 'Minutes',
    balance_before DECIMAL(10, 2) NOT NULL,
    balance_after DECIMAL(10, 2) NOT NULL,
    description VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE SET NULL,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Processing Queue Table
-- =============================================
CREATE TABLE IF NOT EXISTS processing_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    note_id INT NOT NULL UNIQUE,
    user_id INT NOT NULL,
    priority SMALLINT DEFAULT 0 NOT NULL COMMENT '0=normal, 1=premium, 2=urgent',
    status ENUM('waiting', 'processing', 'completed', 'failed') DEFAULT 'waiting' NOT NULL,
    retry_count SMALLINT DEFAULT 0 NOT NULL,
    estimated_credits DECIMAL(10, 2) NULL COMMENT 'Estimated credits required',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_message TEXT NULL,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- User Quotas Table
-- =============================================
CREATE TABLE IF NOT EXISTS user_quotas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    daily_upload_count INT DEFAULT 0 NOT NULL,
    last_upload_at TIMESTAMP NULL,
    concurrent_processing SMALLINT DEFAULT 0 NOT NULL,
    total_minutes_used_today DECIMAL(10, 2) DEFAULT 0 NOT NULL,
    last_reset_at DATE DEFAULT (CURRENT_DATE),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- Insert Sample Data (Plans)
-- =============================================
INSERT INTO plans (name, price_toman, duration_days, max_minutes, max_notebooks, features, is_active) VALUES
('رایگان', 0, 30, 10, 3, '["تبدیل تا 10 دقیقه صوت", "حداکثر 3 دفترچه"]', TRUE),
('برنزی', 99000, 30, 120, 10, '["تبدیل تا 120 دقیقه صوت", "حداکثر 10 دفترچه", "پشتیبانی ایمیلی"]', TRUE),
('نقره‌ای', 199000, 30, 300, 25, '["تبدیل تا 300 دقیقه صوت", "حداکثر 25 دفترچه", "پشتیبانی ایمیلی و تلفنی"]', TRUE),
('طلایی', 349000, 30, 600, 50, '["تبدیل تا 600 دقیقه صوت", "حداکثر 50 دفترچه", "پشتیبانی اولویت‌دار", "امکان دانلود PDF"]', TRUE)
ON DUPLICATE KEY UPDATE name=name;


-- =============================================
-- Create Indexes for Performance
-- =============================================
CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_notebooks_user_id ON notebooks(user_id);
CREATE INDEX idx_notes_notebook_id ON notes(notebook_id);
CREATE INDEX idx_notes_user_id ON notes(user_id);
CREATE INDEX idx_notes_status ON notes(status);
CREATE INDEX idx_notes_is_active ON notes(is_active);
CREATE INDEX idx_uploads_note_id ON uploads(note_id);
CREATE INDEX idx_uploads_user_id ON uploads(user_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX idx_processing_queue_status ON processing_queue(status);
CREATE INDEX idx_processing_queue_user_id ON processing_queue(user_id);

-- =============================================
-- End of Schema
-- =============================================
