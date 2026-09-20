# -*- coding: utf-8 -*-
p = "/home/ubuntu/.openclaw/workspace/web/pea-comparator/style.css"
d = open(p, encoding="utf-8").read()
# remplacer les backslash-n litteraux (2 caracteres \ + n) par de vraies nouvelles lignes
d2 = d.replace("\\n", chr(10))
# nettoie les doublons d espacements
d2 = d2.replace(chr(10)*3, chr(10)*2)
open(p, "w", encoding="utf-8").write(d2)
print("nouvelle ligne reelle dans css:", "\\n" not in d2)
print("taille css:", len(d2))
print("--- fin du fichier ---")
print(d2[-400:])