# Snapshot سیستم Premium / Custom Emoji

## معماری

پیاده‌سازی اصلی Premium Emoji در این پروژه در سورس قرار دارد و همراه بک‌آپ است، مخصوصاً:

- `bot/core/emojis.py`
- `bot/modules/admin/report_emojis.py`
- `bot/services/order_reports.py`
- Product/Module fields مربوط به `custom_emoji_id`

### قواعد UI

- Emoji در Button قبل از متن قرار می‌گیرد.
- Localization نباید Custom Emoji ID یا Button style را حذف کند.
- در صورت رد شدن Custom Emoji توسط Telegram، Unicode fallback استفاده می‌شود.
- Button Premium Emoji از `icon_custom_emoji_id` استفاده می‌کند در صورت مجاز بودن.

## Report Emoji Settings

Setting keyها:

| Slot | Setting key | Snapshot ID |
| --- | --- | --- |
| shop | `order_report_emoji_shop` | بازیابی قطعی نشد |
| buyer | `order_report_emoji_buyer` | `5453940933512944480` |
| product | `order_report_emoji_product` | `5294476812221439592` |
| amount | `order_report_emoji_amount` | `5325685779760962109` |
| time | `order_report_emoji_time` | `5395355586730679238` |
| bot | `order_report_emoji_bot` | `5938534225140519372` |
| button | `order_report_emoji_button` | بازیابی قطعی نشد |

دو ID نامشخص عمداً حدس زده نشده‌اند. برای Clone کاملاً یکسان، مالک باید آن‌ها را از نسخه فعلی با `/reportemoji` یا از Sticker/Custom Emoji اصلی دوباره ثبت کند.

## اولویت Product Emoji در گزارش

منطق جدید و صحیح گزارش باید این ترتیب را داشته باشد:

1. Report-specific product emoji (`/reportemoji product`)
2. Product-specific custom emoji
3. Contextual/category emoji

یعنی تنظیم Report باید روی Emoji خود Product اولویت داشته باشد.

## محدودیت Telegram Channel

Validation یک Custom Emoji در Private Chat تضمین نمی‌کند که همان Entity در Channel هم رندر شود. Telegram Bot API برای Custom Emoji در Channel محدودیت‌های account/bot eligibility دارد. اگر Request بدون خطا ارسال شد ولی Emoji در Channel Unicode شد، قبل از تغییر کد eligibility Telegram/Fragment را بررسی کنید.

`premium_emoji_used=True` در log این نسخه به معنی انتخاب مسیر Rich request است و اثبات پیکسلی رندر Telegram نیست.
