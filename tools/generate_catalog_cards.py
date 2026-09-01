from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.database.catalog_seed import DEFAULT_PRODUCTS  # noqa: E402
from bot.services.product_presentation import quantity_policy_for_slug  # noqa: E402

OUTPUT = ROOT / "assets" / "products"
ICON_ROOT = ROOT / "assets" / "brand-icons"
BACKGROUND = ROOT / "assets" / "poster-templates" / "premium-tech-background.jpg"
WIDTH, HEIGHT = 1200, 675
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BRANDS: tuple[tuple[str, str, str | None, tuple[str, str]], ...] = (
    ("instagram-", "INSTAGRAM", "instagram", ("#FF2D75", "#7B2CFF")),
    ("telegram-", "TELEGRAM", "telegram", ("#2AABEE", "#1264D9")),
    ("tiktok-", "TIKTOK", "tiktok", ("#25F4EE", "#FE2C55")),
    ("youtube-", "YOUTUBE", "youtube", ("#FF0033", "#9A001D")),
    ("ai-chatgpt", "CHATGPT", None, ("#10A37F", "#065F55")),
    ("ai-claude", "CLAUDE", "anthropic", ("#D97757", "#7C2D12")),
    ("ai-gemini", "GEMINI", "googlegemini", ("#4E82EE", "#8B5CF6")),
    ("ai-perplexity", "PERPLEXITY", "perplexity", ("#22B8B0", "#0F766E")),
    ("ai-midjourney", "MIDJOURNEY", None, ("#A5B4FC", "#4338CA")),
    ("ai-suno", "SUNO", "suno", ("#A3E635", "#15803D")),
    ("ai-elevenlabs", "ELEVENLABS", "elevenlabs", ("#F8FAFC", "#64748B")),
    ("ai-cursor", "CURSOR", "cursor", ("#E2E8F0", "#475569")),
    ("ai-google-flow", "GOOGLE FLOW", "google", ("#4285F4", "#34A853")),
    ("ai-canva", "CANVA", None, ("#00C4CC", "#7D2AE8")),
    ("ai-capcut", "CAPCUT", None, ("#F8FAFC", "#64748B")),
    ("digital-telegram", "TELEGRAM", "telegram", ("#2AABEE", "#1264D9")),
    ("digital-spotify", "SPOTIFY", "spotify", ("#1ED760", "#087F3E")),
    ("digital-youtube", "YOUTUBE", "youtube", ("#FF0033", "#9A001D")),
    ("digital-apple", "APPLE MUSIC", "applemusic", ("#FA2D48", "#A11245")),
    ("digital-soundcloud", "SOUNDCLOUD", "soundcloud", ("#FF5500", "#A12A00")),
    ("digital-discord", "DISCORD", "discord", ("#5865F2", "#312E81")),
    ("digital-google", "GOOGLE ONE", "google", ("#4285F4", "#34A853")),
    ("digital-microsoft", "MICROSOFT 365", None, ("#F25022", "#00A4EF")),
    ("social-threads", "THREADS", "threads", ("#F8FAFC", "#52525B")),
    ("social-x", "X", "x", ("#F8FAFC", "#475569")),
    ("social-discord", "DISCORD", "discord", ("#5865F2", "#312E81")),
    ("social-twitch", "TWITCH", "twitch", ("#9146FF", "#5B21B6")),
    ("social-linkedin", "LINKEDIN", None, ("#0A66C2", "#164E8A")),
)


def rgb(value: str) -> tuple[int, int, int]:
    clean = value.removeprefix("#")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))


def brand_for(slug: str) -> tuple[str, str | None, tuple[str, str]]:
    for prefix, name, icon, colors in BRANDS:
        if slug.startswith(prefix):
            return name, icon, colors
    return "PERSIAN SHOP", None, ("#8B5CF6", "#2563EB")


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> ImageFont.FreeTypeFont:
    for size in range(70, 33, -2):
        font = ImageFont.truetype(FONT_BOLD, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return ImageFont.truetype(FONT_BOLD, 34)


def poster_title(title: str, slug: str) -> list[str]:
    lines = title.split("\n")
    if quantity_policy_for_slug(slug):
        lines[0] = re.sub(r"^(?:\d+[KM]?|\d+)\s+", "", lines[0]).strip()
    return [line for line in lines if line]


def product_badge(slug: str) -> str:
    labels = (
        ("premium", "PREMIUM QUALITY"),
        ("iranian", "IRANIAN AUDIENCE"),
        ("economy", "ECONOMY"),
        ("watchtime", "WATCH TIME"),
        ("story", "STORY"),
        ("shorts", "SHORTS"),
        ("comments", "CUSTOM COMMENTS"),
        ("reactions", "REACTIONS"),
        ("saves", "SAVES"),
        ("shares", "SHARES"),
        ("views", "VIEWS"),
        ("followers", "FOLLOWERS"),
        ("members", "MEMBERS"),
        ("subscribers", "SUBSCRIBERS"),
    )
    return next((label for token, label in labels if token in slug), "DIGITAL SERVICE")


def make_brand_background(slug: str, colors: tuple[str, str]) -> Image.Image:
    base = Image.open(BACKGROUND).convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    accent_a, accent_b = rgb(colors[0]), rgb(colors[1])
    seed = hashlib.sha256(slug.encode()).digest()
    mask = Image.linear_gradient("L").rotate(seed[0] % 80 - 40, expand=True).resize((WIDTH, HEIGHT))
    tint = Image.composite(
        Image.new("RGB", (WIDTH, HEIGHT), accent_b),
        Image.new("RGB", (WIDTH, HEIGHT), accent_a),
        mask,
    )
    tinted = Image.blend(base, ImageChops.screen(base, tint), 0.34)
    return ImageEnhance.Contrast(tinted).enhance(1.12).convert("RGBA")


def render_logo(icon_slug: str | None, brand: str, directory: Path) -> Image.Image:
    if icon_slug and (ICON_ROOT / f"{icon_slug}.svg").exists():
        target = directory / f"{icon_slug}.png"
        subprocess.run(
            [
                "inkscape",
                str(ICON_ROOT / f"{icon_slug}.svg"),
                "--export-background-opacity=0",
                "--export-width=260",
                "--export-height=260",
                f"--export-filename={target}",
            ],
            check=True,
            capture_output=True,
        )
        source = Image.open(target).convert("RGBA")
        white = Image.new("RGBA", source.size, "white")
        white.putalpha(source.getchannel("A"))
        return white

    image = Image.new("RGBA", (260, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    initials = {
        "CHATGPT": "GPT",
        "MIDJOURNEY": "MJ",
        "CANVA": "C",
        "CAPCUT": "CC",
        "MICROSOFT 365": "M365",
        "LINKEDIN": "in",
    }.get(brand, brand[:3])
    font = fit_font(draw, initials, 220)
    bounds = draw.textbbox((0, 0), initials, font=font)
    draw.text(
        ((260 - (bounds[2] - bounds[0])) / 2, (260 - (bounds[3] - bounds[1])) / 2 - 8),
        initials,
        font=font,
        fill="white",
    )
    return image


def make_card(product, directory: Path) -> None:
    slug = product.image_slug
    brand, icon_slug, colors = brand_for(slug)
    image = make_brand_background(slug, colors)
    draw = ImageDraw.Draw(image, "RGBA")
    accent = rgb(colors[0])

    draw.rounded_rectangle((48, 42, 330, 102), radius=24, fill=(5, 12, 28, 205))
    draw.ellipse((70, 62, 88, 80), fill=(*accent, 255))
    draw.text(
        (105, 59),
        "PERSIAN SHOP",
        font=ImageFont.truetype(FONT_BOLD, 24),
        fill="white",
    )

    badge = product_badge(slug)
    badge_font = ImageFont.truetype(FONT_BOLD, 21)
    badge_width = draw.textbbox((0, 0), badge, font=badge_font)[2] + 54
    draw.rounded_rectangle((52, 142, 52 + badge_width, 194), radius=22, fill=(*accent, 210))
    draw.text((79, 156), badge, font=badge_font, fill="white")

    y = 238
    for line in poster_title(product.card_title, slug)[:3]:
        font = fit_font(draw, line, 720)
        draw.text(
            (54, y),
            line,
            font=font,
            fill="white",
            stroke_width=2,
            stroke_fill=(0, 0, 0, 90),
        )
        y += font.size + 18

    policy_label = "CHOOSE YOUR QUANTITY" if quantity_policy_for_slug(slug) else "FIXED PLAN"
    draw.text(
        (58, 510),
        policy_label,
        font=ImageFont.truetype(FONT_BOLD, 23),
        fill=(*accent, 255),
    )
    draw.text(
        (58, 552),
        "SECURE CHECKOUT  •  ORDER TRACKING  •  SUPPORT",
        font=ImageFont.truetype(FONT_REGULAR, 22),
        fill=(235, 242, 255, 225),
    )
    draw.rounded_rectangle((58, 610, 1142, 614), radius=2, fill=(*accent, 210))
    draw.text(
        (58, 628),
        brand,
        font=ImageFont.truetype(FONT_BOLD, 21),
        fill="white",
    )

    draw.rounded_rectangle(
        (850, 156, 1135, 478),
        radius=52,
        fill=(7, 14, 31, 145),
        outline=(*accent, 190),
        width=3,
    )
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((865, 175, 1120, 430), fill=(*accent, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    image = Image.alpha_composite(image, glow)
    logo = render_logo(icon_slug, brand, directory).resize((210, 210), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (888, 205))

    image.convert("RGB").save(
        OUTPUT / f"{slug}.jpg",
        format="JPEG",
        quality=92,
        optimize=True,
        progressive=True,
    )


def main() -> None:
    if not BACKGROUND.exists():
        raise SystemExit(f"Missing poster background: {BACKGROUND}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="persian-shop-posters-") as temp:
        directory = Path(temp)
        for product in DEFAULT_PRODUCTS:
            make_card(product, directory)
    print(f"Generated {len(DEFAULT_PRODUCTS)} premium product posters in {OUTPUT}")


if __name__ == "__main__":
    main()
