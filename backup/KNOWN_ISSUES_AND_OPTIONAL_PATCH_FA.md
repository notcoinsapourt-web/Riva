# نکته شناخته‌شده در Source Snapshot

سورس Production مرجع (`fc0e7ae989572a3297079182f729dbf8951ecd21`) در Railway در حال اجراست، اما GitHub Actions همان Commit یک Failure صرفاً Lint دارد:

```text
E501 Line too long (101 > 100)
bot/modules/report_test/router.py:86
```

این مورد رفتار Runtime را تغییر نمی‌دهد و مربوط به طول یک رشته‌ی Log است. `pytest` در آن Run اجرا نشد چون Workflow بعد از Failure راف متوقف شد.

اگر هنگام Restore می‌خواهید CI کاملاً سبز شود، Patch اختیاری `OPTIONAL_PATCH_RUFF_E501.diff` را اعمال کنید. Patch فقط رشته‌ی Log را در دو literal کنار هم می‌شکند و هیچ منطق، پیام Telegram، دیتابیس، Product یا Emoji را تغییر نمی‌دهد.

بعد از اعمال Patch:

```bash
ruff check .
pytest -q
```

هر دو را اجرا و نتیجه را ثبت کنید.

برای حفظ Snapshot تاریخی، `project-source/` عمداً همان Source واقعی Production را نگه می‌دارد و Patch روی آن از قبل اعمال نشده است.
