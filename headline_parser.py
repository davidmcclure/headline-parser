

import re
import spacy
import regex

from spacy.tokens import Token, Doc
from boltons.iterutils import pairwise
from functools import reduce
from cached_property import cached_property


CURLY_STRAIGHT = (('“', '"'), ('”', '"'), ('‘', "'"), ('’', "'"))

def standardize_quotes(text):
    """Curly -> straight.
    """
    for c, s in CURLY_STRAIGHT:
        text = text.replace(c, s)

    text = text.replace("''", '"')

    return text


# http://jkorpela.fi/dashes.html
HYPHENS = {u'\u002D', u'\u2010', u'\u2011', u'\u2212', u'\uFE63'}

def standardize_hyphens(text):
    """Hyphen variants -> "-".
    """
    for h in HYPHENS:
        text = text.replace(h, '-')

    # Drop infix hyphens.
    text = re.sub('([^\s])-([^\s])', r'\1 \2', text)

    return text


def scrub_twitter_chars(text):
    return re.sub('[@#]', '', text)


STANDARDIZERS = (
    standardize_quotes,
    standardize_hyphens,
    scrub_twitter_chars,
)

def standardize_text(text):
    return reduce(lambda t, func: func(t), STANDARDIZERS, text)


BREAK_CHAR_PATTERN = '[^a-z0-9\.,;\'"\?!\$\s]'
ALPHA_BREAK_TOKENS = {'via'}

def is_break_token(token):
    """Does the token constitute a "sentence" break?
    """
    text = token.text.lower()

    has_break_char = bool(re.search(BREAK_CHAR_PATTERN, text))
    is_alpha_break_token = text in ALPHA_BREAK_TOKENS

    return has_break_char or is_alpha_break_token


def clean_clf_text(token):
    """Drop everything but letters, numbers, and currency ($.,)
    """
    text = re.sub('[^a-z0-9\$\.,]', '', token.text.lower())

    # Drop periods, unless in number.
    if not re.match('[0-9\.,]', text):
        text = re.sub('[\.,]', '', text)

    return text


def longest_unbroken_span(doc):
    """Find the longest span of tokens without a break token.
    """
    break_idxs = [-1, *[t.i for t in doc if t._.is_break_token], len(doc)]

    pairs = sorted(pairwise(break_idxs), key=lambda p: p[1]-p[0])
    i1, i2 = pairs[-1]

    return doc[i1+1:i2]


def clf_tokens(doc):
    """Get filtered tokens for classifier.
    """
    return [
        t._.text_clf for t in doc._.longest_unbroken_span
        if len(t._.text_clf)
    ]


Token.set_extension('is_break_token', getter=is_break_token)
Token.set_extension('text_clf', getter=clean_clf_text)

Doc.set_extension('longest_unbroken_span', getter=longest_unbroken_span)
Doc.set_extension('clf_tokens', getter=clf_tokens)

nlp = spacy.load('en', disable=['ner', 'parser', 'tagger'])


class Headline:

    def __init__(self, text):
        self.text = text

    @cached_property
    def standardized_text(self):
        return standardize_text(self.text)

    @cached_property
    def doc(self):
        return nlp(self.standardized_text)

    @cached_property
    def tokens(self):
        return [t.text for t in self.doc]

    @cached_property
    def clf_tokens(self):
        return self.doc._.clf_tokens