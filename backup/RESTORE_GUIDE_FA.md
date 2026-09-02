# راهنمای بازسازی و انتقال Riva / Persian Shop به ربات جدید

این راهنما برای حالتی است که می‌خواهید یک Bot Token جدید، کانال گزارش جدید و Railway Project جدید بسازید و همان پروژه را با کمترین اختلاف ممکن بالا بیاورید.

## بخش A — بازیابی سورس

### روش پیشنهادی: از project-source

محتویات `project-source/` را داخل یک Repository جدید قرار دهید.

```bash
git init
git add .
git commit -m "restore Persian Shop from verified backup"
```

### روش کامل با تاریخچه Git

فایل `git/Riva-full-history.bundle` یک Git Bundle است. برای بازیابی:

```bash
git clone Riva-full-history.bundle Riva-restored
cd Riva-restored
git checkout main
```

Commit مرجع Production هنگام تهیه بک‌آپ:

`fc0e7ae989572a3297079182f729dbf8951ecd21`

اگر هدف «دقیقاً همان سورس Production» است، روی همین Commit checkout کنید.

---

## بخش B — ساخت Bot جدید

1. در Telegram به BotFather بروید.
2. Bot جدید بسازید.
3. Token جدید دریافت کنید.
4. Token را فقط در Railway Variable `BOT_TOKEN` قرار دهید.
5. Token را داخل Git، Screenshot عمومی یا Prompt اشتراکی قرار ندهید.

Telegram numeric Bot ID بعد از اجرا از log مشخص می‌شود و نیازی به Hard-code کردن آن نیست.

---

## بخش C — ساخت Database جدید

برای Production از PostgreSQL استفاده کنید.

در Railway:

1. Add Service → PostgreSQL.
2. `DATABASE_URL` را به Service ربات Reference کنید.
3. مطمئن شوید Scheme مورد انتظار SQLAlchemy async است؛ اگر Railway URL معمولی `postgresql://` می‌دهد و Config تبدیل خودکار ندارد، طبق `bot/config.py` فرمت صحیح را بررسی کنید.

برای نصب محلی SQLite:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/persian_shop.db
```

برای Database تازه، اجرای اپ `create_schema` و `seed_database` را انجام می‌دهد. Alembic نیز داخل پروژه موجود است.

در صورت نیاز:

```bash
alembic upgrade head
```

---

## بخش D — Environment Variables

فایل `ENV_TEMPLATE_CURRENT.env` را باز کنید و مقادیر Placeholder را پر کنید.

حداقل موارد ضروری:

```dotenv
BOT_TOKEN=<NEW_TOKEN>
ADMIN_IDS=<NEW_OWNER_TELEGRAM_ID>
DATABASE_URL=<NEW_DATABASE_URL>
SHOP_NAME=Persian Shop
DEFAULT_LANGUAGE=fa
TIMEZONE=Asia/Tehran
HEALTH_SERVER_ENABLED=true
```

برای گزارش سفارش:

```dotenv
ORDER_REPORT_CHANNEL_ID=<NEW_REPORT_CHANNEL_ID>
ORDER_REPORT_RECONCILE_INTERVAL_SECONDS=30
ORDER_REPORT_RECONCILE_HOURS=2
```

---

## بخش E — ساخت Channel گزارش جدید

1. Channel جدید بسازید.
2. Bot جدید را Administrator کنید.
3. دسترسی Post Messages بدهید.
4. Chat ID عددی Channel را پیدا کنید و در `ORDER_REPORT_CHANNEL_ID` ثبت کنید.
5. یک سفارش کنترل‌شده با اکانت مالک تست کنید.
6. بررسی کنید Report فقط یک بار ارسال شود.

برای Channel خصوصی، لینک Invite مثل `t.me/+...` همیشه برای Bot API معادل Chat ID قابل Resolve نیست. مطمئن‌ترین روش این است که Bot داخل Channel Admin باشد و Chat ID عددی ثبت شود.

---

## بخش F — Premium Emoji گزارش

پس از Deploy، با اکانت Owner در Private Chat ربات از `/reportemoji` استفاده کنید.

Slotهای قابل تنظیم:

```text
/reportemoji shop
/reportemoji buyer
/reportemoji product
/reportemoji amount
/reportemoji time
/reportemoji bot
/reportemoji button
```

IDهای قطعی Snapshot قبلی:

```text
buyer   = 5453940933512944480
product = 5294476812221439592
amount  = 5325685779760962109
time    = 5395355586730679238
bot     = 5938534225140519372
```

`shop` و `button` را از مالک/نسخه فعلی بگیرید؛ حدس نزنید.

پس از هر تنظیم:

```text
/reportemoji test
```

نکته: موفق بودن API call لزوماً به معنی رندر شدن Custom Emoji در Channel نیست. محدودیت‌های Telegram برای Channel را در نظر بگیرید.

---

## بخش G — تست زبان و Menu

پس از `/start`:

- Welcome فارسی صحیح باشد.
- Reply keyboard تغییر زبان باقی بماند.
- تغییر به English انجام شود.
- Welcome انگلیسی صحیح باشد.
- FAQ انگلیسی با فارسی هم‌راستا باشد.
- هیچ Button انگلیسی دارای متن فارسی باقی‌مانده نباشد.
- Emojiهای Premium و styleهای Button بعد از ترجمه حفظ شوند.

دو پیام قدیمی تأیید تغییر زبان نباید نمایش داده شوند.

---

## بخش H — تست کاتالوگ

1. Categoryها را باز کنید.
2. Product list را بررسی کنید.
3. عکس هر Product باز شود.
4. Description اختصاصی همان Product باشد.
5. قیمت integer تومان صحیح باشد.
6. Product emoji/custom emoji از بین نرفته باشد.
7. Quantity/Input flow درست باشد.

Seed پروژه باید کاتالوگ مرجع را بسازد. اگر Admin قبلی Product خاصی را فقط در DB ساخته و داخل Seed نیست، برای Clone جدید باید آن Product جداگانه Export/Import شود.

---

## بخش I — Wallet و Manual Payment

### Card-to-card

- کاربر ابتدا مبلغ را وارد کند.
- سپس Card method را انتخاب کند.
- Card number و holder نمایش داده شود.
- کاربر Receipt را ارسال کند.
- Admin Notification دریافت کند.
- Admin تأیید کند.
- Wallet فقط یک بار شارژ شود.

### USDT

- Network و address مطابق Admin setting باشد.
- مبلغ/Conversion نمایش داده شود اگر Rate source فعال است.
- Receipt/Tx hash flow تست شود.

هیچ شارژی صرفاً با Upload receipt خودکار انجام نشود؛ تأیید Admin الزامی است مگر Source صریحاً چیز دیگری تعریف کرده باشد.

---

## بخش J — Order و Report

1. Wallet کنترل‌شده شارژ کنید.
2. یک Product بخرید.
3. موجودی دقیقاً یک بار کم شود.
4. Order ایجاد شود.
5. Admin notification برسد.
6. Report Channel ارسال شود.
7. اگر Report را عمداً Fail کردید، Order نباید Fail شود.
8. پس از رفع مشکل، reconciliation باید Report جاافتاده را بفرستد.

Report idempotency را با ActivityLog بررسی کنید.

---

## بخش K — کمپین تست 30 Report/day

این قابلیت صرفاً برای Channel خصوصی تست است و در Clone جدید پیش‌فرض خاموش باشد.

برای فعال‌سازی:

```dotenv
REPORT_TEST_CAMPAIGN_ENABLED=true
REPORT_TEST_CAMPAIGN_CHANNEL_ID=<PRIVATE_TEST_CHANNEL_ID>
REPORT_TEST_CAMPAIGN_DAYS=14
REPORT_TEST_CAMPAIGN_DAILY_COUNT=30
REPORT_TEST_CAMPAIGN_MIN_PRICE=300000
REPORT_TEST_CAMPAIGN_POLL_SECONDS=20
```

Bot را Admin Channel خصوصی کنید. اگر Auto-bind انجام نشد، در همان Channel:

```text
/bindreporttest
```

Flow تست نباید Order/User/Payment/Wallet Transaction واقعی بسازد.

برای نصب جدید بهتر است Production Report Channel و Private Test Channel دو Chat ID متفاوت باشند.

---

## بخش L — Railway Deploy

Snapshot مرجع:

- Builder: RAILPACK
- Runtime: V2
- Start: `python -m bot`
- Health: `/health`
- Health timeout: 300s
- Region: SFO
- Replicas: 1

مراحل:

1. Repository جدید را به Railway وصل کنید.
2. Production environment بسازید.
3. Variables را وارد کنید.
4. PostgreSQL را وصل کنید.
5. Start command را `python -m bot` بگذارید.
6. Healthcheck را `/health` بگذارید.
7. Deploy کنید.
8. Log باید شامل `Persian Shop bot started` و `Start polling` باشد.
9. `/health` باید 200 شود.

اگر هنگام Rolling Deploy یک `TelegramConflictError` کوتاه دیدید، deployment قدیمی را بررسی کنید. بعد از حذف instance قدیمی باید connection پایدار شود.

---

## بخش M — CI و تست کد

قبل از Production:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

هر دو باید بدون Failure تمام شوند.

---

## بخش N — داده‌های Runtime نسخه قبلی

این ZIP سورس را کامل نگه می‌دارد ولی Database Runtime Production در Git نیست. اگر هدف فقط ساخت Bot جدید با همان طراحی و امکانات است، **کاربران، سفارش‌ها و موجودی‌های قبلی را منتقل نکنید**.

اگر هدف Migration کامل Business data است:

- PostgreSQL: `pg_dump` رمزگذاری‌شده تهیه کنید.
- SQLite: فایل DB را در زمان توقف Write کپی کنید.
- قبل از Import به Bot جدید، Telegram user IDs و Admin IDs را از نظر حریم خصوصی و نیاز تجاری بررسی کنید.

Secretها و Dump شامل اطلاعات کاربر را داخل Repository عمومی قرار ندهید.

---

## بخش O — تحویل نهایی

ربات جدید فقط وقتی آماده است که:

- GitHub CI سبز باشد.
- Railway Health سبز باشد.
- Polling پایدار باشد.
- `/start` هر دو زبان تست شده باشد.
- Product/Wallet/Order تست شده باشد.
- Report channel تست شده باشد.
- Admin panel تست شده باشد.
- Secretها در Git وجود نداشته باشند.

برای جزئیات رفتاری و محدودیت‌های غیرقابل حذف، فایل `MASTER_RESTORE_PROMPT_FA.md` را مرجع قرار دهید.
