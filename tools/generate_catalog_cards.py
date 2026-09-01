from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from bot.database.catalog_seed import DEFAULT_CATEGORIES, DEFAULT_PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "products"
WIDTH, HEIGHT = 1200, 675
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CATEGORY_LABELS = {
    "خدمات تلگرام": "TELEGRAM SERVICES",
    "خدمات اینستاگرام": "INSTAGRAM SERVICES",
    "خدمات تیک‌تاک": "TIKTOK SERVICES",
    "خدمات یوتیوب": "YOUTUBE SERVICES",
    "اشتراک هوش مصنوعی": "AI & CREATIVE TOOLS",
    "سایر محصولات دیجیتال": "PREMIUM SUBSCRIPTIONS",
    "سایر شبکه‌های اجتماعی": "SOCIAL NETWORKS",
}


def rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def gradient(start: str, end: str) -> Image.Image:
    first, second = rgb(start), rgb(end)
    mask = Image.linear_gradient("L").rotate(-65, expand=True).resize((WIDTH, HEIGHT))
    return Image.composite(
        Image.new("RGB", (WIDTH, HEIGHT), second),
        Image.new("RGB", (WIDTH, HEIGHT), first),
        mask,
    )


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> ImageFont.FreeTypeFont:
    for size in range(78, 39, -2):
        font = ImageFont.truetype(FONT_BOLD, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return ImageFont.truetype(FONT_BOLD, 40)


def make_card(product_slug: str, title: str, category: str, colors: tuple[str, str]) -> None:
    image = gradient(*colors).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Soft decorative circles keep every card distinct while preserving readability.
    for x, y, radius, alpha in ((1020, 80, 250, 38), (110, 610, 220, 32), (1040, 620, 135, 28)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 255, 255, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(4))
    image = Image.alpha_composite(image, overlay)
    image = ImageEnhance.Contrast(image.convert("RGB")).enhance(1.06).convert("RGBA")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((58, 48, 500, 112), radius=26, fill=(15, 23, 42, 230))
    label_font = ImageFont.truetype(FONT_BOLD, 25)
    draw.text((86, 66), CATEGORY_LABELS[category], font=label_font, fill="white")

    lines = title.split("\n")
    y = 214
    for line in lines:
        font = fit_font(draw, line, 900)
        draw.text((68, y), line, font=font, fill="white", stroke_width=1, stroke_fill=(0, 0, 0, 50))
        y += font.size + 20

    body_font = ImageFont.truetype(FONT_REGULAR, 27)
    draw.text(
        (70, 540),
        "FAST DELIVERY  •  SECURE ORDER  •  SUPPORT",
        font=body_font,
        fill=(255, 255, 255, 225),
    )
    draw.rounded_rectangle((70, 598, 1130, 603), radius=2, fill=(255, 255, 255, 85))
    footer_font = ImageFont.truetype(FONT_BOLD, 24)
    draw.text((70, 621), "PERSIAN SHOP", font=footer_font, fill="white")
    footer = "DIGITAL SERVICES"
    footer_width = draw.textbbox((0, 0), footer, font=footer_font)[2]
    draw.text((1130 - footer_width, 621), footer, font=footer_font, fill=(255, 255, 255, 205))

    image.convert("RGB").save(
        OUTPUT / f"{product_slug}.jpg",
        format="JPEG",
        quality=88,
        optimize=True,
        progressive=True,
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    colors = {category.name: category.card_color for category in DEFAULT_CATEGORIES}
    for product in DEFAULT_PRODUCTS:
        make_card(
            product.image_slug,
            product.card_title,
            product.category,
            colors[product.category],
        )
    print(f"Generated {len(DEFAULT_PRODUCTS)} product cards in {OUTPUT}")


if __name__ == "__main__":
    main()
