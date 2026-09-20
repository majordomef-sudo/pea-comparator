# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
urls = []
def add(u, prio, freq):
    urls.append((u, prio, freq))
add("https://alfredstudio.mooo.com/", "1.0", "weekly")
add("https://alfredstudio.mooo.com/blog/", "0.9", "weekly")
add("https://alfredstudio.mooo.com/top-etf.html", "0.8", "weekly")
add("https://alfredstudio.mooo.com/bonus-pea.html", "0.7", "monthly")
add("https://alfredstudio.mooo.com/methodologie", "0.6", "monthly")
add("https://alfredstudio.mooo.com/outils/", "0.7", "monthly")
add("https://alfredstudio.mooo.com/etf/", "0.6", "monthly")
for slug in ["comparer-2-etf","top-etf-par-indice","simulation-allocation","pea-vs-av-vs-cto","interets-composes","plan-40-ans","chemin-1-million","independance-financiere","impact-des-frais","inflation","retraits-mensuels","plan-rattrapage"]:
    add("https://alfredstudio.mooo.com/outils/" + slug + "/", "0.5", "monthly")
for d in os.listdir("etf"):
    if os.path.isdir("etf/" + d) and os.path.exists("etf/" + d + "/index.html") and len(d) == 12:
        add("https://alfredstudio.mooo.com/etf/" + d + "/", "0.4", "monthly")
for p in ["mentions-legales","politique-de-confidentialite","cgu","avertissement-investissement","affiliation"]:
    add("https://alfredstudio.mooo.com/" + p, "0.3", "monthly")
xml = ['<?xml version="1.0" encoding="UTF-8"?>']
xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
for u, prio, freq in urls:
    xml.append('  <url><loc>' + u + '</loc><lastmod>2026-09-20</lastmod><changefreq>' + freq + '</changefreq><priority>' + prio + '</priority></url>')
xml.append('</urlset>')
open("sitemap.xml", "w", encoding="utf-8").write(chr(10).join(xml))
print("sitemap URLs:", len(urls))
