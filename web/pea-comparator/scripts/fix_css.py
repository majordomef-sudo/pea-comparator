# -*- coding: utf-8 -*-
p = "/home/ubuntu/.openclaw/workspace/web/pea-comparator/style.css"
d = open(p, encoding="utf-8").read()
# retirer les lignes avec backslash-n littéraux ajoutées par erreur
import re
d2 = re.sub(r"\\n/* Lot B1.*?margin-right:6px}", "", d, flags=re.S)
# nettoyer aussi la ligne vide multiple
while "\\n" in d2:
    d2 = d2.replace("\\n", "")
open(p, "w", encoding="utf-8").write(d2)
print("css cleaned:", "Lot B1" not in d2)