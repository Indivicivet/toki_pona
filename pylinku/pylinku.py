import functools
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import toml

SONA_FOLDER = Path(__file__).parent.parent.parent / "sona"


@functools.total_ordering
class Usage(Enum):
    CORE = -1
    WIDESPREAD = -2
    COMMON = -3
    UNCOMMON = -4
    RARE = -5
    OBSCURE = -6
    UNKNOWN = -99

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


@dataclass
class Word:
    word: str
    usage: Usage = Usage.OBSCURE

    def __str__(self):
        return self.word


CATEGORY_MAP = {
    "core": Usage.CORE,
    "widespread": Usage.WIDESPREAD,
    "common": Usage.COMMON,
    "uncommon": Usage.UNCOMMON,
    "rare": Usage.RARE,
    "obscure": Usage.OBSCURE,
}


def load_word_file(f):
    data = toml.load(f)
    return Word(
        word=data["word"],
        usage=CATEGORY_MAP.get(data["usage_category"], Usage.UNKNOWN),
    )


def load_words(
    min_usage=Usage.WIDESPREAD,
    word_folder=SONA_FOLDER / "words",
):
    files = list(word_folder.glob("*toml"))
    if not files:
        raise ValueError(f"found no files in {word_folder}")
    return [
        word
        for f in files
        if (word := load_word_file(f)).usage >= min_usage
    ]


if __name__ == "__main__":
    WORDS = load_words()
    print(WORDS[0])
    print(repr(WORDS[0]))
