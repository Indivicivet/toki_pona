from pathlib import Path
import re
from collections import Counter

import matplotlib.pyplot as plt
import wordcloud


def do_analysis(filename):
    all_text = Path(filename).read_text()
    just_letters = re.sub(r"[^a-zA-Z \t\n]", "", all_text)
    words = [x.strip() for x in just_letters.split()]
    counts = Counter(words)
    print(counts)
    print(f"{len(counts)} distinct words")
    wordcloud.WordCloud(
        width=1280,
        height=720,
        max_words=1000,
        prefer_horizontal=1,
    ).generate_from_frequencies(counts).to_image().show()
    plt.bar(*zip(*counts.most_common()))
    plt.show()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        dest="input_file",
        required=True,
    )
    args = parser.parse_args()
    do_analysis(args.input_file)
