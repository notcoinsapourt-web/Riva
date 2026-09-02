# چک‌لیست تحویل Clone جدید Persian Shop

هر مورد باید قبل از اعلام «آماده» بودن ربات جدید تأیید شود.

## Source و Deploy

- [ ] Source دقیقاً از Commit مرجع یا `project-source/` بازیابی شده.
- [ ] Secret واقعی داخل Git نیست.
- [ ] `ruff check .` موفق.
- [ ] `pytest -q` موفق.
- [ ] Railway build موفق.
- [ ] `/health` پاسخ 200.
- [ ] فقط یک Polling instance دائمی برای Token فعال است.

## Start / Language

- [ ] `/start` فارسی صحیح.
- [ ] Welcome فارسی بدون Reset شدن متن سفارشی.
- [ ] دکمه تغییر زبان دائماً در Reply keyboard قابل دسترس.
- [ ] تغییر به English صحیح.
- [ ] Welcome انگلیسی صحیح.
- [ ] FAQ انگلیسی صحیح.
- [ ] هیچ دکمه انگلیسی با متن مخلوط فارسی وجود ندارد.
- [ ] دو پیام قدیمی تأیید زبان نمایش داده نمی‌شوند.

## Premium Emoji

- [ ] Emoji قبل از Button text.
- [ ] Button style حفظ شده.
- [ ] Product Custom Emoji حفظ شده.
- [ ] Module Custom Emoji حفظ شده.
- [ ] Rules/Profile داخل Emoji system هستند.
- [ ] `/reportemoji` برای همه Slotها کار می‌کند.
- [ ] `/reportemoji test` کار می‌کند.
- [ ] اگر Channel Custom Emoji رندر نمی‌شود eligibility Telegram بررسی شده.

## Catalog

- [ ] Categoryها کامل.
- [ ] Productها کامل.
- [ ] تصاویر Productها لود می‌شوند.
- [ ] Priceها صحیح و تومان integer هستند.
- [ ] Descriptionها اختصاصی و باکیفیت هستند.
- [ ] Input prompt هر Product صحیح است.
- [ ] Admin product list مرتب/قابل مدیریت است.

## Wallet / Payment

- [ ] کاربر اول مبلغ شارژ را وارد می‌کند.
- [ ] Card-to-card نمایش صحیح دارد.
- [ ] Crypto/USDT نمایش صحیح دارد.
- [ ] Receipt upload کار می‌کند.
- [ ] Admin receipt notification می‌رسد.
- [ ] Approval دقیقاً یک بار Wallet را شارژ می‌کند.
- [ ] Rejection موجودی را تغییر نمی‌دهد.
- [ ] Settings/Add methodها کار می‌کنند.

## Orders

- [ ] Checkout از Wallet صحیح.
- [ ] Double-click باعث Double charge نمی‌شود.
- [ ] Order history صحیح.
- [ ] Admin status transition صحیح.
- [ ] Cancel/refund idempotent.
- [ ] Notification کاربر صحیح.

## Order Report Channel

- [ ] Channel جدید تنظیم شده.
- [ ] Bot Admin و دارای Post Messages است.
- [ ] Report فقط یک بار برای Order ارسال می‌شود.
- [ ] Buyer masked است.
- [ ] Product/amount/time/bot صحیح است.
- [ ] CTA button صحیح است.
- [ ] Report failure باعث Fail شدن Checkout نمی‌شود.
- [ ] Background reconciliation Report جاافتاده را Recover می‌کند.
- [ ] `/reportemoji product` بر Product custom emoji اولویت دارد.

## Report Test Campaign — فقط در صورت استفاده

- [ ] Channel تست خصوصی و ترجیحاً جدا از Production report است.
- [ ] `REPORT_TEST_CAMPAIGN_ENABLED=true` فقط برای دوره تست.
- [ ] 30 Report/day تنظیم شده.
- [ ] 14 days تنظیم شده.
- [ ] Product فقط Active و Price > 300000 تومان.
- [ ] Buyer pseudo ID متفاوت/Masked.
- [ ] هیچ Order واقعی ساخته نمی‌شود.
- [ ] هیچ Wallet transaction واقعی ساخته نمی‌شود.
- [ ] ActivityLog جلوی Duplicate را می‌گیرد.

## Forced Join / Support / Admin

- [ ] Forced join روشن/خاموش می‌شود.
- [ ] چند Channel قابل تنظیم است.
- [ ] Support ticket ایجاد و پاسخ داده می‌شود.
- [ ] Owner/Admin/Operator/Support permissions صحیح.
- [ ] آخرین Owner قابل حذف/تنزل ناخواسته نیست.
- [ ] Broadcast تست کنترل‌شده شده.

## Restart Safety

- [ ] Restart باعث Reset Product/Settings نمی‌شود.
- [ ] Restart باعث Duplicate Wallet credit نمی‌شود.
- [ ] Restart باعث Duplicate Order Report نمی‌شود.
- [ ] Database persist است.
- [ ] Old deployment پس از Rolling deploy Removed شده.

وقتی همه موارد مرتبط تیک خوردند، Clone جدید از نظر عملکردی با نسخه مرجع هم‌تراز محسوب می‌شود.
