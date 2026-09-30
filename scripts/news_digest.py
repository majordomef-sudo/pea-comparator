#!/usr/bin/env python3
"""news_digest.py - Briefing matinal (/news) d'Eric.

Tire 4 axes d'actualite (Google News RSS, FR) et envoie une synthese courte
sur Telegram. Aucune dependance externe, aucun appel LLM, aucun cout API.

Usage:
    python3 scripts/news_digest.py            # envoie sur Telegram
    python3 scripts/news_digest.py --dry-run  # affiche seulement
"""
import json, os, sys, time, html, urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify_alfred import send_telegram

UA = {"User-Agent": "Mozilla/5.0 (compatible; AlfredNewsDigest/1.0)"}

AXES = [
    ("MARQUES", "CAC 40 bourse"),
    ("MACRO", "inflation zone euro BCE taux"),
    ("EPARGNE", "ETF PEA epargne"),
    ("TECH", "YouTube monetisation IA"),
]
FEED = "https://news.google.com/rss/search?q={q}&hl=fr&gl=FR&ceid=FR:fr"
MAX_PAR_AXE = 5


def collecter(q, essais=2):
    url = FEED.format(q=urllib.parse.quote_plus(q))
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=15).read()
            root = ET.fromstring(data)
            items = []
            for it in root.iter("item"):
                titre = (it.findtext("title") or "").strip()
                src = (it.findtext("source") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                if titre:
                    items.append({"t": titre, "s": src, "d": pub})
                if len(items) >= MAX_PAR_AXE:
                    break
            return items
        except Exception as e:
            if i == essais - 1:
                return [{"err": str(e)[:90]}]
            time.sleep(2)
    return []


def construire():
    blocs, erreurs = [], []
    for nom, q in AXES:
        items = collecter(q)
        lignes = []
        for it in items:
            if "err" in it:
                erreurs.append(nom + ": " + it["err"])
                continue
            src = (" - <i>" + html.escape(it["s"]) + "</i>") if it["s"] else ""
            titre = html.escape(it["t"].split(" - ")[0][:150])
            lignes.append("&bull; " + titre + src)
        if lignes:
            blocs.append("<b>" + nom + "</b>\n" + "\n".join(lignes))
    date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    entete = "<b>Briefing du " + date + "</b>\n"
    corps = "\n\n".join(blocs) if blocs else "Aucune actualite recuperee."
    pied = ""
    if erreurs:
        pied = "\n\n<i>Sources en echec : " + html.escape("; ".join(erreurs)) + "</i>"
    return entete + "\n" + corps + pied


def main():
    dry = "--dry-run" in sys.argv
    msg = construire()
    if dry:
        print(msg)
        return 0
    ok = send_telegram(msg, parse_mode="HTML")
    print(("envoye" if ok else "ECHEC envoi") + " - " + str(len(msg)) + " caracteres")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

