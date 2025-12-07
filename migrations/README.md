# 🚀 راهنمای سریع Migration

## ⚡ روش سریع (پیشنهادی)

```bash
# اجرای خودکار migration
python scripts/run_migration.py
```

این script:
- ✅ به صورت خودکار نوع داده `users.id` را تشخیص می‌دهد
- ✅ جداول را با نوع داده صحیح می‌سازد
- ✅ Foreign key ها را به درستی تنظیم می‌کند
- ✅ نتیجه را verify می‌کند

---

## 🔧 روش دستی

### 1. بررسی نوع داده users.id

```sql
mysql -u root -p neviso -e "DESCRIBE users;"
```

### 2. اجرای migration

```bash
mysql -u root -p neviso < migrations/add_credit_and_queue_tables_v2.sql
```

---

## ❓ مشکل Foreign Key

اگر با این خطا مواجه شدید:
```
Referencing column 'user_id' and referenced column 'id' in foreign key constraint are incompatible
```

**راه‌حل:**
```bash
# استفاده از migration خودکار
python scripts/run_migration.py
```

یا مراجعه به: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

---

## ✅ بررسی موفقیت

```bash
mysql -u root -p neviso -e "SHOW TABLES LIKE '%credit%';"
mysql -u root -p neviso -e "SHOW TABLES LIKE '%queue%';"
mysql -u root -p neviso -e "SHOW TABLES LIKE '%quota%';"
```

باید 3 جدول ببینید:
- `credit_transactions`
- `processing_queue`
- `user_quotas`

---

## 📚 مستندات کامل

- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - راهنمای کامل migration
- [../PAYMENT_CREDIT_SYSTEM.md](../PAYMENT_CREDIT_SYSTEM.md) - مستندات سیستم
- [../QUICKSTART_GUIDE.md](../QUICKSTART_GUIDE.md) - راهنمای سریع شروع
