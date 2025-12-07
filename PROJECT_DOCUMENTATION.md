# 📚 مستندات کامل پروژه نویسو (Neviso)

## 📋 فهرست مطالب
- [معرفی پروژه](#معرفی-پروژه)
- [ساختار کلی پروژه](#ساختار-کلی-پروژه)
- [فایل‌های اصلی](#فایل‌های-اصلی)
- [مدل‌های دیتابیس](#مدل‌های-دیتابیس)
- [API Endpoints](#api-endpoints)
- [سرویس‌های Backend](#سرویس‌های-backend)
- [Worker و Celery](#worker-و-celery)
- [صفحات Frontend](#صفحات-frontend)
- [استایل‌ها و Assets](#استایل‌ها-و-assets)

---

## معرفی پروژه

**نویسو** یک پلتفرم هوشمند برای تبدیل فایل‌های صوتی، تصویری و ویدیویی کلاس‌های درسی به جزوات متنی ساختاریافته است.

### تکنولوژی‌های استفاده شده:
- **Backend**: FastAPI (Python 3.12+)
- **Database**: MySQL/MariaDB
- **ORM**: SQLAlchemy (Async)
- **Task Queue**: Celery + Redis
- **AI Engine**: Google Gemini 2.5 Flash
- **PDF Generation**: ReportLab
- **SMS**: Kavenegar
- **Payment Gateway**: ZarinPal

---

## ساختار کلی پروژه

```
neviso-backend/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # تنظیمات اصلی
│   ├── crud/            # عملیات دیتابیس
│   ├── db/              # مدل‌ها و اتصال DB
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # سرویس‌های کاربردی
│   ├── static/          # فایل‌های استاتیک
│   ├── templates/       # صفحات HTML
│   └── worker/          # Celery workers
├── migrations/          # SQL migrations
├── scripts/             # اسکریپت‌های کمکی
├── tests/               # تست‌ها
├── .env                 # تنظیمات محیطی
├── main.py              # نقطه ورود برنامه
└── requirements.txt     # وابستگی‌ها
```

---

## فایل‌های اصلی

### 📄 `app/main.py`
**نقطه ورود اصلی برنامه FastAPI**

#### محتویات:
- **ایجاد FastAPI app** با تنظیمات CORS
- **Import و register کردن تمام routers**:
  - `auth`: احراز هویت (OTP-based)
  - `plans`: پلن‌های اشتراک
  - `payments`: پرداخت‌ها
  - `notebooks`: دفترها
  - `notes`: جزوات
  - `export`: خروجی PDF
  - `users`: کاربران
  - `notifications`: اعلان‌ها
  - `credits`: مدیریت اعتبار
- **Static files mounting**: `/static`
- **Template engine setup**: Jinja2
- **Frontend routes**: صفحات HTML (login, notebooks, notes, editor, upload, profile, etc.)

---

## مدل‌های دیتابیس

### 📂 `app/db/models.py`

#### 1️⃣ **User** - کاربران
```python
- id: شناسه کاربر
- phone_number: شماره موبایل (unique)
- full_name: نام کامل
- university: دانشگاه
- field_of_study: رشته تحصیلی
- otp_code: کد OTP
- otp_expires_at: زمان انقضای OTP
- is_verified: تایید شده یا نه
- created_at, updated_at
```

#### 2️⃣ **Plan** - پلن‌های اشتراک
```python
- id: شناسه پلن
- name: نام پلن (ماهانه، سه‌ماهه، سالانه)
- price_toman: قیمت (تومان)
- duration_days: مدت زمان (روز)
- max_minutes: حداکثر دقیقه پردازش
- max_notebooks: حداکثر تعداد دفتر
- features: ویژگی‌ها (JSON)
- is_active: فعال/غیرفعال
```

#### 3️⃣ **UserSubscription** - اشتراک‌های کاربران
```python
- id: شناسه اشتراک
- user_id: کاربر
- plan_id: پلن
- start_date, end_date: تاریخ شروع و پایان
- minutes_consumed: دقیقه مصرف شده
- status: وضعیت (active/expired/cancelled)
```

#### 4️⃣ **Payment** - پرداخت‌ها
```python
- id: شناسه پرداخت
- user_id: کاربر
- subscription_id: اشتراک
- amount_toman: مبلغ
- payment_gateway: درگاه پرداخت
- transaction_ref_id: شناسه تراکنش (unique)
- status: وضعیت (pending/completed/failed)
- paid_at: زمان پرداخت
```

#### 5️⃣ **Notebook** - دفترها
```python
- id: شناسه دفتر
- user_id: کاربر
- title: عنوان دفتر
- created_at, updated_at
```

#### 6️⃣ **Note** - جزوات
```python
- id: شناسه جزوه
- notebook_id: دفتر
- user_id: کاربر
- title: عنوان
- session_date: تاریخ جلسه (شمسی، VARCHAR(10))
- gemini_output_text: خروجی Gemini (HTML)
- user_edited_text: متن ویرایش شده توسط کاربر (HTML)
- status: وضعیت (processing/completed/failed)
- error_type, error_message, error_detail: اطلاعات خطا
- retry_count: تعداد تلاش مجدد
- last_error_at: آخرین خطا
- is_active: فعال/حذف شده
- created_at, updated_at
```

#### 7️⃣ **Upload** - فایل‌های آپلود شده
```python
- id: شناسه آپلود
- note_id: جزوه
- original_filename: نام فایل اصلی
- storage_path: مسیر ذخیره
- file_type: نوع فایل (MIME type)
- file_size_bytes: حجم فایل
- uploaded_at: زمان آپلود
```

#### 8️⃣ **Notification** - اعلان‌ها
```python
- id: شناسه اعلان
- user_id: کاربر
- type: نوع (note_completed/note_failed/quota_warning/subscription_expiring)
- title: عنوان
- message: پیام
- related_note_id: جزوه مرتبط
- is_read: خوانده شده یا نه
- created_at
```

#### 9️⃣ **CreditTransaction** - تراکنش‌های اعتبار
```python
- id: شناسه تراکنش
- user_id: کاربر
- subscription_id: اشتراک
- note_id: جزوه مرتبط
- transaction_type: نوع (purchase/deduct/refund)
- amount: مقدار (دقیقه)
- balance_before, balance_after: موجودی قبل و بعد
- description: توضیحات
- created_at
```

#### 🔟 **ProcessingQueue** - صف پردازش
```python
- id: شناسه
- note_id: جزوه
- user_id: کاربر
- status: وضعیت (pending/processing/completed/failed)
- priority: اولویت
- retry_count: تعداد تلاش
- error_message: پیام خطا
- created_at, started_at, completed_at
```

---

## API Endpoints

### 🔐 `app/api/v1/auth.py` - احراز هویت

#### Endpoints:
1. **`POST /api/v1/auth/send-otp`**
   - ارسال کد OTP به شماره موبایل
   - ایجاد کاربر جدید در صورت عدم وجود
   - استفاده از سرویس Kavenegar برای ارسال SMS

2. **`POST /api/v1/auth/verify-otp`**
   - تایید کد OTP
   - ایجاد JWT token
   - ست کردن cookie با نام `access_token`

3. **`POST /api/v1/auth/logout`**
   - حذف cookie احراز هویت
   - خروج از سیستم

---

### 📦 `app/api/v1/plans.py` - پلن‌های اشتراک

#### Endpoints:
1. **`GET /api/v1/plans/`**
   - دریافت لیست پلن‌های فعال
   - نمایش قیمت، مدت زمان، ویژگی‌ها

---

### 💳 `app/api/v1/payments.py` - پرداخت‌ها

#### Endpoints:
1. **`POST /api/v1/payments/create`**
   - ایجاد درخواست پرداخت
   - ساخت subscription جدید با وضعیت pending
   - ایجاد payment record
   - دریافت لینک پرداخت از ZarinPal

2. **`GET /api/v1/payments/verify`**
   - تایید پرداخت (callback از ZarinPal)
   - فعال‌سازی اشتراک
   - ثبت تراکنش خرید اعتبار
   - ایجاد notification برای کاربر

3. **`GET /api/v1/payments/history`**
   - دریافت تاریخچه پرداخت‌های کاربر

---

### 📓 `app/api/v1/notebooks.py` - دفترها

#### Endpoints:
1. **`POST /api/v1/notebooks/`**
   - ایجاد دفتر جدید
   - محدودیت تعداد دفتر بر اساس پلن کاربر

2. **`GET /api/v1/notebooks/`**
   - دریافت لیست دفترهای کاربر
   - شامل تعداد جزوات فعال و غیر-failed هر دفتر

3. **`GET /api/v1/notebooks/{notebook_id}`**
   - دریافت اطلاعات یک دفتر
   - شامل تعداد جزوات

4. **`PUT /api/v1/notebooks/{notebook_id}`**
   - ویرایش عنوان دفتر

5. **`DELETE /api/v1/notebooks/{notebook_id}`**
   - حذف دفتر (cascade delete برای notes)

---

### 📝 `app/api/v1/notes.py` - جزوات

#### Endpoints:
1. **`POST /api/v1/notes/`**
   - آپلود فایل‌ها و ایجاد جزوه جدید
   - پشتیبانی از multi-file upload
   - ذخیره فایل‌ها در `uploads/`
   - ایجاد note با status=processing
   - **تریگر کردن Celery task**: `process_file_with_credits.delay(note_id)`

2. **`GET /api/v1/notes/`**
   - دریافت لیست جزوات کاربر
   - فیلتر بر اساس notebook_id
   - **مرتب‌سازی**: براساس `session_date` نزولی (جدیدترین اول)، سپس `created_at`
   - **فیلتر**: فقط is_active=True و status != failed

3. **`GET /api/v1/notes/{note_id}`**
   - دریافت اطلاعات کامل یک جزوه
   - شامل محتوای HTML

4. **`PUT /api/v1/notes/{note_id}`**
   - ویرایش عنوان، تاریخ یا محتوای جزوه
   - ذخیره تغییرات در `user_edited_text`

5. **`DELETE /api/v1/notes/{note_id}`**
   - حذف نرم (soft delete): `is_active = False`

6. **`GET /api/v1/notes/{note_id}/pdf`**
   - دانلود PDF یک جزوه
   - استفاده از `pdf_service` برای تولید PDF

---

### 📤 `app/api/v1/export.py` - خروجی PDF

#### Endpoints:
1. **`GET /api/v1/export/notebooks/{notebook_id}/pdf`**
   - دانلود PDF تمام جزوات یک دفتر
   - ترکیب همه notes در یک فایل PDF
   - شامل عنوان، تاریخ جلسه و محتوا

---

### 👤 `app/api/v1/users.py` - کاربران

#### Endpoints:
1. **`GET /api/v1/users/me`**
   - دریافت اطلاعات کاربر جاری

2. **`PUT /api/v1/users/me`**
   - ویرایش اطلاعات پروفایل
   - فیلدها: full_name, university, field_of_study

3. **`GET /api/v1/users/subscription`**
   - دریافت اطلاعات اشتراک فعال کاربر
   - شامل نام پلن، مصرف، تاریخ انقضا

---

### 🔔 `app/api/v1/notifications.py` - اعلان‌ها

#### Endpoints:
1. **`GET /api/v1/notifications/`**
   - دریافت لیست اعلان‌های کاربر
   - پشتیبانی از pagination

2. **`GET /api/v1/notifications/unread-count`**
   - تعداد اعلان‌های خوانده نشده

3. **`PUT /api/v1/notifications/{notif_id}/read`**
   - علامت‌زدن یک اعلان به عنوان خوانده شده

4. **`PUT /api/v1/notifications/read-all`**
   - علامت‌زدن همه اعلان‌ها به عنوان خوانده شده

5. **`DELETE /api/v1/notifications/{notif_id}`**
   - حذف یک اعلان

---

### 💰 `app/api/v1/credits.py` - مدیریت اعتبار

#### Endpoints:
1. **`GET /api/v1/credits/balance`**
   - دریافت موجودی اعتبار کاربر
   - **مجموع از همه اشتراک‌های فعال**
   - شامل breakdown هر اشتراک

2. **`GET /api/v1/credits/transactions`**
   - تاریخچه تراکنش‌های اعتبار
   - شامل: خرید، کسر، بازگشت

3. **`GET /api/v1/credits/check/{note_id}`**
   - محاسبه اعتبار مورد نیاز برای یک note
   - بررسی کفایت موجودی

---

### 👨‍💼 `app/api/v1/admin.py` - پنل ادمین

#### Endpoints:
1. **`GET /api/v1/admin/stats`**
   - آمار کلی سیستم
   - تعداد کاربران، notes، subscriptions

2. **`GET /api/v1/admin/users`**
   - لیست کاربران با جزئیات

3. **`GET /api/v1/admin/notes`**
   - لیست تمام notes با فیلتر

4. **`GET /api/v1/admin/subscriptions`**
   - لیست اشتراک‌های فعال/منقضی شده

---

## سرویس‌های Backend

### 🤖 `app/services/ai_service.py` - سرویس Gemini AI

#### توابع اصلی:

1. **`process_files_with_gemini(file_paths: List[str])`**
   - آپلود فایل‌ها به Gemini File API
   - انتظار برای پردازش فایل‌ها
   - ارسال prompt به Gemini 2.5 Flash
   - تنظیمات:
     - `max_output_tokens: 100000` (برای خروجی‌های بلند)
     - `temperature: 0.4`
   - پارس کردن خروجی JSON
   - بازگشت: `{title, note}` (HTML)

2. **System Instruction**:
   - تبدیل صوت/تصویر به یادداشت ساختاریافته
   - حفظ زبان اصلی محتوا (فارسی/انگلیسی)
   - خروجی: HTML با تگ‌های معنایی
   - تولید عنوان بر اساس محتوا

---

### 💳 `app/services/credit_service.py` - مدیریت اعتبار

#### کلاس `CreditManager`:

1. **`get_file_duration(file_path, file_type)`**
   - استخراج مدت زمان فایل صوتی/تصویری
   - استفاده از `ffprobe`

2. **`calculate_file_credits(file_path, file_type)`**
   - محاسبه اعتبار مورد نیاز برای یک فایل
   - صوتی/ویدیو: بر اساس مدت زمان (دقیقه)
   - تصویر: 0.5 دقیقه (ثابت)

3. **`calculate_note_credits(db, note_id)`**
   - محاسبه مجموع اعتبار مورد نیاز یک note
   - جمع اعتبار همه uploads

4. **`get_user_balance(db, user_id)`**
   - محاسبه موجودی کل از همه اشتراک‌های فعال
   - بازگشت: total_minutes + breakdown

5. **`deduct_credits(db, user_id, amount, note_id)`**
   - کسر اعتبار از اشتراک‌ها
   - **اولویت**: اشتراک‌هایی که زودتر منقضی می‌شوند
   - ثبت تراکنش
   - خطا در صورت عدم کفایت موجودی

6. **`refund_credits(db, user_id, amount, note_id)`**
   - بازگشت اعتبار (در صورت خطا)
   - بازگشت به همان اشتراک‌هایی که کسر شده

---

### 📄 `app/services/pdf_service.py` - تولید PDF

#### توابع:

1. **`generate_note_pdf(title, content, session_date)`**
   - تولید PDF از یک جزوه
   - تبدیل HTML به PDF
   - استفاده از ReportLab
   - فونت فارسی: Vazirmatn

2. **`generate_notebook_pdf(notebook_title, notes_data)`**
   - تولید PDF از چند جزوه
   - ترکیب notes در یک فایل
   - جدول محتویات

---

### 📱 `app/services/sms_service.py` - ارسال SMS

#### توابع:

1. **`send_otp_sms(phone_number, otp_code)`**
   - ارسال کد OTP از طریق Kavenegar
   - template-based SMS

---

### 🎨 `app/services/html_processor.py` - پردازش HTML

#### توابع:

1. **`process_gemini_output(html_content)`**
   - اصلاح code blocks برای scroll افقی
   - اصلاح جداول بزرگ
   - افزودن wrapper برای عناصر عریض

---

## Worker و Celery

### ⚙️ `app/worker/celery_app.py` - تنظیمات Celery

#### محتویات:
- ایجاد Celery app
- تنظیم broker: Redis
- تنظیم backend: Redis
- Import tasks از:
  - `app.worker.tasks`
  - `app.worker.tasks_with_credits_fixed`

---

### 🔄 `app/worker/tasks_with_credits_fixed.py` - Task اصلی پردازش

#### Task: `process_file_with_credits(note_id)`

**جریان کار:**

1. **محاسبه اعتبار دقیق**:
   - بر اساس مدت واقعی فایل‌ها
   - استفاده از ffprobe

2. **بررسی موجودی**:
   - چک کردن اعتبار کافی
   - در صورت کمبود: fail + notification

3. **کسر اعتبار**:
   - deduct از اشتراک‌ها (اولویت: قدیمی‌تر)
   - ثبت تراکنش

4. **پردازش با Gemini**:
   - ارسال فایل‌ها به AI
   - دریافت HTML output

5. **پردازش HTML**:
   - اصلاح code blocks
   - اصلاح جداول

6. **ذخیره نتیجه**:
   - update note: title, gemini_output_text, status=completed
   - ایجاد notification موفقیت

7. **مدیریت خطا**:
   - بازگشت اعتبار
   - retry logic (حداکثر 3 بار)
   - ایجاد notification خطا

---

### ⚠️ `app/worker/error_handler.py` - مدیریت خطاها

#### کلاس `ProcessingError`:

1. **`classify_error(error)`**
   - دسته‌بندی خطا:
     - `quota_exceeded`: سهمیه API تمام شده
     - `invalid_format`: فرمت فایل نامعتبر
     - `network_error`: مشکل شبکه
     - `timeout`: timeout
     - `file_too_large`: فایل بزرگ
     - `content_generation`: خطای تولید محتوا
   - تعیین retryable یا نه

2. **`should_retry(error, retry_count, max_retries)`**
   - تصمیم‌گیری برای retry
   - exponential backoff

3. **`get_retry_delay(retry_count)`**
   - محاسبه تاخیر retry: 60s, 300s, 900s

---

## صفحات Frontend

### 🏠 `app/templates/index.html` - صفحه لندینگ
- معرفی سرویس
- دکمه ورود/ثبت‌نام
- ویژگی‌ها

### 🔐 `app/templates/login.html` - ورود/ثبت‌نام
- ورود با OTP
- ارسال کد تایید
- تایید OTP و redirect

### 📚 `app/templates/notebooks.html` - دفترها
- نمایش grid دفترها
- افزودن دفتر جدید
- ویرایش/حذف دفتر
- نمایش تعداد جزوات (فقط فعال و غیر-failed)

### 📝 `app/templates/notes.html` - جزوات
- لیست جزوات یک دفتر
- فیلتر بر اساس دفتر
- نمایش status (processing/completed/failed)
- **مرتب‌سازی**: بر اساس `session_date` (جدیدترین بالا)
- دکمه‌های: مشاهده، ویرایش، حذف، PDF

### 📝 `app/templates/all-notes.html` - همه جزوات
- نمایش تمام جزوات کاربر
- بدون فیلتر دفتر
- جستجو

### ✏️ `app/templates/editor.html` - ویرایشگر
- ویرایش محتوای HTML
- استفاده از TinyMCE
- ذخیره خودکار
- پیش‌نمایش

### 📤 `app/templates/upload.html` - آپلود
- آپلود چند فایل همزمان
- drag & drop
- انتخاب دفتر
- وارد کردن تاریخ جلسه (شمسی)
- **نمایش موجودی اعتبار**
- **بررسی اعتبار قبل از آپلود**:
  - تخمین اولیه (بر اساس حجم)
  - بررسی نهایی (بعد از آپلود، منتظر worker)
  - در صورت کمبود: ماندن در صفحه + نمایش خطا
- progress bar آپلود

### 👤 `app/templates/profile.html` - پروفایل
- ویرایش اطلاعات شخصی
- نمایش وضعیت اشتراک:
  - **پشتیبانی از چند اشتراک همزمان**
  - مجموع دقیقه/مصرف
  - تاریخ انقضا
  - progress bar
- تنظیمات حالت تاریک/روشن
- خروج از حساب

### 🔔 `app/templates/notifications.html` - اعلان‌ها
- **یک تب**: همه اعلان‌ها
- نمایش: عنوان، پیام، زمان
- دکمه‌ها:
  - **مشاهده یادداشت**: redirect + mark as read
  - خواندم: mark as read
  - حذف
- علامت‌زدن همه به عنوان خوانده شده

### 💎 `app/templates/plans.html` - پلن‌ها
- نمایش پلن‌های موجود
- قیمت، مدت، ویژگی‌ها
- دکمه خرید → redirect به payment

---

## استایل‌ها و Assets

### 🎨 `app/static/css/style.css` - استایل اصلی

#### ویژگی‌ها:
- **Neobrutalism Design**:
  - border: 4px solid black
  - box-shadow: 6px 6px 0 black
  - رنگ‌های تند و پررنگ
  - گوشه‌های گرد
- **حالت تاریک/روشن**
- **RTL Support** (راست به چپ)
- **Responsive** (موبایل، تبلت، دسکتاپ)
- **فونت فارسی**: Vazirmatn

#### متغیرهای CSS:
```css
--accent: رنگ اصلی (زرد)
--accent-fg: رنگ متن روی accent
--bg-primary: پس‌زمینه اصلی
--text-primary: رنگ متن اصلی
--border-color: رنگ border (مشکی)
--border-width: ضخامت border (4px)
--radius: شعاع گوشه (12px)
--shadow-hard: سایه سخت
```

---

### 📜 `app/static/js/api.js` - API Client

#### کلاس‌ها:

1. **`AuthAPI`**:
   - `sendOTP(phoneNumber)`
   - `verifyOTP(phoneNumber, otpCode)`
   - `logout()`

2. **`NotebooksAPI`**:
   - `getAll()`
   - `create(title)`
   - `update(id, title)`
   - `delete(id)`

3. **`NotesAPI`**:
   - `create(formData, onProgress)`
   - `getAll(notebookId)`
   - `getById(id)`
   - `update(id, data)`
   - `delete(id)`

4. **`UsersAPI`**:
   - `getMe()`
   - `updateMe(data)`
   - `getSubscription()`

5. **`NotificationsAPI`**:
   - `getAll()`
   - `getUnreadCount()`
   - `markAsRead(id)`
   - `markAllAsRead()`
   - `delete(id)`

---

### 🛠 `app/static/js/common.js` - توابع مشترک

#### توابع:
- `setupSidebarToggle()`: کنترل sidebar موبایل
- `setupThemeSwitcher()`: تغییر حالت تاریک/روشن
- `showToast(message, type)`: نمایش پیغام‌ها
- `formatFileSize(bytes)`: فرمت حجم فایل
- `formatDate(dateString)`: فرمت تاریخ (شمسی)
- `getRelativeTime(dateString)`: زمان نسبی (5 دقیقه پیش)

---

## Core

### ⚙️ `app/core/config.py` - تنظیمات

#### Settings:
```python
- APP_NAME: نام برنامه
- DATABASE_URL: آدرس دیتابیس
- SECRET_KEY: کلید رمزنگاری JWT
- GEMINI_API_KEY: کلید API Gemini
- KAVENEGAR_API_KEY: کلید SMS
- ZARINPAL_MERCHANT_ID: کد پذیرنده
- CELERY_BROKER_URL: Redis URL
- REDIS_URL: آدرس Redis
- IMAGE_CREDIT_COST: 0.5 (دقیقه به ازای هر تصویر)
- UPLOAD_DIR: مسیر ذخیره فایل‌ها
```

---

### 🔒 `app/core/dependencies.py` - Dependencies

#### توابع:
1. **`get_current_user_from_cookie(request, db)`**:
   - استخراج JWT token از cookie
   - verify و decode token
   - بازگشت User object

---

### 🗄️ `app/db/session.py` - اتصال دیتابیس

#### محتویات:
- ایجاد async engine (MySQL+asyncmy)
- تعریف SessionLocal
- تابع `get_db()`: dependency برای دریافت session

---

## CRUD Operations

### 📂 `app/crud/`

#### فایل‌ها:

1. **`notebook.py`**:
   - `create_notebook()`
   - `get_notebooks_by_user()`
   - `get_notebook_by_id()`
   - `update_notebook()`
   - `delete_notebook()`
   - **`get_notebook_notes_count()`**: شمارش notes (فقط فعال و غیر-failed)

2. **`note.py`**:
   - `create_note()`
   - **`get_notes_by_user()`**: با مرتب‌سازی session_date descending
   - `get_note_by_id()`
   - `update_note()`
   - `delete_note()`: soft delete
   - `create_upload()`

3. **`user.py`**:
   - `get_user_by_phone()`
   - `create_user()`
   - `update_user()`
   - `update_otp()`
   - `verify_user()`

4. **`plan.py`**:
   - `get_all_plans()`
   - `get_plan_by_id()`

5. **`subscription.py`**:
   - `create_subscription()`
   - `get_active_subscription()`
   - `activate_subscription()`

6. **`payment.py`**:
   - `create_payment()`
   - `get_payment_by_ref()`
   - `update_payment_status()`

7. **`notification.py`**:
   - `create_notification()`
   - `get_user_notifications()`
   - `mark_as_read()`
   - `delete_notification()`

---

## Schemas (Pydantic)

### 📂 `app/schemas/`

#### فایل‌ها:

1. **`user.py`**:
   - `UserCreate`, `UserUpdate`, `UserResponse`

2. **`notebook.py`**:
   - `NotebookCreate`, `NotebookUpdate`, `NotebookResponse`
   - شامل `notes_count`

3. **`note.py`**:
   - `NoteCreate`, `NoteUpdate`, `NoteResponse`
   - `session_date`: Optional[str] (فرمت شمسی YYYY/MM/DD)

4. **`plan.py`**:
   - `PlanResponse`

5. **`payment.py`**:
   - `PaymentCreate`, `PaymentResponse`

---

## مایگریشن‌ها

### 📂 `migrations/`

#### فایل‌های SQL:
1. **Initial schema**: ساخت جداول اولیه
2. **`change_session_date_to_varchar.sql`**: تبدیل session_date به VARCHAR(10) برای تاریخ شمسی
3. سایر migrations مربوط به credit system, queue, etc.

---

## ویژگی‌های کلیدی پروژه

### ✅ 1. سیستم احراز هویت
- OTP-based (بدون پسورد)
- JWT token در cookie
- تایید شماره موبایل

### ✅ 2. سیستم اعتبار (Credit System)
- **چند اشتراک همزمان**: کاربر می‌تونه چند پلن فعال داشته باشه
- **اولویت مصرف**: اشتراک‌هایی که زودتر منقضی می‌شن، اول مصرف می‌شن
- **محاسبه دقیق**: بر اساس مدت واقعی فایل (ffprobe)
- **بررسی قبل از پردازش**: در frontend و worker
- **بازگشت اعتبار**: در صورت خطا

### ✅ 3. پردازش هوشمند با AI
- **Gemini 2.5 Flash**: مدل قدرتمند multimodal
- **پشتیبانی از انواع فایل**: صوتی، تصویری، ویدیویی
- **چند فایل همزمان**: یک جزوه از چند فایل
- **خروجی ساختاریافته**: HTML با تگ‌های معنایی
- **max_output_tokens: 100K**: برای محتوای بلند

### ✅ 4. مدیریت تاریخ شمسی
- **ذخیره تاریخ شمسی**: VARCHAR(10) به فرمت YYYY/MM/DD
- **بدون تبدیل**: مستقیماً از frontend ذخیره می‌شه
- **مرتب‌سازی**: براساس session_date (جدیدترین بالا)

### ✅ 5. صف پردازش (Queue)
- **Celery + Redis**: پردازش asynchronous
- **Retry logic**: حداکثر 3 بار با exponential backoff
- **مدیریت خطا**: دسته‌بندی و refund خودکار

### ✅ 6. Notification System
- **انواع**: موفقیت، خطا، هشدار سهمیه، انقضای اشتراک
- **Real-time count**: تعداد خوانده نشده در navbar
- **Auto mark as read**: هنگام مشاهده note

### ✅ 7. UI/UX
- **Neobrutalism Design**: زیبا، مدرن، متمایز
- **Dark/Light Mode**: با ذخیره preference
- **RTL Support**: کامل فارسی
- **Responsive**: موبایل، تبلت، دسکتاپ
- **Progress indicators**: برای آپلود و پردازش

### ✅ 8. Export و PDF
- **تک جزوه**: دانلود PDF یک note
- **کل دفتر**: ترکیب همه notes در یک PDF
- **فونت فارسی**: Vazirmatn
- **فرمت حرفه‌ای**: با header/footer

---

## جریان کار کامل (End-to-End)

### 📤 آپلود و پردازش:

1. **کاربر وارد `/upload` میشه**
2. **انتخاب دفتر و فایل‌ها**
3. **وارد کردن تاریخ جلسه** (شمسی، اختیاری)
4. **بررسی اعتبار اولیه** (frontend):
   - تخمین بر اساس حجم
   - اگه کافی نیست → خطا + توقف
5. **آپلود فایل‌ها** به سرور:
   - ذخیره در `uploads/`
   - ایجاد note با status=processing
   - ایجاد upload records
6. **تریگر Celery task**: `process_file_with_credits.delay(note_id)`
7. **صبر 3 ثانیه** (frontend):
   - بررسی status note
   - اگه failed با خطای اعتبار → نمایش خطا + ماندن در صفحه
   - اگه موفق → redirect به `/notes`

### ⚙️ Worker (Background):

8. **محاسبه اعتبار دقیق** (بر اساس مدت فایل)
9. **بررسی موجودی**:
   - اگه کافی نیست → status=failed + notification + refund نمی‌خواد (چون هنوز deduct نشده)
10. **کسر اعتبار** از اشتراک‌ها (قدیمی‌تر اول)
11. **آپلود به Gemini** و پردازش
12. **دریافت HTML output**
13. **پردازش HTML** (اصلاح code blocks/tables)
14. **ذخیره در دیتابیس**:
    - title, gemini_output_text, user_edited_text
    - status = completed
15. **ایجاد notification موفقیت**

### 🔔 Notification:

16. **کاربر وارد `/notifications` میشه**
17. **کلیک روی "مشاهده یادداشت"**:
    - mark as read
    - redirect به `/editor?note_id=X`

### ✏️ ویرایش:

18. **کاربر محتوا رو ویرایش می‌کنه**
19. **ذخیره در `user_edited_text`**

### 📥 دانلود PDF:

20. **کلیک روی دکمه PDF**
21. **تولید PDF** با ReportLab
22. **دانلود فایل**

---

## نکات مهم برای توسعه‌دهندگان

### 🔧 راه‌اندازی محیط توسعه:

```bash
# 1. نصب وابستگی‌ها
pip install -r requirements.txt

# 2. تنظیم .env
cp .env.example .env
# ویرایش و تکمیل کلیدها

# 3. ساخت دیتابیس
mysql -u root -p < migrations/initial_schema.sql

# 4. اجرای سرور
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. اجرای Celery worker
celery -A app.worker.celery_app worker --loglevel=info

# 6. اجرای Redis
redis-server
```

### 🐛 Debug:

- **Logs**: چک کنید console سرور و worker
- **Database**: از MySQL workbench یا CLI استفاده کنید
- **Redis**: `redis-cli monitor` برای مشاهده commands
- **Celery**: `celery -A app.worker.celery_app inspect active` برای tasks

### 📝 اضافه کردن قابلیت جدید:

1. **مدل جدید**: `app/db/models.py` + migration
2. **Schema**: `app/schemas/`
3. **CRUD**: `app/crud/`
4. **API**: `app/api/v1/`
5. **Register router**: `app/main.py`
6. **Frontend**: `app/templates/` + `app/static/`

---

## پشتیبانی و نگهداری

### 🔄 Backup:
- **دیتابیس**: `mysqldump -u user -p neviso_db > backup.sql`
- **فایل‌های آپلود**: backup کردن `uploads/`

### 📊 Monitoring:
- **Health check**: `GET /health`
- **Celery**: تعداد task‌های در صف
- **Redis**: حافظه مصرفی
- **MySQL**: اتصالات و queries

### 🚀 Deployment:
- **Production**: استفاده از Gunicorn + Nginx
- **SSL**: Let's Encrypt
- **Docker**: می‌تونید dockerize کنید
- **Environment**: تنظیم متغیرهای محیطی

---

## تماس و پشتیبانی

برای گزارش باگ یا پیشنهادات:
- ایمیل: support@neviso.ir
- مستندات بیشتر: [README.md](README.md)

---

**نسخه مستندات**: 1.0.0
**تاریخ آخرین بروزرسانی**: 2025-01-09
