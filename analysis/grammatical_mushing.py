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
        if s.split()[0] == "mi":
            s = "mi li" + s[2:]
        elif s.split()[0] == "sina":
            s = "sina li" + s[4:]
        if " li " in s:
            idx = s.index(" li ")
            s = "[" + s[:idx] + "]" + s[idx + 4:]
        if " la " in s:
            # todo :: recursive parsing needed eh...?
            idx = s.index(" la ")
            s = "{" + s[:idx] + "} " + s[idx + 4:]
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
