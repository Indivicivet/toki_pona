from pathlib import Path


def do_stuff(file):
    txt = Path(file).read_text()
    sents = [
        s.strip()
        for line in txt.splitlines()
        for s in line.split(".")
        if s.strip()
    ]
    for i, s in enumerate(sents):
        s2 = s.replace(" e ", ">>").replace(" pi ", ";")
        sents[i] = s2
    return ". ".join(sents)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        dest="input_file",
        required=True,
    )
    args = parser.parse_args()
    text_mushed = do_stuff(args.input_file)
    print(text_mushed)
