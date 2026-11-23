"""Build the mobile icon layers from the editable transparent foreground."""

from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'design' / '图标' / 'playing-cards-master.png'
ASSETS = ROOT / 'data' / 'android-icon'
HEADER = ROOT / 'data' / 'images' / 'icons' / '48x48' / 'pysol.png'


def transparent_mark():
    art = Image.open(MASTER).convert('RGBA')
    alpha = art.getchannel('A')
    visible = alpha.point(lambda value: 255 if value >= 32 else 0)
    bounds = visible.getbbox()
    if not bounds or alpha.getextrema() != (0, 255):
        raise ValueError('Expected a transparent foreground with visible playing cards')
    return art.crop(bounds)


def mark_on_square(mark, size, safe_radius):
    alpha = mark.getchannel('A')
    cx, cy = (length / 2 for length in mark.size)
    spread = max(hypot(x - cx, y - cy) for y in range(mark.height)
                 for x in range(mark.width) if alpha.getpixel((x, y)) >= 80)
    scale = safe_radius / spread
    fitted = mark.resize(tuple(round(length * scale) for length in mark.size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size))
    canvas.alpha_composite(fitted, tuple((size - length) // 2 for length in fitted.size))
    return canvas


def green_background(size):
    pixels = []
    for y in range(size):
        for x in range(size):
            light = max(0, 1 - hypot(x / size - .34, y / size - .28))
            pixels.append((round(10 + 12 * light), round(37 + 40 * light), round(31 + 26 * light)))
    image = Image.new('RGB', (size, size))
    image.putdata(pixels)
    return image


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    mark = transparent_mark()
    # Android reserves the outer 18 dp of each 108 dp adaptive icon layer.
    mark_on_square(mark, 432, safe_radius=129).save(ASSETS / 'foreground.png', optimize=True)
    green_background(432).save(ASSETS / 'background.png', optimize=True)

    size = 512
    preview = green_background(size).convert('RGBA')
    preview.alpha_composite(mark_on_square(mark, size, safe_radius=210))
    mask = Image.new('L', (size, size))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=114, fill=255)
    preview.putalpha(mask)
    preview.save(ASSETS / 'launcher.png', optimize=True)
    mark_on_square(mark, 320, safe_radius=140).save(ASSETS / 'presplash.png', optimize=True)
    mark_on_square(mark, 192, safe_radius=93).resize((48, 48), Image.Resampling.LANCZOS).save(HEADER, optimize=True)


if __name__ == '__main__':
    main()
