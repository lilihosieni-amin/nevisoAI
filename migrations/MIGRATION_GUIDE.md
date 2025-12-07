# 📋 راهنمای Migration - سیستم پرداخت و اعتبار

## 🐛 مشکل Foreign Key Incompatibility

اگر با این خطا مواجه شدید:
```
Referencing column 'user_id' and referenced column 'id' in foreign key constraint are incompatible.
```

این به این خاطره که نوع داده `user_id` با نوع داده `users.id` مطابقت نداره.

---

## ✅ راه‌حل: استفاده از Migration نسخه 2

### روش 1: Migration خودکار (پیشنهادی)

این migration به صورت خودکار نوع داده `users.id` رو تشخیص میده و جداول رو با همون نوع می‌سازه:

```bash
mysql -u root -p neviso < migrations/add_credit_and_queue_tables_v2.sql
```

### روش 2: بررسی دستی و Migration

#### مرحله 1: بررسی نوع داده users.id

```sql
-- وارد MySQL شوید
mysql -u root -p neviso

-- بررسی نوع داده
DESCRIBE users;
```

خروجی مثل این خواهد بود:
```
+------------------+-------------+------+-----+---------+----------------+
| Field            | Type        | Null | Key | Default | Extra          |
+------------------+-------------+------+-----+---------+----------------+
| id               | int         | NO   | PRI | NULL    | auto_increment |
| phone_number     | varchar(20) | NO   | UNI | NULL    |                |
...
```

یا:
```
| id               | int unsigned| NO   | PRI | NULL    | auto_increment |
```

یا:
```
| id               | bigint      | NO   | PRI | NULL    | auto_increment |
```

#### مرحله 2: استفاده از Migration مناسب

##### اگر `int` بود:
```bash
mysql -u root -p neviso < migrations/add_credit_and_queue_tables_v2.sql
```

##### اگر `int unsigned` بود:
```bash
# ابتدا migration را edit کنید و تمام `INT` را به `INT UNSIGNED` تبدیل کنید
# یا از این دستور استفاده کنید:
sed 's/user_id INT/user_id INT UNSIGNED/g' migrations/add_credit_and_queue_tables_v2.sql | mysql -u root -p neviso
```

##### اگر `bigint` بود:
```bash
# تمام `INT` را به `BIGINT` تبدیل کنید
sed 's/user_id INT/user_id BIGINT/g' migrations/add_credit_and_queue_tables_v2.sql | mysql -u root -p neviso
```

---

## 🔍 عیب‌یابی

### خطا: Table already exists

اگر جداول قبلاً ساخته شده بودند:

```sql
-- حذف جداول (احتیاط: داده‌ها پاک می‌شوند!)
DROP TABLE IF EXISTS credit_transactions;
DROP TABLE IF EXISTS processing_queue;
DROP TABLE IF EXISTS user_quotas;

-- سپس migration را دوباره اجرا کنید
```

### خطا: Foreign key constraint fails

اگر foreign key ساخته نمیشه:

```sql
-- بررسی محدودیت‌های موجود
SELECT * FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'neviso'
AND REFERENCED_TABLE_NAME IS NOT NULL;

-- حذف محدودیت‌های قدیمی
ALTER TABLE credit_transactions DROP FOREIGN KEY credit_transactions_ibfk_1;
-- سپس migration را دوباره اجرا کنید
```

### بررسی موفقیت Migration

```sql
-- بررسی جداول
SHOW TABLES LIKE '%credit%';
SHOW TABLES LIKE '%queue%';
SHOW TABLES LIKE '%quota%';

-- بررسی ساختار
DESCRIBE credit_transactions;
DESCRIBE processing_queue;
DESCRIBE user_quotas;

-- بررسی foreign keys
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'neviso'
AND TABLE_NAME IN ('credit_transactions', 'processing_queue', 'user_quotas')
AND REFERENCED_TABLE_NAME IS NOT NULL;
```

خروجی صحیح:
```
credit_transactions | user_id | credit_transactions_ibfk_1 | users | id
credit_transactions | subscription_id | credit_transactions_ibfk_2 | user_subscriptions | id
credit_transactions | note_id | credit_transactions_ibfk_3 | notes | id
processing_queue | note_id | processing_queue_ibfk_1 | notes | id
processing_queue | user_id | processing_queue_ibfk_2 | users | id
user_quotas | user_id | user_quotas_ibfk_1 | users | id
```

---

## 📊 ساختار جداول ایجاد شده

### 1. credit_transactions
```sql
id                 BIGINT           (PK, AUTO_INCREMENT)
user_id            INT/BIGINT       (FK → users.id)
subscription_id    INT              (FK → user_subscriptions.id)
note_id            INT              (FK → notes.id)
transaction_type   ENUM             (deduct, refund, purchase, bonus)
amount             DECIMAL(10,2)    (دقیقه)
balance_before     DECIMAL(10,2)
balance_after      DECIMAL(10,2)
description        VARCHAR(500)
created_at         TIMESTAMP
```

### 2. processing_queue
```sql
id                 BIGINT           (PK, AUTO_INCREMENT)
note_id            INT              (FK → notes.id, UNIQUE)
user_id            INT/BIGINT       (FK → users.id)
priority           SMALLINT         (0=normal, 1=premium, 2=urgent)
status             ENUM             (waiting, processing, completed, failed)
retry_count        SMALLINT
estimated_credits  DECIMAL(10,2)
added_at           TIMESTAMP
started_at         TIMESTAMP
completed_at       TIMESTAMP
error_message      TEXT
```

### 3. user_quotas
```sql
id                      INT          (PK, AUTO_INCREMENT)
user_id                 INT/BIGINT   (FK → users.id, UNIQUE)
daily_upload_count      INT
last_upload_at          TIMESTAMP
concurrent_processing   SMALLINT
total_minutes_used_today DECIMAL(10,2)
last_reset_at           DATE
```

---

## 🔄 Rollback (برگشت به قبل)

اگر مشکلی پیش اومد و خواستید تغییرات رو برگردونید:

```sql
-- حذف جداول جدید
DROP TABLE IF EXISTS credit_transactions;
DROP TABLE IF EXISTS processing_queue;
DROP TABLE IF EXISTS user_quotas;

-- برگرداندن تغییرات payments
ALTER TABLE payments
MODIFY COLUMN transaction_ref_id VARCHAR(255);

-- برگرداندن تغییرات uploads (اگر اضافه شده بود)
ALTER TABLE uploads
DROP COLUMN IF EXISTS duration_seconds;
```

---

## ✅ چک‌لیست بعد از Migration

- [ ] هر 3 جدول ساخته شدند
- [ ] Foreign keys به درستی تنظیم شدند
- [ ] Index ها اضافه شدند
- [ ] `uploads.duration_seconds` اضافه شد
- [ ] `payments.transaction_ref_id` به 500 کاراکتر افزایش یافت
- [ ] هیچ خطایی در لاگ MySQL نیست

---

## 💡 نکات مهم

1. **Backup بگیرید**: قبل از migration حتماً از دیتابیس backup بگیرید
   ```bash
   mysqldump -u root -p neviso > backup_before_migration.sql
   ```

2. **Test Environment**: اول در محیط test migration رو اجرا کنید

3. **Data Type Compatibility**: اطمینان حاصل کنید نوع داده `user_id` با `users.id` مطابقت داره

4. **Foreign Key Constraints**: اگر جداول قبلاً وجود داشتند، اول constraint های قدیمی رو پاک کنید

5. **Character Set**: همه جداول با `utf8mb4` و collation `utf8mb4_unicode_ci` ساخته میشن (برای فارسی)

---

## 📞 پشتیبانی

اگر مشکلی پیش اومد:

1. لاگ خطا رو کامل کپی کنید
2. نتیجه `DESCRIBE users` رو بفرستید
3. نتیجه `SHOW CREATE TABLE users` رو بفرستید
4. نسخه MySQL رو بفرستید: `SELECT VERSION();`

---

## 🎉 موفقیت

اگر migration موفق بود، پیام زیر رو خواهید دید:
```
✓ Migration completed successfully!
```

و جداول جدید در `SHOW TABLES` قابل مشاهده خواهند بود.
