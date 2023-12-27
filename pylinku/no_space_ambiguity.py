import itertools
from collections import defaultdict

import pylinku

words = pylinku.load_words_str()

ways_to_form = defaultdict(list)

for combo in itertools.combinations_with_replacement(words, 3):
    ways_to_form["".join(combo)].append(" ".join(combo))

for combo, vals in ways_to_form.items():
    if len(vals) == 1:
        continue
    print(combo, vals)
