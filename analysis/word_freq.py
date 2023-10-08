from pathlib import Path
import re
from collections import Counter


def do_analysis(filename):
    all_text = Path(filename).read_text()
    just_letters = re.sub(r"[^a-zA-Z \t\n]", "", all_text)
    words = [x.strip() for x in just_letters.split()]
    counts = Counter(words)
    print(counts)


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
