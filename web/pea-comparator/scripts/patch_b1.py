# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
D = chr(36)
a = open("app.min.js", encoding="utf-8").read()
old_td = "<td>" + D + "{e.isin}</td>"
new_td = "<td><a href=\"/etf/" + D + "{e.isin}/\" class=\"etf-fiche-link\">" + D + "{e.isin}</a></td>"
n = a.count(old_td)
a = a.replace(old_td, new_td)
open("app.min.js", "w", encoding="utf-8").write(a)
print("ISIN->lien:", n)
redirect = "<script>window.addEventListener(\"load\",function(){var h=location.hash;if(h&&h.indexOf(\"#etf-\")===0){location.replace(\"/etf/\"+h.slice(5)+\"/\")}});</script>"
for f in ("index.html", "top-etf.html"):
    t = open(f, encoding="utf-8").read()
    if "redirectAncienneAncre" not in t:
        t = t.replace("</body>", redirect + "</body>")
        open(f, "w", encoding="utf-8").write(t)
        print(f + ": redirect ajoute")
    else:
        print(f + ": deja present")
print("OK")
