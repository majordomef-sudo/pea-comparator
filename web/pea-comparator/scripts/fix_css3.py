# -*- coding: utf-8 -*-
p = "/home/ubuntu/.openclaw/workspace/web/pea-comparator/style.css"
d = open(p, encoding="utf-8").read()
n = d.count("\\n")
d2 = d.replace("\\n", chr(10))
# enlever les lignes vides multiples
import re
d2 = re.sub(chr(10)+"{3,}", chr(10)+chr(10), d2)
open(p, "w", encoding="utf-8").write(d2)
print("remplace:", n, "occurrences | encore:", "\\n" in d2)
print("taille:", len(d2))