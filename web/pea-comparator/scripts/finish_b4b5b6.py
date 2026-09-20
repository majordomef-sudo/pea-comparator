# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
# ajouter /a-propos au sitemap (apres methodologie)
d = open("sitemap.xml", encoding="utf-8").read()
if "/a-propos" not in d:
    entry = "  <url><loc>https://alfredstudio.mooo.com/a-propos</loc><lastmod>2026-09-20</lastmod><changefreq>monthly</changefreq><priority>0.5</priority></url>"
    d = d.replace("</urlset>", entry + chr(10) + "</urlset>")
    open("sitemap.xml", "w", encoding="utf-8").write(d)
    print("sitemap: /a-propos ajoute")
else:
    print("sitemap: deja present")
# deploy
import subprocess
for f in ["a-propos.html", "index.html", "sitemap.xml"]:
    subprocess.run(["sudo", "-n", "cp", f, "/var/www/html/" + f])
print("deploy ok")
