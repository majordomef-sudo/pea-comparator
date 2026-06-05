#!/usr/bin/env python3
"""
Bot Telegram public — Recherche d'ETF par ISIN + Calculateurs
Enrichi avec les données des 14 fichiers investissement d'Eric.
"""

import json
import time
import sys
import os
import signal
import requests
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("PEA_BOT_TOKEN", "")
ETF_DATA_PATH = Path(__file__).parent.parent / "pea-comparator" / "etf-data.js"
API_BASE = "https://api.telegram.org/bot"

HELP_TEXT = """🎩 <b>Alfred ETF Bot</b>

<b>🔍 Recherche</b>
Envoie un <b>ISIN</b> ou <b>nom d'ETF</b> pour voir ses infos
<code>FR001400U5Q4</code> ou "Amundi World"

<b>📋 Commandes :</b>
/help — Cette aide
/comparateur — Ouvrir le comparateur PEA
/fire — Calculateur d'indépendance financière
/compound — Simulateur intérêts composés
/top — Top ETF par catégorie
/stats — Stats du bot

🎩 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Comparateur PEA complet →</a>"""


# ── ALIAS ISIN ──────────────────────────────────────────────────────
ISIN_ALIASES = {
    "FR0010900076": "FR001400U5Q4",  # CW8 → DCAM
    "FR0010900050": "FR0014003IY1",
}

# Catégories pour /top
CATEGORIES = {
    "world": "🌍 MSCI World",
    "sp500": "🇺🇸 S&P 500",
    "europe": "🇪🇺 Europe",
    "em": "🌏 Emergents",
    "sector": "🏭 Sectoriel",
    "bond": "📜 Obligataire",
    "gold": "🥇 Or / Matières",
}


def load_etfs():
    """Charge la base ETF depuis etf-data.js"""
    try:
        raw = ETF_DATA_PATH.read_text(encoding="utf-8")
        json_str = raw.replace("window.PEA_ETFS = ", "", 1).strip()
        if json_str.endswith(";"):
            json_str = json_str[:-1]
        return json.loads(json_str)
    except Exception as e:
        print(f"[ERREUR] Chargement ETF: {e}", file=sys.stderr)
        return []


def find_etf(query):
    """Cherche un ETF par ISIN ou nom"""
    q = query.strip().upper()

    # Essayer ISIN exact
    alias = ISIN_ALIASES.get(q, q)
    for e in ETFS:
        if e["isin"].upper() == alias:
            return e

    # Essayer par nom (partiel, insensible à la casse)
    q_norm = q.lower()
    for e in ETFS:
        if q_norm in e["nom"].lower():
            return e

    # Chercher par ticker (dans le nom)
    for e in ETFS:
        if q_norm in e["isin"][:4].lower():
            return e

    return None


def search_etfs(query, limit=5):
    """Recherche multiple d'ETF"""
    q = query.strip().lower()
    results = []
    for e in ETFS:
        if q in e["isin"].lower() or q in e["nom"].lower():
            results.append(e)
    return results[:limit]


def format_etf(etf):
    """Formate les infos d'un ETF en message Telegram"""
    frais = etf["frais"] if etf["frais"] not in ("", "N/A", "?") else "N/C"
    perf = etf["perf5"] if etf["perf5"] not in ("", "N/A", "?") else "N/C"
    sri = etf["sri"] if etf["sri"] not in ("", "?") else "N/C"

    text = f"""📊 <b>{etf['nom'][:80]}</b>

<b>ISIN :</b> <code>{etf['isin']}</code>
<b>Frais :</b> {frais}%
<b>Risque (SRI) :</b> {sri}/7
<b>Perf 5 ans :</b> {perf}%
<b>Émetteur :</b> {etf['emetteur'] or 'N/C'}
<b>Pays :</b> {etf['pays'] or 'N/C'}

🔗 <a href='https://www.justetf.com/fr/etf-profile.html?isin={etf['isin']}'>DIC justETF</a>
📊 <a href='https://alfredstudio.mooo.com/pea-comparator/?isin={etf['isin']}'>Comparateur</a>"""
    return text


# ── CALCULATEURS ────────────────────────────────────────────────────
def calc_fire(income_monthly, withdrawal_rate, current, saving_monthly, return_rate, age=26):
    """Calculateur FIRE"""
    target = (income_monthly * 12) / (withdrawal_rate / 100)
    years = 0
    cap = current
    while cap < target and years < 100:
        cap = cap * (1 + return_rate / 100) + saving_monthly * 12
        years += 1

    return {
        "target": target,
        "years": years if years < 100 else None,
        "age": age + years if years < 100 else None,
        "estimate": cap,
    }


def calc_compound(init, monthly, rate, years):
    """Calculateur intérêts composés"""
    months = years * 12
    r = rate / 100 / 12
    cap = init
    invested = init
    half_target = (init + monthly * months) / 2
    found_half = None
    found_work = None

    for m in range(1, months + 1):
        cap = (cap + monthly) * (1 + r)
        invested += monthly
        if found_half is None and cap >= half_target:
            found_half = m
        if found_work is None and m % 12 == 0:
            yearly_return = (cap - (cap / (1 + r))) * 12
            if yearly_return >= monthly * 12:
                found_work = m // 12

    return {
        "final": cap,
        "invested": invested,
        "gain": cap - invested,
        "half_month": found_half,
        "work_year": found_work,
    }


# ── API TELEGRAM ────────────────────────────────────────────────────
def send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True):
    url = f"{API_BASE}{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"[ERREUR] sendMessage: {e}", file=sys.stderr)
        return None


def set_webhook():
    resp = requests.post(
        f"{API_BASE}{BOT_TOKEN}/deleteWebhook",
        json={"drop_pending_updates": True},
        timeout=10,
    )
    return resp.json()


def get_updates(offset=0):
    url = f"{API_BASE}{BOT_TOKEN}/getUpdates"
    payload = {"offset": offset, "timeout": 30, "allowed_updates": ["message"]}
    try:
        resp = requests.post(url, json=payload, timeout=35)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
        return []
    except requests.Timeout:
        return []
    except Exception as e:
        print(f"[ERREUR] getUpdates: {e}", file=sys.stderr)
        return []


def format_euro(v):
    """Format monétaire"""
    if v is None:
        return "—"
    return f"{v:,.0f}€".replace(",", " ")


def handle_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()
    sender = msg.get("from", {})
    username = sender.get("first_name", sender.get("username", "?"))
    msg_id = msg.get("message_id")

    if not chat_id or not text:
        return

    print(f"[MSG] {username}: {text}", flush=True)

    # ── COMMANDES ────────────────────────────────────────────────
    if text in ("/start", "/help"):
        send_message(chat_id, HELP_TEXT)
        return

    if text == "/comparateur":
        send_message(
            chat_id,
            "📊 <b>Comparateur ETF PEA 2026</b>\n\n"
            "429 ETF éligibles au PEA comparés : frais, SRI, performance, émetteur.\n"
            "+ 5 simulateurs : intérêts composés, FIRE, impact frais, enveloppes fiscales, allocation.\n\n"
            "🔗 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Ouvrir le comparateur →</a>",
        )
        return

    if text == "/top":
        msg = "🏆 <b>Top ETF PEA par catégorie</b>\n\n"
        msg += "🔗 Voir les classements complets :\n"
        msg += "<a href='https://alfredstudio.mooo.com/pea-comparator/'>Comparateur ETF PEA →</a>"
        send_message(chat_id, msg)
        return

    if text == "/stats":
        emetteurs = len(set(e["emetteur"] for e in ETFS if e["emetteur"]))
        avg_fees = sum(float(e["frais"]) for e in ETFS if e["frais"] and e["frais"] not in ("N/A", "?")) / max(1, len([e for e in ETFS if e["frais"] and e["frais"] not in ("N/A", "?")]))
        send_message(
            chat_id,
            f"📈 <b>Stats du bot</b>\n\n"
            f"📊 {len(ETFS)} ETF indexés\n"
            f"🏷️ {emetteurs} émetteurs\n"
            f"📉 Frais moyen : {avg_fees:.2f}%\n"
            f"🔗 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Comparateur PEA</a>",
        )
        return

    if text == "/fire":
        msg = (
            "🔥 <b>Calculateur FIRE</b>\n\n"
            "Envoie au format :\n"
            "<code>/fire 2000 4 0 200 7</code>\n\n"
            "Paramètres : revenu mensuel souhaité, taux retrait (%), "
            "capital actuel, épargne mensuelle, rendement attendu (%)\n\n"
            "Exemple : <code>/fire 2000 4 0 200 7</code>\n"
            "→ Capital nécessaire : 600 000€\n"
            "→ Atteint en ~30 ans"
        )
        send_message(chat_id, msg)
        return

    if text.startswith("/fire "):
        try:
            parts = text.split()[1:]
            income = float(parts[0])
            wrate = float(parts[1])
            current = float(parts[2])
            saving = float(parts[3])
            ret = float(parts[4])
            result = calc_fire(income, wrate, current, saving, ret, 26)
            msg = f"""🔥 <b>Résultat FIRE</b>

<b>Capital nécessaire :</b> {format_euro(result['target'])}
<b>Au rythme actuel :</b> {result['years']} ans (âge {result['age']} ans)
<b>Capital estimé à l'arrivée :</b> {format_euro(result['estimate'])}

📊 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Simulateur complet →</a>"""
        except (IndexError, ValueError):
            msg = "❌ Format invalide. Ex: <code>/fire 2000 4 0 200 7</code>"
        send_message(chat_id, msg)
        return

    if text == "/compound":
        msg = (
            "📈 <b>Simulateur intérêts composés</b>\n\n"
            "Envoie au format :\n"
            "<code>/compound 10000 200 7 30</code>\n\n"
            "Paramètres : capital initial, versement mensuel, "
            "taux annuel (%), durée (années)\n\n"
            "Exemple : <code>/compound 10000 200 7 30</code>\n"
            "→ Capital final : ~245 000€"
        )
        send_message(chat_id, msg)
        return

    if text.startswith("/compound "):
        try:
            parts = text.split()[1:]
            init = float(parts[0])
            monthly = float(parts[1])
            rate = float(parts[2])
            years = int(parts[3])
            result = calc_compound(init, monthly, rate, years)
            half_str = f"Mois {result['half_month']} (~{result['half_month']/12:.1f} ans)" if result['half_month'] else "Après la période"
            work_str = f"Année {result['work_year']}" if result['work_year'] else "Pas encore"
            msg = f"""📈 <b>Résultat intérêts composés</b>

<b>Capital final :</b> {format_euro(result['final'])}
<b>Capital investi :</b> {format_euro(result['invested'])}
<b>Plus-value :</b> {format_euro(result['gain'])}
<b>🔄 Moitié du chemin :</b> {half_str}
<b>⚡ Argent travaille :</b> {work_str}

📊 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Simulateur complet →</a>"""
        except (IndexError, ValueError):
            msg = "❌ Format invalide. Ex: <code>/compound 10000 200 7 30</code>"
        send_message(chat_id, msg)
        return

    # ── RECHERCHE ETF ───────────────────────────────────────────
    # Nettoyage : enlever espaces, vérifier si ISIN
    query_clean = text.replace(" ", "").upper()

    # Si ça ressemble à un ISIN ou une recherche textuelle courte
    if len(query_clean) == 12 and query_clean[:2].isalpha() or len(text) > 2:
        # Recherche unique
        etf = find_etf(text)
        if etf:
            reply = format_etf(etf)
        else:
            # Recherche multiple
            results = search_etfs(text, limit=5)
            if results:
                lines = [f"🔍 <b>Résultats pour \"{text}\" :</b>\n"]
                for e in results:
                    name = e['nom'][:60]
                    fees = e['frais'] if e['frais'] not in ('', 'N/A', '?') else 'N/C'
                    lines.append(f"• <code>{e['isin']}</code> — {name} ({fees}%)")
                lines.append("\n📊 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Comparateur complet →</a>")
                reply = "\n".join(lines)
            else:
                reply = (
                    f"❌ <b>ETF non trouvé</b>\n\n"
                    f"<code>{text}</code> n'est pas dans ma base.\n\n"
                    f"📊 <a href='https://alfredstudio.mooo.com/pea-comparator/'>Voir tous les ETF</a>"
                )
    else:
        reply = (
            "❌ <b>Format incorrect</b>\n\n"
            "Un ISIN fait 12 caractères (ex: <code>FR001400U5Q4</code>).\n"
            "Tu peux aussi chercher par nom d'ETF.\n\n"
            "Envoie /help pour les commandes."
        )

    send_message(chat_id, reply)


# ── MAIN ────────────────────────────────────────────────────────────
def main():
    global ETFS

    if not BOT_TOKEN:
        print("❌ PEA_BOT_TOKEN non configuré", file=sys.stderr)
        sys.exit(1)

    ETFS = load_etfs()
    print(f"✅ Base ETF chargée : {len(ETFS)} fonds", flush=True)

    set_webhook()
    print("✅ Webhook désactivé", flush=True)

    me = requests.post(f"{API_BASE}{BOT_TOKEN}/getMe", timeout=10).json()
    if me.get("ok"):
        print(f"🤖 @{me['result']['username']} prêt !", flush=True)

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                update_id = update.get("update_id")
                if update_id:
                    offset = update_id + 1
                msg = update.get("message")
                if msg:
                    handle_message(msg)
        except KeyboardInterrupt:
            print("\n🛑 Arrêt", flush=True)
            break
        except Exception as e:
            print(f"[ERREUR] {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()