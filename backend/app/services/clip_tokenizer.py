"""CLIP's byte-pair tokenizer without PyTorch (returns numpy arrays).

Adapted from OpenAI CLIP / open_clip ``SimpleTokenizer`` (MIT License,
Copyright (c) 2021 OpenAI). Behaviour matches open_clip's default tokenizer for
ViT-B-32: lower-case + whitespace clean, <start_of_text>/<end_of_text>, 77
tokens, truncation keeps <end_of_text> last, padded with 0. A test checks it
against open_clip token-for-token.
"""

from __future__ import annotations

import gzip
import html
from functools import lru_cache
from pathlib import Path

import ftfy
import numpy as np
import regex as re

BPE_PATH = Path(__file__).resolve().parents[1] / "data" / "bpe_simple_vocab_16e6.txt.gz"
CONTEXT_LENGTH = 77


@lru_cache
def bytes_to_unicode() -> dict[int, str]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


def get_pairs(word: tuple[str, ...]) -> set[tuple[str, str]]:
    return {(a, b) for a, b in zip(word, word[1:])}


def clean(text: str) -> str:
    text = ftfy.fix_text(text)
    text = html.unescape(html.unescape(text)).strip()
    return " ".join(text.split()).strip().lower()


class ClipTokenizer:
    def __init__(self, bpe_path: Path = BPE_PATH, context_length: int = CONTEXT_LENGTH):
        self.byte_encoder = bytes_to_unicode()
        merges = gzip.open(bpe_path).read().decode("utf-8").split("\n")
        merges = [tuple(m.split()) for m in merges[1 : 49152 - 256 - 2 + 1]]
        vocab = list(self.byte_encoder.values())
        vocab = vocab + [v + "</w>" for v in vocab]
        vocab += ["".join(m) for m in merges]
        specials = ["<start_of_text>", "<end_of_text>"]
        vocab += specials
        self.encoder = {tok: i for i, tok in enumerate(vocab)}
        self.bpe_ranks = {m: i for i, m in enumerate(merges)}
        self.cache = {t: t for t in specials}
        words = r"""|'s|'t|'re|'ve|'m|'ll|'d|[\p{L}]+|[\p{N}]|[^\s\p{L}\p{N}]+"""
        self.pat = re.compile("|".join(re.escape(t) for t in specials) + words, re.IGNORECASE)
        self.sot = self.encoder["<start_of_text>"]
        self.eot = self.encoder["<end_of_text>"]
        self.context_length = context_length

    def bpe(self, token: str) -> str:
        if token in self.cache:
            return self.cache[token]
        word = tuple(token[:-1]) + (token[-1] + "</w>",)
        pairs = get_pairs(word)
        if not pairs:
            return token + "</w>"
        while True:
            bigram = min(pairs, key=lambda p: self.bpe_ranks.get(p, float("inf")))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word: list[str] = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                except ValueError:
                    new_word.extend(word[i:])
                    break
                new_word.extend(word[i:j])
                i = j
                if word[i] == first and i < len(word) - 1 and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = tuple(new_word)
            if len(word) == 1:
                break
            pairs = get_pairs(word)
        out = " ".join(word)
        self.cache[token] = out
        return out

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        for token in re.findall(self.pat, clean(text)):
            token = "".join(self.byte_encoder[b] for b in token.encode("utf-8"))
            ids.extend(self.encoder[t] for t in self.bpe(token).split(" "))
        return ids

    def __call__(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.context_length), dtype=np.int64)
        for row, text in enumerate(texts):
            tokens = [self.sot, *self.encode(text), self.eot]
            if len(tokens) > self.context_length:
                tokens = tokens[: self.context_length]
                tokens[-1] = self.eot
            out[row, : len(tokens)] = tokens
        return out
