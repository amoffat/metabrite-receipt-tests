from os.path import join, abspath, dirname, expanduser, basename
import sys

from PIL import ImageFont, ImageDraw, Image
import os
import random
from functools import partial, lru_cache
from collections import defaultdict as dd
import glyphs


#THIS_DIR = expanduser("~/workspace/acolyte")
THIS_DIR = dirname(abspath(__file__))
FONT_DIR = join(THIS_DIR, "fonts/ttfs")
BB_PADDING = 0.45

FONT_WHITELIST = {
    "BPtypewrite.otf",
    "BPtypewriteDamaged.otf",
    "BebasNeue.otf",
    "Cella.ttf",
    "Code New Roman b.woff",
    "Code New Roman.otf",
    "Code New Roman.woff",
    "Courier Prime Bold.ttf",
    "Courier Prime Sans Bold.ttf",
    "Courier Prime Sans.ttf",
    "Courier Prime.ttf",
    "DejaVuSansMono-Bold.ttf",
    "DejaVuSansMono.ttf",
    "Erika Ormig.ttf",
    "Instruction Bold.otf",
    "Instruction.otf",
    "Kingthings Trypewriter 2.ttf",
    "LiberationMono-Bold.ttf",
    "LiberationMono-Regular.ttf",
    "Momоt___.ttf"
    "Monoid-a0-a1-a3-al-ad-aa.ttf",
    "MonospaceTypewriter.ttf",
    "PTM55F.ttf",
    "PTM75F.ttf",
    "Reitam Regular.otf",
    "Ticketing.otf",
    "Tox Typewriter.ttf",
    "Ubuntu-B.ttf",
    "Ubuntu-C.ttf",
    "Ubuntu-L.ttf",
    "Ubuntu-M.ttf",
    "Ubuntu-R.ttf",
    "UbuntuMono-B.ttf",
    "UbuntuMono-R.ttf",
    "big_noodle_titling.ttf",
    "fake receipt.ttf",
    "gabriele-d.ttf",
    "kenyan coffee rg.ttf",
    "lmmono10-regular.otf",
    "lmmono12-regular.otf",
    "lmmono8-regular.otf",
    "lmmono9-regular.otf",
    "lmmonocaps10-regular.otf",
    "lmmonolt10-bold.otf",
    "lmmonolt10-regular.otf",
    "lmmonoltcond10-regular.otf",
    "lmmonoprop10-regular.otf",
    "lmmonoproplt10-bold.otf",
    "lmmonoproplt10-regular.otf",
    "uwch.ttf",

    # THERMAL FONTS
    "DotLatin_D01b_ext.ttf",
    "DotLatin_D21b.ttf",
}

# fonts that only have uppercase letters
ONLY_UPPERCASE = {
    "fake receipt.ttf",
    "big_noodle_titling.ttf",
    "Instruction Bold.otf",
    "Reitam Regular.otf",
    "lmmonocaps10-regular.otf",
    "BebasNeue.otf",
    "Instruction.otf",
}
assert ONLY_UPPERCASE.issubset(FONT_WHITELIST)


def pick_font(d):
    name = None
    while name not in FONT_WHITELIST:
        name = random.choice(os.listdir(d))
    font_file = join(d, name)
    return font_file

def gen_fonts(d):
    for name in os.listdir(d):
        font_file = join(d, name)
        if name in FONT_WHITELIST:
            yield font_file

def load_font(font_file, size):
    font = ImageFont.truetype(font_file, size)
    return font

def make_tight_bounder(chars):
    """ makes a function that can take a font and produce a mappign of all chars
    to its tight bounding box.  tight bounding box is per-pixel shrink wrapped
    bounding box around the actual character content """
    def fn(font):
        mapping = {}

        for letter in chars:
            w, h = font.getsize(letter)
            im = Image.new("RGB", (w, h), (0,0,0))
            draw = ImageDraw.Draw(im)

            draw.text((0, 0), letter, font=font, fill=(255,255,255))
            box = im.getbbox()

            # empty content, like space, will return None for bounding box
            if not box:
                box = (0, 0, w, h)

            mapping[letter] = box

        return mapping
    return fn


def gen_char():
    return glyphs.get_glyph()

def gen_word():
    chars = []

    # ensure the first char is not a space
    char = " "
    while char == " ":
        char = gen_char()
    chars.append(char)

    while char != " ":
        char = gen_char()
        chars.append(char)

    return "".join(chars)


def gen_text(sizer, max_width):
    line = []
    cur_len = 0

    while True:
        word = gen_word()
        cur_len, _ = sizer("".join(line + [word]))
        if cur_len >= max_width:
            break
        line.append(word)

    # remove the trailing space from the last word
    line[-1] = line[-1].strip()

    return "".join(line)


def create_text_sizer(bb_mapping, kerning):
    def fn(text):
        size = [0, 0]
        if text:
            for i, letter in enumerate(text):
                x1, y1, x2, y2 = bb_mapping[letter]
                h = y2 - y1

                real_width = x2 
                last_letter = i == len(text) - 1
                if not last_letter:
                    real_width = x2 * kerning

                size[0] += real_width
                size[1] = max(size[1], h)
        return size 
    return fn


def draw_bbs(cursor, draw, bbs):
    for ul, br in bbs:
        draw.rectangle([(ul[0], ul[1]), br[0], br[1]], outline=(255, 0, 0)) 


def demo_fonts(font_dir, im_size, font_size):
    im = Image.new("RGB", im_size, (255, 255, 255))
    draw = ImageDraw.Draw(im)

    all_glyphs = glyphs.get_print_glyphs()

    cursor = [0, 0]
    for font_file in gen_fonts(font_dir):
        font = load_font(font_file, font_size)
        name = basename(font_file)

        bounder = make_tight_bounder(glyphs.get_print_glyphs())
        bb_mapping = bounder(font)

        sizer = create_text_sizer(bb_mapping, 0)
        _, letter_height = sizer("I")

        draw.text(cursor, name + " " + all_glyphs, font=font, fill=(0,0,0))
        cursor[1] += 40

    return im


def gen_receipt(font_dir, im_size, font_size, im_padding,
        line_spacing, kerning):
    """
    font_dir is the directory to pick a font from
    im_size is a (width, height) tuple
    font_size is the font size
    im_padding is a fraction from 0-1 repesenting what percentage of the image
    width should be padding
    """

    font_file = pick_font(font_dir)
    font = load_font(font_file, font_size)

    bounder = make_tight_bounder(glyphs.get_print_glyphs())
    width, height = im_size
    bb_mapping = bounder(font)

    image = Image.new("RGB", im_size, (255, 255, 255))
    draw = ImageDraw.Draw(image)


    sizer = create_text_sizer(bb_mapping, kerning)
    max_letter_height = 0
    for glyph in glyphs.get_print_glyphs():
        max_letter_height = max(sizer(glyph)[1], max_letter_height)

    im_padding *= im_size[0]
    cursor = (im_padding, im_padding)
    all_bbs = dd(list)
    left_start = cursor[0]

    while True:
        text = gen_text(sizer, im_size[0]-(2*im_padding))

        if cursor[1] + max_letter_height > (im_size[1]-(2*im_padding)):
            break

        for letter in text:
            x1, y1, x2, y2 = bb_mapping[letter]
            ul = (cursor[0] + x1, cursor[1] + y1)
            br = (cursor[0] + x2, cursor[1] + y2)
            bb = (ul, br)

            # this isn't x2 - x2 because the true with has to include the
            # difference between x2 and the edge of the glyph, which starts to
            # the left of x1
            w = x2

            all_bbs[letter].append(bb)

            draw.text(cursor, letter, font=font, fill=(0,0,0))
            cursor = (cursor[0] + (x2 * kerning), cursor[1])

            #draw_bbs(cursor, draw, [bb])

        cursor = (left_start, cursor[1] + max_letter_height * line_spacing)

    # normalize our bounding boxes by image size
    for letter in list(all_bbs.keys()):
        bbs = all_bbs[letter]
        bbs = [((l/width, 1.0-u/height), (r/width, 1.0-b/height)) for ((l, u), (r, b))
                in bbs]
        all_bbs[letter] = bbs

    return image, all_bbs, basename(font_file)


def main():
    #bounder = make_tight_bounder(glyphs.get_print_glyphs())
    #font_file = pick_font(FONT_DIR)
    #font = load_font(font_file, 20)
    #mapping = bounder(font)
    #return

    im = demo_fonts(FONT_DIR, (2200, 2200), 25)
    im.show()
    return

    def random_float(start, end):
        return (random.random() * (end - start)) + start

    line_spacing = random_float(0.9, 1.1)
    kerning = random_float(0.95, 1.05)
    #kerning = 1.0
    im, bbs, font_used = gen_receipt(FONT_DIR, (1440, 2584), 45, 0.04,
            line_spacing, kerning)
    im.save("/tmp/wtf.png")
    im.show()


if __name__ == "__main__":
    #while True:
    main()
