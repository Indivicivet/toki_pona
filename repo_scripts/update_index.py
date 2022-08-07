from pathlib import Path

index_folder = Path(__file__).resolve().parent.parent
index_file = index_folder / "index.html"

words_folder_name = "words"
words = Path(__file__).resolve().parent.parent / words_folder_name

print("generating html")
html = """
<html>
<head>
<link rel="stylesheet" href="index_style.css">
</head>
<body>
<header>toki pona</header>
"""

for word_file in words.glob("*.*"):
    html += f"""
<div class="word">
    {word_file.stem} <br/>
    <img src="{words_folder_name}/{word_file.name}" />
</div>
"""

html += """
</body>
</html>
"""

index_file.parent.mkdir(exist_ok=True, parents=True)
index_file.write_text(html)
print(f"successfully wrote {index_file}")
