from pathlib import Path


def do_stuff(file):
    txt = Path(file).read_text()
    txt = txt.replace(" e ", ">>")
    txt = txt.replace(" pi ", ";")
    return txt


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
