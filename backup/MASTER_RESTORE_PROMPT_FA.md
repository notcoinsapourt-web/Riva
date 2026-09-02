# پرامپت مادر بازسازی کامل ربات Persian Shop / Riva

> این فایل را همراه پوشه `project-source/` به یک هوش مصنوعی یا توسعه‌دهنده بده. هدف این است که پروژه روی **Bot Token جدید، کانال جدید و Railway Project جدید** با همان رفتار، ساختار، ظاهر و قابلیت‌ها بازسازی شود؛ بدون اینکه منطق‌های تأییدشده حذف یا ساده‌سازی شوند.

---

## نقش و مأموریت

تو مسئول بازسازی، Deploy و تست کامل یک Telegram Shop Bot به نام Persian Shop هستی. سورس مرجع در همین بک‌آپ موجود است و **اولویت مطلق با اجرای همان سورس و حفظ رفتار فعلی آن است**. از بازنویسی بی‌دلیل، تغییر معماری، Reset کردن Database یا حذف قابلیت‌های موجود خودداری کن.

نسخه مرجع Production از Repository `notcoinsapourt-web/Riva` و Commit زیر تهیه شده است:

`fc0e7ae989572a3297079182f729dbf8951ecd21`

Stack اصلی:

- Python 3.12
- Aiogram 3.x
- SQLAlchemy Async
- SQLite برای توسعه / PostgreSQL برای Production
- Alembic
- Telegram Bot API
- Railway
- GitHub Actions (`ruff` + `pytest`)
- Long Polling
- Health endpoint: `/health`

Start command:

`python -m bot`

---

# 1. قانون طلایی بازسازی

هیچ بخشی را صرفاً برای «تمیزتر شدن» حذف یا ساده نکن. ابتدا پروژه را دقیقاً از روی سورس بالا بیاور، Migration/Schema را بساز، Seedها را اجرا کن، سپس فقط مقادیر مخصوص Bot جدید را تنظیم کن.

موارد زیر باید حفظ شوند:

- محصولات، دسته‌بندی‌ها، ترتیب، نام‌ها، قیمت‌ها، تصاویر و توضیحات موجود در Seed/Source.
- Premium/Custom Emoji infrastructure.
- ترتیب Emoji قبل از متن دکمه‌ها.
- Button styleهای Native Telegram.
- فارسی/انگلیسی و منطق Localization.
- کیف پول، کارت‌به‌کارت، USDT، رسید و تأیید ادمین.
- سیستم Support/Ticket.
- Admin Panel و نقش‌ها.
- Order lifecycle و refund.
- گزارش سفارش موفق به کانال.
- Retry/Reconciliation گزارش سفارش.
- تنظیم Premium Emoji گزارش از `/reportemoji`.
- قابلیت Channel Lock / Forced Join.
- متن‌های قابل ویرایش از Admin.
- Anti-spam و error middleware.
- Campaign موقت تست گزارش کانال (در نصب جدید فقط در صورت نیاز روشن شود).

از ایجاد سفارش، کاربر یا تراکنش ساختگی در دیتابیس برای تست ظاهری گزارش خودداری کن؛ مسیر Synthetic Report موجود برای همین هدف طراحی شده است.

---

# 2. هویت نصب جدید

در بازسازی جدید، این مقادیر باید با مقادیر جدید جایگزین شوند:

- `BOT_TOKEN`: Token جدید از BotFather.
- `ADMIN_IDS`: Telegram ID مالک/مدیر جدید.
- `ORDER_REPORT_CHANNEL_ID`: کانال گزارش جدید.
- `REPORT_TEST_CAMPAIGN_CHANNEL_ID`: اگر تست گزارش مصنوعی لازم است، یک **کانال خصوصی تست جداگانه**.
- `SUPPORT_USERNAME`: یوزرنیم پشتیبانی جدید در صورت نیاز.
- `DATABASE_URL`: دیتابیس جدید.

مقادیر Bot فعلی فقط برای Reference هستند و نباید در Clone جدید استفاده شوند:

- Username فعلی: `@Persionshope_bot`
- Bot numeric ID فعلی: `8861317112`
- Report chat ID فعلی مشاهده‌شده: `-1004360571325`

---

# 3. معماری و ساختار پروژه

ساختار مرجع را حفظ کن:

```text
bot/
├── app.py
├── config.py
├── core/
│   ├── callbacks / ui / security helpers
│   ├── emojis.py
│   ├── customer_localization.py
│   ├── language.py
│   └── middlewares.py
├── database/
│   ├── models.py
│   ├── enums.py
│   ├── session.py
│   ├── bootstrap.py
│   ├── catalog_seed.py
│   └── product_content.py
├── locales/
│   ├── fa.json
│   └── en.json
├── modules/
│   ├── start/
│   ├── catalog/
│   ├── orders/
│   ├── wallet/
│   ├── referral/
│   ├── tickets/
│   ├── report_test/
│   └── admin/
├── services/
│   ├── order_reports.py
│   ├── report_test_campaign.py
│   ├── settings.py
│   ├── users.py
│   ├── channels.py
│   └── ...
└── web/
    └── health.py

alembic/
assets/
tests/
deploy/
.github/workflows/
```

از همان package boundaries استفاده کن تا تست‌ها و importها بدون تغییر کار کنند.

---

# 4. رابط کاربری و زبان

## فارسی

نسخه فارسی مبنای اصلی است. متن‌های دستی فارسی، محصولات و FAQ نباید با ترجمه ماشینی بازنویسی شوند مگر صریحاً لازم باشد.

## انگلیسی

نسخه انگلیسی باید:

- Welcome صحیح و کامل داشته باشد.
- FAQ انگلیسی از نسخه فارسی فعلی هم‌راستا باشد.
- هیچ Button کاربر به شکل نصف فارسی/نصف انگلیسی نمایش داده نشود.
- Middleware پاک‌سازی English button labelها حفظ شود.

## دکمه Change language

پس از `/start` دکمه `🌐 Change language` / معادل فارسی باید در Reply Keyboard پایین Telegram باقی بماند و بعد از یک ثانیه ناپدید نشود.

دو پیام تأیید قدیمی تغییر زبان که قبلاً نمایش داده می‌شدند نباید برگردند:

- «زبان ربات با موفقیت تغییر کرد.»
- «از دکمه پایین می‌توانید زبان ربات را تغییر دهید.»

## Welcome

Welcome فارسی موجود را بدون درخواست مالک تغییر نده. Welcome انگلیسی از `bot/core/customer_localization.py` و منطق فعلی استفاده کند.

---

# 5. Premium / Custom Emoji

این پروژه از Telegram Custom/Premium Emoji در دکمه‌ها و بخش‌های پشتیبانی‌شده استفاده می‌کند.

قواعد:

1. Emoji قبل از متن Button باشد.
2. تغییر زبان نباید `custom_emoji_id` یا style دکمه را از بین ببرد.
3. اگر Telegram یک Custom Emoji را برای Bot/Chat مجاز نداند، fallback Unicode باید کار کند.
4. `PremiumEmojiFallbackMiddleware` حفظ شود.
5. `icon_custom_emoji_id` برای دکمه‌های Native Telegram در صورت مجاز بودن استفاده شود.
6. Moduleهای Rules و Profile نیز جزو سیستم Emoji هستند و نباید از آن حذف شوند.
7. Product-specific Emoji و Report-specific Emoji دو مفهوم جدا هستند.

### نکته محدودیت Telegram

Telegram Bot API ممکن است Custom Emoji را در Channel با محدودیت بیشتری نسبت به Private/Group/Supergroup اعمال کند. Owner Premium به تنهایی تضمین نمی‌کند که Channel Custom Emoji رندر شود. اگر Channel Emoji رندر نشد، اول محدودیت Bot API/Fragment eligibility را بررسی کن و کد را به اشتباه Reset نکن.

---

# 6. کاتالوگ و محصولات

کاتالوگ Seed فعلی داخل سورس قرار دارد. `catalog_seed.py` و `product_content.py` مرجع هستند.

ویژگی‌های هر محصول:

- Category
- Name
- Description اختصاصی
- Price (integer تومان)
- Photo
- Emoji
- Custom Emoji ID در صورت تنظیم
- Input prompt اختصاصی
- Sort order
- Active status

در UI فروشگاه ابتدا Category/نوع سرویس نمایش داده شود، سپس صفحه توضیح محصول و بعد Quantity/Input مورد نیاز.

متن‌ها نباید Generic و کم‌کیفیت شوند. Product descriptionها و نکات محصول اختصاصی باقی بمانند.

در Admin، لیست محصولات Grouped/مرتب باشد تا مدیریت تعداد زیاد محصول ساده باشد.

**واحد پول دیتابیس integer تومان است و برای مبلغ از float استفاده نشود.**

---

# 7. کیف پول و شارژ دستی

Flow شارژ کیف پول:

1. کاربر اول مبلغ شارژ را وارد می‌کند.
2. سپس روش پرداخت را انتخاب می‌کند.
3. روش‌های فعلی شامل Card-to-card و USDT هستند.
4. کاربر رسید/اسکرین‌شات می‌فرستد.
5. Admin رسید را تأیید می‌کند.
6. فقط پس از تأیید، Wallet با تراکنش اتمیک شارژ می‌شود.

Card number، Card holder، متن راهنما و Crypto address از Admin قابل مدیریت باشند.

USDT فعلی در منطق پروژه از BEP20 پشتیبانی می‌کند و conversion لحظه‌ای در Flow مرتبط باید حفظ شود اگر Provider/Price source فعال است.

پیام‌های اضافی مانند «Quick menu enabled» نباید نمایش داده شوند.

دکمه Settings و Add method باید کار کنند و Placeholder «not set» به کاربر نهایی تحمیل نشود.

---

# 8. Order lifecycle

Order flow باید Transaction-safe و idempotent باشد.

ویژگی‌ها:

- خرید از Wallet.
- جلوگیری از Double order / Double charge.
- Order status history.
- وضعیت‌های سفارش موجود در Enum/Source.
- اعلان تغییر وضعیت.
- Refund یک‌باره هنگام Cancel در شرایط تعریف‌شده.
- Admin بتواند Order را مدیریت کند.

هیچ تغییر مربوط به Report نباید Checkout را Fail کند. Report یک side effect است و شکست Report نباید سفارش موفق را خراب کند.

---

# 9. گزارش سفارش موفق به کانال

Service مرجع: `bot/services/order_reports.py`

پس از سفارش موفق، Report به Channel تعیین‌شده ارسال شود و شامل حداقل این اطلاعات باشد:

- Shop
- Buyer masked ID
- Product
- Amount
- Time
- Bot
- CTA button

Buyer ID در Report واقعی باید Mask شود و اطلاعات خصوصی کامل کاربر افشا نشود.

## Retry / Reconciliation

اگر ارسال لحظه‌ای Report شکست خورد، Background worker سفارش‌های اخیر را بررسی می‌کند و Report جاافتاده را Retry می‌کند.

Current production-style values:

- reconcile interval: `30` ثانیه
- reconciliation lookback: `2` ساعت

از ActivityLog برای idempotency استفاده شود تا Report تکراری ارسال نشود.

## اولویت Emoji محصول در Report

برای Report Channel، Emoji تنظیم‌شده از `/reportemoji product` باید اولویت بالاتر از Custom Emoji خود محصول داشته باشد.

منطق مورد انتظار:

```python
configured_report_product_emoji
or product.custom_emoji_id
or contextual_emoji_id
```

این رفتار در سورس مرجع اعمال شده و نباید به حالت قدیمی برگردد.

---

# 10. مدیریت Premium Emoji گزارش با /reportemoji

فرمان Admin:

`/reportemoji`

Slotها:

- `shop`
- `buyer`
- `product`
- `amount`
- `time`
- `bot`
- `button`

Setting keyهای فعلی:

- `order_report_emoji_shop`
- `order_report_emoji_buyer`
- `order_report_emoji_product`
- `order_report_emoji_amount`
- `order_report_emoji_time`
- `order_report_emoji_bot`
- `order_report_emoji_button`

IDهای Report Emoji که در Snapshot گفتگو به‌طور قطعی ثبت شده‌اند:

- buyer: `5453940933512944480`
- product: `5294476812221439592`
- amount: `5325685779760962109`
- time: `5395355586730679238`
- bot: `5938534225140519372`

IDهای `shop` و `button` در داده قابل دسترس این بک‌آپ به‌طور قطعی بازیابی نشدند؛ اگر Clone باید دقیقاً همان Stickerها را داشته باشد، مالک باید این دو ID را از ربات فعلی/Telegram مجدداً وارد کند. **هیچ ID را حدس نزن.**

`/reportemoji test` باید از مسیر Report واقعی برای Preview استفاده کند؛ اما نتیجه `premium_emoji_used=True` را به‌عنوان اثبات قطعی Render شدن در Channel تلقی نکن، چون Telegram می‌تواند entity را قبول کند ولی رندر نکند.

---

# 11. کمپین موقت تست Report Channel

Service: `bot/services/report_test_campaign.py`

این قابلیت برای مشاهده مسیر Report در یک Channel خصوصی ساخته شده و **نباید Order واقعی بسازد**.

قواعد:

- فقط Channel خصوصی.
- Bot باید Admin و دارای Post Messages باشد.
- Productها از DB واقعی انتخاب شوند.
- فقط Productهای Active با Price > حد تعیین‌شده.
- Buyer ID مصنوعی و Masked باشد.
- Order/User/Wallet transaction ساخته نشود.
- ActivityLog داخلی synthetic=true ثبت شود.
- ظاهر پیام می‌تواند دقیقاً شبیه Report Production باشد چون Channel تست خصوصی است.
- Schedule pseudo-random اما deterministic باشد.
- پس از restart، Slotهای ارسال‌شده از ActivityLog تشخیص داده شوند تا Duplicate نشود.

Snapshot آخرین تنظیم تست:

- Duration: 14 روز
- Daily reports: **30**
- Min price: **300000 تومان** (شرط کد: strictly greater than)
- Poll interval: حدود 20 ثانیه
- شروع ثبت‌شده در Runtime: `2026-09-02T12:34:25.874536+00:00`
- پایان همان کمپین: `2026-09-16T12:34:25.874536+00:00`
- Campaign ID پس از تغییر به 30/day: `2bbc3c2b14a4facd`

در نصب جدید، این Campaign را پیش‌فرض `false` نگه دار مگر مالک صریحاً برای تست بخواهد. در حالت صحیح بهتر است Test Channel با Production Report Channel جدا باشد.

---

# 12. Channel Lock / Forced Join

Admin بتواند:

- Forced Join را Enable/Disable کند.
- یک یا چند Channel تعیین کند.
- قبل از ورود کاربر به Main Menu عضویت را بررسی کند.

Bot باید در Channelهای لازم دسترسی مناسب داشته باشد. خطاهای `chat not found` باید به پیام Validation تمیز تبدیل شوند و نباید User ORM object بعد از rollback باعث `DetachedInstanceError` شود. اگر این خطا در Clone مشاهده شد، middleware error handling را با session lifecycle بررسی کن؛ قابلیت Channel Lock را حذف نکن.

---

# 13. Admin Panel

Admin panel داخل Telegram حفظ شود.

قابلیت‌ها:

- Orders
- Products
- Categories
- Users
- Wallet adjustment
- Admins/Roles
- Discounts
- Broadcast
- Tickets
- Settings
- Modules
- Payment methods
- Channel lock
- Report emoji configuration

Roles:

- owner
- admin
- operator
- support

آخرین Owner نباید accidentally حذف/تنزل داده شود.

---

# 14. Settings و متن‌های قابل ویرایش

متن Main Menu / Welcome / Rules / FAQ / Support و متن‌های Category تا حدی که سورس فعلی اجازه می‌دهد از Admin قابل ویرایش باشند.

قاعده مهم: تغییر Locale یا Deploy نباید متن فارسی سفارشی DB را با Seed قدیمی overwrite کند.

Seed version markerهای موجود برای همین حفظ شوند.

---

# 15. Database و Seed

Production جدید ترجیحاً PostgreSQL باشد.

برای Database تازه:

```bash
alembic upgrade head
```

یا Flow فعلی `create_schema + seed_database` طبق سورس اجرا شود.

Seedها شامل:

- Settings
- Modules
- Categories
- Products
- Initial owner/admin

Seed باید idempotent باشد و Admin edits موجود را در restart بی‌دلیل overwrite نکند.

اگر Database از قبل توسط `create_all` ساخته شده است، Migration strategy را قبل از upgrade بررسی کن و در صورت نیاز `alembic stamp head` انجام بده.

---

# 16. Railway — پیکربندی مرجع

Snapshot فعلی Production:

- Railway project ID: `d982d4fd-9723-4b06-877f-42fc3adc892d`
- Service ID: `259a16b1-09df-4033-8db5-15e1b881ee23`
- Environment ID: `50266aaf-285b-4517-baab-6f3656e480b7`
- Service name: `persian-shop-bot`
- Source repo: `notcoinsapourt-web/Riva`
- Builder: `RAILPACK`
- Build environment: `V3`
- Runtime: `V2`
- Start command: `python -m bot`
- Healthcheck: `/health`
- Healthcheck timeout: `300`
- Region: `sfo`
- Replicas: `1`
- Service domain snapshot: `persian-shop-bot-production.up.railway.app`

برای Clone جدید Project/Service IDها باید جدید باشند. IDهای بالا فقط Reference هستند.

نکته: در این پروژه مشاهده شده Railway `redeploy` ممکن است همان Commit قبلی را دوباره Deploy کند. برای Pull شدن Source جدید از GitHub، Deploy باید واقعاً به Source جدید متصل شود/Push جدید Trigger کند؛ صرف Redeploy همیشه معادل Pull latest main نیست.

در Rolling deploy ممکن است برای چند ثانیه `TelegramConflictError` دیده شود چون دو replica قدیم/جدید همزمان `getUpdates` می‌زنند. زمانی Stable محسوب شود که deployment قدیمی Removed و connection جدید Established شده باشد.

---

# 17. Environment Variables

از فایل `ENV_TEMPLATE_CURRENT.env` استفاده کن.

Secretهای زیر را از مالک بگیر و هرگز Commit نکن:

- BOT_TOKEN
- DATABASE_URL (اگر شامل password است)
- Payment provider secrets

Variableهای Functional مهم:

- ADMIN_IDS
- DEFAULT_LANGUAGE
- TIMEZONE
- SHOP_NAME
- ORDER_REPORT_CHANNEL_ID
- ORDER_REPORT_RECONCILE_INTERVAL_SECONDS
- ORDER_REPORT_RECONCILE_HOURS
- REPORT_TEST_CAMPAIGN_*
- PAYMENTS_ENABLED
- PAYMENT_INTEGRATION_CONFIRMED
- RATE_LIMIT_REQUESTS
- RATE_LIMIT_WINDOW_SECONDS
- HEALTH_SERVER_ENABLED

---

# 18. Payments

Provider code برای روش‌های آنلاین وجود دارد، اما پرداخت آنلاین را بدون Credential واقعی و تست Sandbox فعال نکن.

هر دو Feature gate زیر باید برای Live payment صریحاً true شوند:

```dotenv
PAYMENTS_ENABLED=true
PAYMENT_INTEGRATION_CONFIRMED=true
```

اگر فقط Manual Card/USDT استفاده می‌شود، Online provider را false نگه دار.

---

# 19. تست‌های اجباری قبل از تحویل

در هر Clone جدید اجرا کن:

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

سپس Smoke test Telegram:

1. `/start` فارسی.
2. Change language به انگلیسی و برگشت.
3. Reply keyboard زبان بعد از navigation باقی بماند.
4. تمام buttonهای انگلیسی بدون متن فارسی.
5. Premium Emoji IDs از بین نرفته باشند.
6. Category list.
7. Product details.
8. Quantity/input flow.
9. Wallet top-up amount-first.
10. Card method.
11. Crypto method.
12. Receipt upload.
13. Admin receipt approval.
14. Wallet credit idempotency.
15. Order checkout.
16. Admin order status change.
17. Order report channel.
18. Report retry/reconciliation.
19. `/reportemoji` set + test.
20. Forced join enable/disable.
21. Ticket flow.
22. Admin roles.
23. `/health` = HTTP 200.
24. Restart service و بررسی عدم Duplicate report/transaction.

در صورت شکست هر تست، مشکل را Fix و مجدداً کل تست‌های مرتبط را اجرا کن؛ workaround ظاهری که state را خراب کند نپذیر.

---

# 20. مواردی که نباید هنگام Clone انجام شوند

- استفاده از Token Bot فعلی.
- استفاده از دیتابیس Production فعلی برای Bot جدید مگر Migration عمدی باشد.
- Reset کردن Product catalog.
- حذف Premium Emoji برای ساده‌سازی.
- تبدیل تمام متن‌ها به Generic translation.
- حذف Admin RBAC.
- فعال‌کردن Payments بدون Credential واقعی.
- ایجاد Orderهای Fake برای تست Report.
- ذخیره Secret در GitHub.
- ایجاد چند Polling instance دائمی برای یک Bot Token.

---

# 21. معیار «دقیقاً مثل نسخه فعلی»

Clone زمانی قابل قبول است که:

- Menu hierarchy و Button labels با نسخه Source یکی باشند.
- Product catalog و Assets یکی باشند.
- Language behavior یکی باشد.
- Premium Emoji infrastructure حفظ شده باشد.
- Admin capabilities یکی باشد.
- Wallet/Order transactional behavior یکی باشد.
- Report cards و Retry یکی باشد.
- Health/Deploy strategy درست باشد.
- `ruff` و `pytest` موفق باشند.
- هیچ Secret قدیمی یا User data قدیمی ناخواسته منتقل نشده باشد.

در موارد اختلاف بین این Prompt و سورس، **سورس Commit مرجع اولویت فنی دارد**؛ مگر این Prompt صریحاً یک رفتار جدیدتر از README را مشخص کرده باشد (مانند daily report = 30 و اولویت `/reportemoji product`).

---

# دستور نهایی به عامل بازسازی

بدون تغییر سلیقه‌ای پروژه را از `project-source/` بالا بیاور. ابتدا Config جدید و Database جدید را بساز، سپس Deploy کن، Smoke test و CI را کامل اجرا کن و فقط بعد از تأیید همه تست‌ها Bot جدید را آماده استفاده اعلام کن. هر چیزی که به Token/Channel/Database نصب قبلی وابسته است باید با مقدار جدید جایگزین شود؛ اما طراحی، Product content، Emoji architecture، UI flow و business logic باید حفظ شود.
