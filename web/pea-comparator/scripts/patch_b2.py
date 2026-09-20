# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
BT = chr(96)

# 1) Date de MAJ data unifiee (15/09 -> 20/09)
a = open("app.min.js", encoding="utf-8").read()
n = a.count(chr(39) + "15/09/2026" + chr(39))
a = a.replace(chr(39) + "15/09/2026" + chr(39), chr(39) + "20/09/2026" + chr(39))
open("app.min.js", "w", encoding="utf-8").write(a)
print("date MAJ remplacee:", n, "fois")

# 2) data-lab sur les 9 cellules du template de table
a2 = open("app.min.js", encoding="utf-8").read()
i = a2.find("data-isin=")
j = a2.rfind("return ", 0, i)
k = a2.find(BT, i)
seg = a2[j:k]
labs = ["ISIN", "Nom", "Frais", "SRI", "Perf 5A", "Emetteur", "PEA", "Score", "Detail"]
out = seg
for lab in labs:
    p = out.find("<td")
    if p >= 0:
        out = out[:p] + "<td data-lab=\"" + lab + "\"" + out[p+3:]
    else:
        print("WARN: td manquant pour", lab)
a2 = a2[:j] + out + a2[k:]
open("app.min.js", "w", encoding="utf-8").write(a2)
print("data-lab ajoutes:", out.count("data-lab="))

# 3) Note watchlist dans index.html
i2 = open("index.html", encoding="utf-8").read()
old = "<span id=\"watchlistItems\"></span>"
new_ = old + "<span style=\"display:block;font-size:.72rem;color:#8a9bb0;margin-top:4px\">Sauvegard\u00e9 sur cet appareil (localStorage) \u2014 jamais transmis.</span>"
if old in i2:
    i2 = i2.replace(old, new_)
    open("index.html", "w", encoding="utf-8").write(i2)
    print("note watchlist ajoutee")
else:
    print("WARN: watchlistItems introuvable")
print("OK B2")
