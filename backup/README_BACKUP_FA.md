# بک‌آپ کامل پروژه Riva / Persian Shop

تاریخ تهیه بک‌آپ: 2026-09-02

این شاخه فقط برای ساخت بسته‌ی بک‌آپ ایجاد شده است و روی شاخه‌ی `main` و سرویس Production تغییری اعمال نمی‌کند.

## مبنای سورس

- Repository: `notcoinsapourt-web/Riva`
- Production branch: `main`
- Production source commit: `fc0e7ae989572a3297079182f729dbf8951ecd21`
- Bot username فعلی: `@Persionshope_bot`
- Telegram bot numeric ID: `8861317112`

بسته‌ی ZIP نهایی شامل این موارد است:

1. `project-source/` — کپی دقیق همه فایل‌های Track‌شده‌ی پروژه در Commit بالا، شامل سورس، Assets، Migrationها، تست‌ها، Docker و فایل‌های Deploy.
2. `git/Riva-full-history.bundle` — Git Bundle برای بازیابی Repository همراه با تاریخچه Git.
3. `backup-docs/MASTER_RESTORE_PROMPT_FA.md` — پرامپت مادر برای تحویل پروژه به ChatGPT یا هر هوش مصنوعی/توسعه‌دهنده دیگر.
4. `backup-docs/RESTORE_GUIDE_FA.md` — راهنمای قدم‌به‌قدم ساخت یک ربات جدید با همین معماری و ظاهر.
5. `backup-docs/RAILWAY_CURRENT_STATE.json` — Snapshot تنظیمات قابل مشاهده Railway بدون Secretهای واقعی.
6. `backup-docs/ENV_TEMPLATE_CURRENT.env` — الگوی Environment Variables برای نصب جدید؛ Secretها عمداً Placeholder هستند.
7. `backup-docs/PREMIUM_EMOJI_STATE.md` — وضعیت سیستم Premium/Custom Emoji و IDهای گزارش که از تنظیمات فعلی قابل بازیابی بوده‌اند.
8. `backup-docs/RESTORE_CHECKLIST_FA.md` — چک‌لیست تست نهایی قبل از انتقال کاربران.
9. `SOURCE_COMMIT.txt` — Commit مرجع Production.

## نکته امنیتی مهم

این بک‌آپ عمداً توکن واقعی BotFather، پسورد/URL واقعی دیتابیس و Secretهای درگاه را داخل فایل قرار نمی‌دهد. این اطلاعات باید هنگام نصب جدید از منبع امن خود مالک پروژه وارد شوند. قرار دادن Token یا Database password داخل ZIP قابل اشتراک، ریسک تصاحب ربات یا دیتابیس دارد.

کد، ساختار دیتابیس، Seed محصولات، تصاویر، متن‌ها، منطق Premium Emoji، منطق کیف پول و پرداخت دستی، گزارش سفارش، کمپین تست گزارش، ترجمه‌ها، پنل مدیریت و تست‌ها داخل سورس موجود است.

## محدودیت Snapshot

فایل Git شامل سورس کامل پروژه است؛ اما دیتابیس Runtime خود Railway (کاربران واقعی، سفارش‌های واقعی، Wallet balanceها، ActivityLog و تغییراتی که فقط در DB انجام شده‌اند) داخل Repository نیست. برای Clone کردن «ظاهر و قابلیت‌ها» نیازی به این داده‌های کاربری نیست و بهتر است در ربات جدید منتقل نشوند. اگر هدف Migration کامل داده‌های Production باشد باید جداگانه از PostgreSQL/SQLite فعلی یک Dump رمزگذاری‌شده تهیه شود.

برای بازسازی ربات جدید، از `MASTER_RESTORE_PROMPT_FA.md` و سپس `RESTORE_GUIDE_FA.md` استفاده کنید.
