from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import urlparse

from bot.core.exceptions import ValidationError


class ProductLike(Protocol):
    name: str
    description: str
    price: int
    photo_file_id: str | None
    input_prompt: str


@dataclass(frozen=True, slots=True)
class QuantityPolicy:
    base_quantity: int
    minimum: int
    maximum: int
    step: int
    label: str = "تعداد"

    def validate(self, quantity: int) -> int:
        if quantity < self.minimum or quantity > self.maximum:
            raise ValidationError(f"تعداد باید بین {self.minimum:,} تا {self.maximum:,} باشد.")
        if quantity % self.step:
            raise ValidationError(f"تعداد باید مضربی از {self.step:,} باشد.")
        return quantity


NON_SCALABLE_SLUG_PARTS = ("starter-pack", "viral-pack", "future-posts")
PLATFORM_SUFFIXES = (
    " اینستاگرام",
    " تلگرام",
    " تیک‌تاک",
    " یوتیوب",
    " تردز",
    " ایکس",
    " دیسکورد",
    " توییچ",
    " لینکدین",
)
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
LEADING_QUANTITY = re.compile(r"^[\d۰-۹٠-٩]+(?:\s*هزار)?\s+")


def product_slug(product: ProductLike) -> str:
    source = product.photo_file_id or ""
    return PurePosixPath(urlparse(source).path).stem.lower()


def quantity_policy(product: ProductLike) -> QuantityPolicy | None:
    return quantity_policy_for_slug(product_slug(product))


def quantity_policy_for_slug(slug: str) -> QuantityPolicy | None:
    if not slug or any(part in slug for part in NON_SCALABLE_SLUG_PARTS):
        return None
    if not slug.startswith(("instagram-", "telegram-", "tiktok-", "youtube-", "social-")):
        return None

    base = _base_quantity(slug)
    if base is None:
        return None
    if "comments" in slug:
        return QuantityPolicy(base, 10, 10_000, 10, "کامنت")
    if "subscribers" in slug:
        return QuantityPolicy(base, 50, 20_000, 50, "سابسکرایبر")
    if "followers" in slug or "members" in slug:
        return QuantityPolicy(base, 100, 100_000, 100, "کاربر")
    return QuantityPolicy(base, 100, 1_000_000, 100, "تعداد")


def display_name(product: ProductLike) -> str:
    name = LEADING_QUANTITY.sub("", product.name).strip()
    if quantity_policy(product) is None:
        return name
    for suffix in PLATFORM_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def subtotal_for(product: ProductLike, quantity: int) -> int:
    policy = quantity_policy(product)
    if policy is None:
        if quantity != 1:
            raise ValidationError("این محصول با تعداد ثابت ارائه می‌شود.")
        return product.price
    policy.validate(quantity)
    raw = (product.price * quantity + policy.base_quantity - 1) // policy.base_quantity
    return max(1_000, ((raw + 99) // 100) * 100)


def parse_quantity(value: str) -> int:
    normalized = value.translate(PERSIAN_DIGITS)
    normalized = normalized.replace(",", "").replace("٬", "").replace(" ", "")
    if not normalized.isdecimal():
        raise ValidationError("تعداد را فقط به‌صورت عدد وارد کنید؛ مثال: 2500")
    return int(normalized)


def order_requirements(product: ProductLike) -> tuple[str, str]:
    slug = product_slug(product)
    if "comments" in slug:
        prompt = "لینک عمومی محتوا و متن کامنت‌های دلخواه را ارسال کنید."
    elif "poll-votes" in slug:
        prompt = "لینک نظرسنجی و شماره یا متن گزینه موردنظر را ارسال کنید."
    elif "story-views" in slug:
        prompt = (
            "لینک استوری فعال یا نام کاربری پیج عمومی را ارسال کنید؛ استوری باید تا پایان "
            "انجام سفارش فعال بماند."
        )
    elif slug.startswith("instagram-followers-"):
        prompt = "نام کاربری یا لینک پیج عمومی اینستاگرام را ارسال کنید."
    elif slug.startswith("instagram-"):
        prompt = "لینک مستقیم پست یا ریلز عمومی اینستاگرام را ارسال کنید."
    elif slug.startswith("telegram-members-"):
        prompt = "لینک عمومی کانال یا لینک دعوت معتبر گروه تلگرام را ارسال کنید."
    elif slug.startswith("telegram-"):
        prompt = "لینک مستقیم پست عمومی تلگرام را ارسال کنید."
    elif slug.startswith("tiktok-followers-"):
        prompt = "نام کاربری یا لینک پروفایل عمومی TikTok را ارسال کنید."
    elif slug.startswith("tiktok-"):
        prompt = "لینک مستقیم ویدیوی عمومی TikTok را ارسال کنید."
    elif slug.startswith("youtube-subscribers-"):
        prompt = "لینک مستقیم کانال عمومی YouTube را ارسال کنید."
    elif slug.startswith("youtube-"):
        prompt = "لینک مستقیم ویدیوی عمومی YouTube یا Shorts را ارسال کنید."
    elif slug == "social-discord-members-1k":
        prompt = "لینک دعوت معتبر سرور Discord را ارسال کنید."
    elif slug.startswith("social-") and ("followers" in slug or "members" in slug):
        prompt = "نام کاربری یا لینک پروفایل عمومی را ارسال کنید."
    elif slug.startswith("social-"):
        prompt = "لینک مستقیم محتوای عمومی را ارسال کنید."
    else:
        prompt = _clean_prompt(product.input_prompt)

    if quantity_policy(product) is not None or slug.startswith(
        ("instagram-", "telegram-", "tiktok-", "youtube-", "social-")
    ):
        safety = "این سرویس روی لینک عمومی انجام می‌شود و هیچ اطلاعات ورودی لازم ندارد."
    else:
        safety = (
            "فقط ایمیل یا نام کاربری لازم را بفرستید؛ رمز عبور و کد ورود را داخل ربات "
            "ارسال نکنید. اگر فعال‌سازی نیاز به هماهنگی داشته باشد، پشتیبانی راهنمایی می‌کند."
        )
    return prompt, safety


def _base_quantity(slug: str) -> int | None:
    match = re.search(r"-(\d+)(k)?(?:-|$)", slug)
    if match is None:
        return None
    value = int(match.group(1))
    return value * 1_000 if match.group(2) else value


def _clean_prompt(prompt: str) -> str:
    text = prompt.strip()
    for marker in (
        " رمز عبور لازم نیست.",
        "؛ بدون دریافت رمز عبور.",
        "؛ بدون نیاز به رمز عبور.",
        (
            " برای امنیت، رمز عبور را داخل ربات نفرستید؛ هماهنگی فعال‌سازی از طریق "
            "پشتیبانی انجام می‌شود."
        ),
        " رمز عبور را داخل ربات نفرستید.",
    ):
        text = text.replace(marker, "")
    return text.strip()
