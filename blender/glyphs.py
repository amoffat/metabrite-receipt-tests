import random
from string import ascii_lowercase, ascii_uppercase, digits
import text_gen

_punc = "!@#$%*&()-+='\",?/."
_normal = ascii_lowercase + ascii_uppercase + digits
_char_map = dict(zip(ascii_lowercase, ascii_uppercase))

# in english
_AVG_WORD_LENGTH = 5.1

def resolve_glyph(g, font):
    """ resolve a glyph to its true form.  in practice, this means mapping
    lowercase characters to uppercase """
    if font in text_gen.ONLY_UPPERCASE:
        g = _char_map.get(g, g)
    return g

def get_orient_glyphs():
    g = ascii_uppercase + ascii_lowercase + digits + _punc
    return g

def get_glyphs():
    """ get all the glyphs used for classification """
    return get_print_glyphs()
    #return digits

def get_print_glyphs():
    """ get all the glyphs used for printing text on a receipt """
    g = ascii_uppercase + ascii_lowercase + digits + _punc + " "
    #g = digits + " "
    return g

def get_glyph():
    pick_space = random.random() <= (1/(_AVG_WORD_LENGTH-1))
    if pick_space:
        glyph = " "
    else:
        #glyph = random.choice(digits)
        pick_normal = random.random() < 0.8
        if pick_normal:
            glyph = random.choice(_normal)
        else:
            glyph = random.choice(_punc)
    return glyph

def map_dist(dist):
    glyphs = get_glyphs()
    mapping = {glyphs[i]: el for i, el in enumerate(dist) if el}
    return mapping
