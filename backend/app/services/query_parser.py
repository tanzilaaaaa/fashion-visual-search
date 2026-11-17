"""Detect category and colour intent in a free-text query.

The detected attributes feed the ranking's attribute signal
(``final = α·cosine + β·attribute_match``). CLIP does the heavy lifting; this
parser only lifts exact-category / exact-colour matches above visually similar
but wrong-category items (PRD §9.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DRESSES = {"short_sleeve_dress", "long_sleeve_dress", "vest_dress", "sling_dress"}
OUTERWEAR = {"short_sleeve_outwear", "long_sleeve_outwear"}

# Ordered most-specific first; a matched span is consumed so "vest dress"
# doesn't also count as "vest".
CATEGORY_PATTERNS: list[tuple[str, set[str]]] = [
    (r"short[\s-]?sleeve(?:d)? (?:dress|gown)", {"short_sleeve_dress"}),
    (r"long[\s-]?sleeve(?:d)? (?:dress|gown)", {"long_sleeve_dress"}),
    (r"(?:vest|sleeveless|tank) dress", {"vest_dress", "sling_dress"}),
    (r"(?:sling|slip|strappy|spaghetti[\s-]?strap|cami) dress", {"sling_dress"}),
    (r"short[\s-]?sleeve(?:d)? (?:outwear|outerwear|jacket|coat)", {"short_sleeve_outwear"}),
    (r"long[\s-]?sleeve(?:d)? (?:outwear|outerwear|jacket|coat)", {"long_sleeve_outwear"}),
    (r"short[\s-]?sleeve(?:d)? (?:top|shirt|tee|blouse)", {"short_sleeve_top"}),
    (r"long[\s-]?sleeve(?:d)? (?:top|shirt|tee|blouse)", {"long_sleeve_top"}),
    (r"t[\s-]?shirts?|tees?|polo(?: shirt)?s?", {"short_sleeve_top"}),
    (r"sweaters?|jumpers?|hoodies?|sweatshirts?|pullovers?|turtlenecks?|knitwear", {"long_sleeve_top"}),
    (r"tank(?: tops?)?s?|vests?|sleeveless tops?", {"vest"}),
    (r"camis?|camisoles?|slings?|spaghetti[\s-]?straps?|halter(?: tops?)?", {"sling"}),
    (r"shirts?|blouses?|tops?", {"short_sleeve_top", "long_sleeve_top"}),
    (r"jackets?|coats?|blazers?|parkas?|cardigans?|trench(?:coat)?s?|outerwear|outwear", OUTERWEAR),
    (r"shorts|hot pants|bermudas?", {"shorts"}),
    (r"trousers?|pants|jeans|chinos?|leggings?|joggers?|slacks", {"trousers"}),
    (r"skirts?|mini ?skirts?|midi ?skirts?", {"skirt"}),
    (r"dress(?:es)?|gowns?|frocks?|sundress(?:es)?", DRESSES),
]

COLOUR_WORDS: dict[str, str] = {
    "black": "black", "white": "white", "ivory": "white", "cream": "beige",
    "grey": "grey", "gray": "grey", "charcoal": "grey", "silver": "grey",
    "red": "red", "maroon": "red", "burgundy": "red", "crimson": "red",
    "pink": "pink", "rose": "pink", "magenta": "pink", "fuchsia": "pink",
    "orange": "orange", "coral": "orange", "rust": "orange",
    "yellow": "yellow", "mustard": "yellow", "gold": "yellow",
    "green": "green", "olive": "green", "khaki": "beige", "mint": "green", "emerald": "green",
    "blue": "blue", "denim": "blue", "teal": "blue", "turquoise": "blue", "sky blue": "blue",
    "navy": "navy", "navy blue": "navy",
    "purple": "purple", "violet": "purple", "lilac": "purple", "lavender": "purple",
    "brown": "brown", "tan": "beige", "camel": "beige", "chocolate": "brown",
    "beige": "beige", "nude": "beige",
}
_COLOUR_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, COLOUR_WORDS), key=len, reverse=True)) + r")\b"
)


@dataclass
class ParsedQuery:
    categories: set[str] = field(default_factory=set)
    colours: set[str] = field(default_factory=set)

    @property
    def has_attributes(self) -> bool:
        return bool(self.categories or self.colours)

    def as_dict(self) -> dict:
        return {"categories": sorted(self.categories), "colours": sorted(self.colours)}


def parse_query(text: str) -> ParsedQuery:
    remaining = f" {text.lower()} "
    parsed = ParsedQuery()
    for pattern, keys in CATEGORY_PATTERNS:
        rx = re.compile(r"\b(?:" + pattern + r")\b")
        if rx.search(remaining):
            parsed.categories |= keys
            remaining = rx.sub(" ", remaining)
    for match in _COLOUR_RE.finditer(text.lower()):
        word = match.group(1)
        # "denim" names a fabric as often as a colour; only count it as blue
        # when no explicit colour is given.
        if word == "denim":
            continue
        parsed.colours.add(COLOUR_WORDS[word])
    if not parsed.colours and re.search(r"\bdenim\b", text.lower()):
        parsed.colours.add("blue")
    return parsed
