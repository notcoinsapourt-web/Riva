# Persian Shop

ربات فروشگاهی ماژولار تلگرام برای فروش خدمات شبکه‌های اجتماعی، اشتراک‌های هوش مصنوعی و محصولات دیجیتال؛ ساخته‌شده با Python، Aiogram 3 و معماری کاملاً Async.

## امکانات نسخه 1.0

- ثبت خودکار کاربر با Telegram ID و پروفایل
- کاتالوگ داینامیک دسته‌ها و محصولات
- عکس، توضیح، قیمت، ایموجی و Custom Emoji مستقل برای محصول
- خرید از کیف پول با تراکنش اتمیک و محافظت در برابر ثبت دوباره
- پنج وضعیت سفارش با تاریخچه کامل و اعلان تغییر وضعیت
- بازپرداخت خودکار و یک‌باره هنگام لغو سفارش
- کد تخفیف درصدی یا ثابت با تاریخ، ظرفیت و محدودیت هر کاربر
- دعوت دوستان و پاداش قابل تنظیم پس از اولین سفارش تکمیل‌شده
- سیستم تیکت و پاسخ پشتیبانی
- پیام همگانی با مدیریت خطا و محدودیت Telegram
- لاگ فعالیت‌های مدیریتی
- ضداسپم، مدیریت خطا و مسدودسازی کاربران
- پنل مدیریت کامل داخل تلگرام
- نقش‌های `owner`، `admin`، `operator` و `support` با دسترسی تفکیک‌شده
- فعال/غیرفعال‌کردن ماژول‌ها، تغییر ترتیب منو، متن دکمه و Custom Emoji
- دکمه‌های Native Inline با Styleهای جدید Telegram (`primary`، `success` و `danger`)
- لایه ترجمه با فارسی و فایل پایه انگلیسی
- SQLite برای شروع و PostgreSQL برای رشد
- Docker، Render Blueprint، Railway/VPS، Alembic و GitHub Actions

> دکمه «شیشه‌ای» در ربات تلگرام یک CSS سفارشی نیست؛ ظاهر آن را خود Telegram رسم می‌کند. این پروژه از Inline Keyboard بومی، رنگ‌های رسمی Bot API و `icon_custom_emoji_id` استفاده می‌کند تا بهترین ظاهر Premium ممکن را ارائه دهد.

## ساختار پروژه

```text
bot/
├── app.py                    # بوت، polling و health server
├── config.py                 # Environment Variables
├── core/                     # callback، UI، middleware، security و i18n
├── database/                 # SQLAlchemy models، session و seed
├── locales/                  # fa.json و en.json
├── services/                 # منطق تجاری و تراکنش‌ها
├── modules/
│   ├── admin/                # پنل مدیریت و RBAC
│   ├── catalog/              # دسته، محصول و checkout
│   ├── orders/
│   ├── wallet/
│   ├── referral/
│   ├── tickets/
│   └── payments/providers/   # Zarinpal، IDPay و USDT
└── web/                      # health/readiness endpoints
alembic/                      # migrationها
tests/                        # تست سرویس، امنیت تراکنش و UI
```

## راه‌اندازی محلی

پیش‌نیاز: Python 3.11 یا جدیدتر.

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd persian-shop
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

در فایل `.env` حداقل این دو مقدار را وارد کنید:

```dotenv
BOT_TOKEN=توکن_جدید_BotFather
ADMIN_IDS=123456789
```

شناسه چند مدیر اولیه را با ویرگول جدا کنید:

```dotenv
ADMIN_IDS=123456789,987654321
```

اجرا:

```bash
python -m bot
```

چهار دسته اولیه خودکار ساخته می‌شوند. سپس با `/admin` وارد پنل شوید و محصول واقعی، قیمت و عکس را اضافه کنید.

## پنل مدیریت

فرمان `/admin` داشبورد را باز می‌کند. امکانات پنل:

- سفارش‌ها: مشاهده، تأیید، شروع انجام، تکمیل، لغو و پیام به مشتری
- محصولات: افزودن، ویرایش تمام فیلدها، عکس، Emoji، Custom Emoji، فعال‌سازی و حذف
- دسته‌بندی‌ها: افزودن، ویرایش، فعال‌سازی و حذف امن
- کاربران: جستجو، مشاهده حساب، افزایش/کاهش موجودی، پیام و مسدودسازی
- مدیران: افزودن مدیر و تعیین نقش؛ آخرین Owner قابل حذف یا تنزل نیست
- درآمد: مجموع سفارش‌های تکمیل‌شده و گزارش ۳۰ روزه
- تخفیف: کد درصدی/ثابت، ظرفیت، انقضا، فعال‌سازی و حذف
- پیام همگانی
- تیکت‌های پشتیبانی
- تنظیمات فروشگاه، متن خوش‌آمد، پشتیبانی و پاداش دعوت
- ماژول‌ها: روشن/خاموش، جابه‌جایی، متن دکمه، Emoji و Custom Emoji ID

### نقش‌ها

| نقش | دسترسی |
| --- | --- |
| Owner | همه بخش‌ها و مدیریت مدیران |
| Admin | سفارش، محصول، کاربر، تخفیف، پیام، تنظیمات و تیکت |
| Operator | سفارش‌ها و پیام مرتبط با سفارش |
| Support | تیکت‌ها و پاسخ پشتیبانی |

## دیتابیس

حالت پیش‌فرض:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/persian_shop.db
```

PostgreSQL:

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/persian_shop
```

برای دیتابیس تازه می‌توانید migration اولیه را اجرا کنید:

```bash
alembic upgrade head
```

اگر نسخه اولیه قبلاً با `create_all` دیتابیس را ساخته است، قبل از migrationهای آینده یک‌بار اجرا کنید:

```bash
alembic stamp head
```

مبالغ به‌صورت عدد صحیح و با واحد «تومان» ذخیره می‌شوند؛ از `float` برای پول استفاده نشده است.

## پرداخت‌ها — عمداً غیرفعال

کد Provider برای زرین‌پال، IDPay، USDT-TRC20 و USDT-BEP20 موجود است، اما هیچ پرداختی با تنظیم پیش‌فرض فعال نمی‌شود. برای جلوگیری از فعال‌شدن تصادفی، هر دو قفل محیطی باید روشن باشند:

```dotenv
PAYMENTS_ENABLED=true
PAYMENT_INTEGRATION_CONFIRMED=true
```

قبل از روشن‌کردن باید کلید قرارداد، callback HTTPS، امضای webhook متناسب با حساب واقعی و تست Sandbox بررسی شود. ساخت و Verify فاکتور و شارژ idempotent کیف پول در لایه سرویس آماده است؛ مسیر HTTP callback عمداً تا زمان تعیین دامنه واقعی و Secret درگاه فعال نشده است. شارژ دستی کیف پول از پنل مدیر نیز آماده است.

## Custom Emoji

در پنل مدیریت، ماژول یا محصول را باز کنید و `Custom Emoji ID` را ثبت کنید. اگر ID برای حساب/ربات مجاز نباشد، Telegram ممکن است آن را نمایش ندهد؛ در این حالت Emoji معمولی به‌عنوان fallback باقی می‌ماند.

## Docker

```bash
docker build -t persian-shop .
docker run --env-file .env -p 10000:10000 -v persian-shop-data:/app/data persian-shop
```

یا همراه PostgreSQL:

```bash
docker compose up --build -d
```

## Deploy روی Render

1. پروژه را در GitHub قرار دهید.
2. در Render گزینه **New Blueprint** را انتخاب و repository را وصل کنید؛ `render.yaml` شناسایی می‌شود.
3. مقدارهای Secret برای `BOT_TOKEN` و `ADMIN_IDS` را ثبت کنید.
4. برای استفاده تجاری، `DATABASE_URL` را به PostgreSQL تغییر دهید.
5. Health Check روی `/health` آماده است و ربات با Long Polling اجرا می‌شود.

مهم: فایل‌های SQLite روی filesystem موقت سرویس رایگان ممکن است در restart یا deploy از بین بروند. برای داده واقعی از PostgreSQL یا دیسک پایدار استفاده کنید. همچنین محدودیت‌های sleep پلن رایگان Render می‌تواند فعالیت 24/7 ربات را متوقف کند؛ برای سرویس دائمی از پلن Worker/paid یا VPS استفاده کنید.

## Railway

- repository را Import کنید.
- متغیرهای `.env.example` را در Variables بسازید.
- یک PostgreSQL service اضافه و `DATABASE_URL` را به ربات متصل کنید.
- Start Command: `python -m bot`
- Health endpoint: `/health`

## VPS با systemd

پروژه را در `/opt/persian-shop` قرار دهید، virtualenv و `.env` بسازید، سپس فایل `deploy/persian-shop.service` را در systemd کپی کنید:

```bash
sudo cp deploy/persian-shop.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now persian-shop
sudo systemctl status persian-shop
```

## تست و کیفیت

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

CI همین بررسی‌ها را در هر Push و Pull Request اجرا می‌کند.

## امنیت

- توکن هرگز داخل کد یا Git ذخیره نمی‌شود.
- فایل `.env` در `.gitignore` است.
- عملیات کیف پول idempotent و دارای مانده قبل/بعد است.
- callbackها کوتاه و زیر محدودیت 64 بایت Telegram هستند.
- دسترسی پنل با Admin table و نقش‌ها کنترل می‌شود.
- خطاهای داخلی log می‌شوند ولی جزئیات حساس برای کاربر نمایش داده نمی‌شود.
- اگر توکنی قبلاً در چت، تصویر یا repository فرستاده شده است، آن را در BotFather فوراً Revoke و یک توکن تازه تولید کنید.

جزئیات بیشتر در [SECURITY.md](SECURITY.md) آمده است.
