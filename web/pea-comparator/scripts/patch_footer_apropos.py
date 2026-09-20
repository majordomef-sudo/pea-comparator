# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)

# 1) Lien /a-propos dans le footer d index.html (apres Blog)
d = open("index.html", encoding="utf-8").read()
old = "\u00b7 <a href=\"/blog/\">Blog</a>"
new = "\u00b7 <a href=\"/blog/\">Blog</a> \u00b7 <a href=\"/a-propos\">\u00c0 propos</a>"
n = d.count(old)
d = d.replace(old, new)
open("index.html", "w", encoding="utf-8").write(d)
print("footer /a-propos index:", n, "rempl.")
