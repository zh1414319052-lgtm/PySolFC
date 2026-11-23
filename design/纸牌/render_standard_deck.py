"""Render the Android Standard deck from its editable artwork and type settings."""

import argparse
import io
import random
import re
import tarfile
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL_DECK = 'data/cardset-standard-png/'
WIDTH, HEIGHT = 144, 244
SIZE = WIDTH, HEIGHT
SCALE = 2
INK = (27, 24, 17, 255)
RED = (163, 32, 25, 255)
SUITS = dict(c='♣', s='♠', h='♥', d='♦')
RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')
PIPS = {
    1: [(72, 122)],
    2: [(72, y) for y in (86, 158)],
    3: [(72, y) for y in (85, 125, 165)],
    4: [(x, y) for y in (91, 165) for x in (44, 100)],
    5: [(x, y) for y in (91, 165) for x in (44, 100)] + [(72, 128)],
    6: [(x, y) for y in (91, 128, 165) for x in (44, 100)],
    7: [(x, y) for y in (91, 128, 165) for x in (44, 100)] + [(72, 109)],
    8: [(x, y) for y in (91, 128, 165) for x in (44, 100)] + [(72, 109), (72, 146)],
    9: [(x, y) for y in (91, 117, 143, 169) for x in (44, 100)] + [(72, 130)],
    10: [(x, y) for y in (91, 117, 143, 169) for x in (44, 100)] + [(72, 104), (72, 156)],
}


def surface():
    return Image.new('RGBA', (WIDTH * SCALE, HEIGHT * SCALE))


def xy(*values):
    return tuple(round(value * SCALE) for value in values)


@lru_cache(maxsize=None)
def font(size, suit=False):
    name = 'DejaVuSans.ttf' if suit else 'DejaVuSerif-Bold.ttf'
    return ImageFont.truetype(str(HERE / name), size * SCALE)


def letter(image, text, size, color, left=None, right=None, top=None, center=None, suit=False):
    face = font(size, suit)
    x0, y0, x1, y1 = face.getbbox(text)
    if center is None:
        x = left * SCALE - x0 if left is not None else right * SCALE - x1
        y = top * SCALE - y0
    else:
        x = center[0] * SCALE - (x0 + x1) / 2
        y = center[1] * SCALE - (y0 + y1) / 2
    ImageDraw.Draw(image).text((round(x), round(y)), text, fill=color, font=face)


def paper():
    canvas = surface()
    draw = ImageDraw.Draw(canvas)
    # Stack contact shadow is baked into the transparent rim of each sprite.
    draw.rounded_rectangle(xy(1.5, 3, 142.5, 243), radius=17 * SCALE, fill=(9, 17, 10, 78))
    draw.rounded_rectangle(xy(2, 1, 142, 241), radius=16 * SCALE, fill=(208, 191, 152, 255))
    mask = Image.new('L', canvas.size)
    ImageDraw.Draw(mask).rounded_rectangle(xy(3, 2, 141, 239), radius=15 * SCALE, fill=255)
    rng = random.Random(30)
    cream = Image.new('RGB', canvas.size)
    pixels = []
    for y in range(HEIGHT * SCALE):
        for x in range(WIDTH * SCALE):
            tint = (x / canvas.width + y / canvas.height) * 2
            shade = round(rng.gauss(0, 0.66) - tint)
            pixels.append((249 + shade, 242 + shade, 224 + shade))
    cream.putdata(pixels)
    canvas.paste(cream, (0, 0), mask)
    return canvas


def load_courts():
    atlas = Image.open(HERE / 'court-atlas.png').convert('RGB')
    portraits = {}
    for row, rank in enumerate('JQK'):
        for column, suit in enumerate(SUITS):
            bounds = (column * atlas.width // 4, row * atlas.height // 3,
                      (column + 1) * atlas.width // 4, (row + 1) * atlas.height // 3)
            portrait = atlas.crop(bounds)
            background = Image.new('RGB', portrait.size, portrait.getpixel((2, 2)))
            difference = ImageChops.difference(portrait, background).convert('L')
            mask = difference.point(lambda value: 255 if value > 26 else 0)
            ImageDraw.floodfill(mask, (0, 0), 128)
            alpha = mask.point(lambda value: 0 if value == 128 else 255)
            portrait.putalpha(alpha)
            portraits[rank, suit] = portrait.crop(alpha.getbbox())
    return portraits


def front(base, rank, suit, portraits):
    image = base.copy()
    color = RED if suit in 'hd' else INK
    mark = SUITS[suit]
    if rank in 'JQK':
        portrait = ImageOps.contain(portraits[rank, suit], xy(122, 153), Image.Resampling.LANCZOS)
        image.alpha_composite(portrait, ((image.width - portrait.width) // 2, 52 * SCALE))
    else:
        number = 1 if rank == 'A' else int(rank)
        size = 71 if number == 1 else (49 if number < 4 else 34)
        for point in PIPS[number]:
            letter(image, mark, size, color, center=point, suit=True)
    letter(image, rank, 45, color, left=14, top=11)
    letter(image, mark, 33, color, left=13, top=58, suit=True)
    letter(image, rank, 45, color, right=131, top=198)
    return image


def card_back(base, art):
    image = base.copy()
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).rounded_rectangle(xy(8, 8, 136, 234), radius=11 * SCALE, fill=255)
    art = ImageOps.fit(art, xy(129, 227), Image.Resampling.LANCZOS)
    layer = surface()
    layer.paste(art, xy(8, 8))
    image.paste(layer, (0, 0), mask)
    return image


def write_sprite(image, path):
    image.resize(SIZE, Image.Resampling.LANCZOS).save(path, optimize=True)


def render(upstream, destination):
    destination.mkdir(parents=True, exist_ok=True)
    base = paper()
    portraits = load_courts()
    for suit in SUITS:
        for number, rank in enumerate(RANKS, 1):
            write_sprite(front(base, rank, suit, portraits), destination / f'{number:02}{suit}.png')
    for number, color in enumerate((INK, RED), 1):
        joker = base.copy()
        letter(joker, '★', 87, color, center=(72, 113), suit=True)
        letter(joker, 'JOKER', 26, color, center=(72, 164))
        letter(joker, 'J', 45, color, left=14, top=11)
        letter(joker, 'J', 45, color, right=131, top=198)
        write_sprite(joker, destination / f'{number:02}z.png')

    art = Image.open(HERE / 'back-engraving.png').convert('RGB')
    write_sprite(card_back(base, art), destination / 'back111.png')
    highlight = surface()
    ImageDraw.Draw(highlight).rounded_rectangle(
        xy(3, 2, 141, 239), radius=15 * SCALE, outline=(107, 217, 120, 245), width=5 * SCALE,
    )
    write_sprite(highlight, destination / 'shade.png')

    with ZipFile(upstream) as apk:
        private = apk.read('assets/private.tar')
    with tarfile.open(fileobj=io.BytesIO(private)) as archive:
        for entry in archive:
            if not entry.isfile() or not entry.name.startswith(ORIGINAL_DECK):
                continue
            name = entry.name.removeprefix(ORIGINAL_DECK)
            with archive.extractfile(entry) as stream:
                if name == 'config.txt':
                    lines = stream.read().decode('ascii').splitlines()
                    lines[2] = f'{WIDTH} {HEIGHT} 8'
                    lines[3] = '28 90 10 14'
                    (destination / name).write_text('\n'.join(lines) + '\n', encoding='ascii')
                elif re.fullmatch(r'back(?!111)\d+\.png', name):
                    other_art = Image.open(stream).convert('RGB')
                    write_sprite(card_back(base, other_art), destination / name)
                elif re.fullmatch(r'(?:bottom\d+|l\d+)(?:-n)?\.png', name):
                    sprite = Image.open(stream).convert('RGBA').resize(SIZE, Image.Resampling.LANCZOS)
                    sprite.save(destination / name, optimize=True)
                elif re.fullmatch(r'x?shadow\d+\.png', name):
                    sprite = Image.open(stream).convert('RGBA')
                    size = round(sprite.width * WIDTH / 71), round(sprite.height * HEIGHT / 96)
                    sprite.resize(size, Image.Resampling.LANCZOS).save(destination / name, optimize=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / ORIGINAL_DECK)
    args = parser.parse_args()
    render(args.upstream, args.output)
