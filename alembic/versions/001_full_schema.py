"""Full database schema

Revision ID: 001_full_schema
Revises:
Create Date: 2025-12-02

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_full_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: Tables are created in order of dependencies
    # This migration assumes a fresh database

    # 1. users table (no dependencies)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `users` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `phone_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
            `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `full_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `university` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `field_of_study` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `phone_number` (`phone_number`),
            UNIQUE KEY `email` (`email`),
            KEY `idx_phone` (`phone_number`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 2. plans table (no dependencies)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `plans` (
            `id` smallint unsigned NOT NULL AUTO_INCREMENT,
            `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
            `price_toman` decimal(10,0) NOT NULL,
            `duration_days` int NOT NULL,
            `max_minutes` int unsigned NOT NULL,
            `max_notebooks` int unsigned NOT NULL,
            `features` json DEFAULT NULL,
            `is_active` tinyint(1) NOT NULL DEFAULT '1',
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 3. notebooks table (depends on users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `notebooks` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `title` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_user_notebook` (`user_id`,`created_at`),
            CONSTRAINT `notebooks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 4. user_subscriptions table (depends on users, plans)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `user_subscriptions` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `plan_id` smallint unsigned NOT NULL,
            `start_date` timestamp NOT NULL,
            `end_date` timestamp NOT NULL,
            `minutes_consumed` int unsigned NOT NULL DEFAULT '0',
            `status` enum('active','expired','cancelled') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
            PRIMARY KEY (`id`),
            KEY `plan_id` (`plan_id`),
            KEY `idx_user_status` (`user_id`,`status`,`end_date`),
            CONSTRAINT `user_subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
            CONSTRAINT `user_subscriptions_ibfk_2` FOREIGN KEY (`plan_id`) REFERENCES `plans` (`id`) ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 5. notes table (depends on notebooks, users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `notes` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `notebook_id` int unsigned NOT NULL,
            `user_id` int unsigned NOT NULL,
            `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
            `session_date` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Jalali date format: YYYY/MM/DD',
            `gemini_output_text` longtext COLLATE utf8mb4_unicode_ci,
            `user_edited_text` longtext COLLATE utf8mb4_unicode_ci,
            `status` enum('processing','completed','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'processing',
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            `error_message` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `error_detail` text COLLATE utf8mb4_unicode_ci,
            `retry_count` smallint NOT NULL DEFAULT '0',
            `last_error_at` timestamp NULL DEFAULT NULL,
            `is_active` tinyint(1) NOT NULL DEFAULT '1',
            `error_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY `idx_notebook` (`notebook_id`,`created_at`),
            KEY `idx_user_note` (`user_id`,`status`),
            CONSTRAINT `notes_ibfk_1` FOREIGN KEY (`notebook_id`) REFERENCES `notebooks` (`id`) ON DELETE CASCADE,
            CONSTRAINT `notes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 6. uploads table (depends on notes, users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `uploads` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `note_id` int unsigned NOT NULL,
            `user_id` int unsigned NOT NULL,
            `original_file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
            `storage_path` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
            `file_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
            `file_size_bytes` bigint unsigned NOT NULL,
            `duration_seconds` int unsigned DEFAULT NULL,
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `user_id` (`user_id`),
            KEY `idx_note_upload` (`note_id`),
            CONSTRAINT `uploads_ibfk_1` FOREIGN KEY (`note_id`) REFERENCES `notes` (`id`) ON DELETE CASCADE,
            CONSTRAINT `uploads_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 7. notifications table (depends on users, notes)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `notifications` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `type` enum('note_completed','note_failed','subscription_expiring','quota_warning') COLLATE utf8mb4_unicode_ci NOT NULL,
            `title` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
            `message` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
            `is_read` tinyint(1) NOT NULL DEFAULT '0',
            `related_note_id` int unsigned DEFAULT NULL,
            `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `user_id` (`user_id`),
            KEY `related_note_id` (`related_note_id`),
            CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
            CONSTRAINT `notifications_ibfk_2` FOREIGN KEY (`related_note_id`) REFERENCES `notes` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 8. payments table (depends on users, user_subscriptions)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `payments` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `subscription_id` int unsigned NOT NULL,
            `amount_toman` decimal(10,0) NOT NULL,
            `payment_gateway` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
            `transaction_ref_id` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `status` enum('pending','completed','failed') COLLATE utf8mb4_unicode_ci NOT NULL,
            `paid_at` timestamp NULL DEFAULT NULL,
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `transaction_ref_id` (`transaction_ref_id`),
            KEY `subscription_id` (`subscription_id`),
            KEY `idx_transaction` (`transaction_ref_id`),
            KEY `idx_user_payment` (`user_id`,`status`),
            CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
            CONSTRAINT `payments_ibfk_2` FOREIGN KEY (`subscription_id`) REFERENCES `user_subscriptions` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 9. user_otps table (depends on users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `user_otps` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `otp_code` varchar(6) COLLATE utf8mb4_unicode_ci NOT NULL,
            `expires_at` timestamp NOT NULL,
            `is_used` tinyint(1) NOT NULL DEFAULT '0',
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_user_otp` (`user_id`,`otp_code`,`is_used`),
            CONSTRAINT `user_otps_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 10. activity_logs table (depends on users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `activity_logs` (
            `id` bigint unsigned NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned DEFAULT NULL,
            `action_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
            `details` json DEFAULT NULL,
            `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `user_agent` text COLLATE utf8mb4_unicode_ci,
            `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_user_action` (`user_id`,`action_type`,`created_at`),
            CONSTRAINT `activity_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 11. credit_transactions table (depends on users, user_subscriptions, notes)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `credit_transactions` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `subscription_id` int unsigned DEFAULT NULL,
            `note_id` int unsigned DEFAULT NULL,
            `transaction_type` enum('deduct','refund','purchase','bonus') COLLATE utf8mb4_unicode_ci NOT NULL,
            `amount` decimal(10,2) NOT NULL COMMENT 'Amount in minutes',
            `balance_before` decimal(10,2) NOT NULL,
            `balance_after` decimal(10,2) NOT NULL,
            `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_user_created` (`user_id`,`created_at`),
            KEY `idx_note` (`note_id`),
            KEY `idx_subscription` (`subscription_id`),
            KEY `idx_type` (`transaction_type`),
            CONSTRAINT `credit_transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
            CONSTRAINT `credit_transactions_ibfk_2` FOREIGN KEY (`subscription_id`) REFERENCES `user_subscriptions` (`id`) ON DELETE SET NULL,
            CONSTRAINT `credit_transactions_ibfk_3` FOREIGN KEY (`note_id`) REFERENCES `notes` (`id`) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log of all credit transactions'
    """)

    # 12. processing_queue table (depends on notes, users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `processing_queue` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `note_id` int unsigned NOT NULL,
            `user_id` int unsigned NOT NULL,
            `priority` smallint NOT NULL DEFAULT '0' COMMENT '0=normal, 1=premium, 2=urgent',
            `status` enum('waiting','processing','completed','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'waiting',
            `retry_count` smallint NOT NULL DEFAULT '0',
            `estimated_credits` decimal(10,2) DEFAULT NULL COMMENT 'Estimated credits required',
            `added_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            `started_at` timestamp NULL DEFAULT NULL,
            `completed_at` timestamp NULL DEFAULT NULL,
            `error_message` text COLLATE utf8mb4_unicode_ci,
            PRIMARY KEY (`id`),
            UNIQUE KEY `note_id` (`note_id`),
            KEY `idx_status_priority` (`status`,`priority`),
            KEY `idx_user` (`user_id`),
            KEY `idx_added_at` (`added_at`),
            KEY `idx_started_at` (`started_at`),
            CONSTRAINT `processing_queue_ibfk_1` FOREIGN KEY (`note_id`) REFERENCES `notes` (`id`) ON DELETE CASCADE,
            CONSTRAINT `processing_queue_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Processing queue for notes'
    """)

    # 13. user_quotas table (depends on users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `user_quotas` (
            `id` int NOT NULL AUTO_INCREMENT,
            `user_id` int unsigned NOT NULL,
            `daily_upload_count` int NOT NULL DEFAULT '0',
            `last_upload_at` timestamp NULL DEFAULT NULL,
            `concurrent_processing` smallint NOT NULL DEFAULT '0',
            `total_minutes_used_today` decimal(10,2) NOT NULL DEFAULT '0.00',
            `last_reset_at` date DEFAULT (curdate()),
            PRIMARY KEY (`id`),
            UNIQUE KEY `user_id` (`user_id`),
            KEY `idx_user` (`user_id`),
            KEY `idx_last_reset` (`last_reset_at`),
            CONSTRAINT `user_quotas_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User rate limiting and quotas'
    """)

    # 14. chat_sessions table (depends on notebooks, users)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `chat_sessions` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `notebook_id` int unsigned NOT NULL,
            `user_id` int unsigned NOT NULL,
            `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `notebook_id` (`notebook_id`),
            KEY `user_id` (`user_id`),
            CONSTRAINT `chat_sessions_ibfk_1` FOREIGN KEY (`notebook_id`) REFERENCES `notebooks` (`id`) ON DELETE CASCADE,
            CONSTRAINT `chat_sessions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # 15. chat_messages table (depends on chat_sessions)
    op.execute("""
        CREATE TABLE IF NOT EXISTS `chat_messages` (
            `id` int unsigned NOT NULL AUTO_INCREMENT,
            `session_id` int unsigned NOT NULL,
            `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
            `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `session_id` (`session_id`),
            CONSTRAINT `chat_messages_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def downgrade() -> None:
    # Drop tables in reverse order of dependencies
    op.execute("DROP TABLE IF EXISTS `chat_messages`")
    op.execute("DROP TABLE IF EXISTS `chat_sessions`")
    op.execute("DROP TABLE IF EXISTS `user_quotas`")
    op.execute("DROP TABLE IF EXISTS `processing_queue`")
    op.execute("DROP TABLE IF EXISTS `credit_transactions`")
    op.execute("DROP TABLE IF EXISTS `activity_logs`")
    op.execute("DROP TABLE IF EXISTS `user_otps`")
    op.execute("DROP TABLE IF EXISTS `payments`")
    op.execute("DROP TABLE IF EXISTS `notifications`")
    op.execute("DROP TABLE IF EXISTS `uploads`")
    op.execute("DROP TABLE IF EXISTS `notes`")
    op.execute("DROP TABLE IF EXISTS `user_subscriptions`")
    op.execute("DROP TABLE IF EXISTS `notebooks`")
    op.execute("DROP TABLE IF EXISTS `plans`")
    op.execute("DROP TABLE IF EXISTS `users`")
