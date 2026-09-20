# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)

# 1) Ajouter lien /a-propos dans le footer util d index.html (apres Methodologie)
d = open("index.html", encoding="utf-8").read()
old = "<a href=\"/methodologie\">M\u00e9thodologie</a>"
new = "<a href=\"/methodologie\">M\u00e9thodologie</a>\n    <a href=\"/a-propos\">\u00c0 propos</a>"
n = d.count(old)
d = d.replace(old, new, 1)
open("index.html", "w", encoding="utf-8").write(d)
print("footer /a-propos ajoute dans index:", n, "rempl.")
