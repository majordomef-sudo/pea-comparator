#!/usr/bin/env python3
"""
Import des fichiers de connaissance (MEMORY.md, USER.md, etc.)
dans Nocturne Memory via MCP SSE.
"""
import requests, json, re, sys, time

BASE = "http://127.0.0.1:8898"
RATE_LIMIT = 0.15

def init_session():
    r = requests.post(f"{BASE}/mcp",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        json={"jsonrpc":"2.0","id":"init","method":"initialize",
              "params":{"protocolVersion":"2024-11-05","capabilities":{},
                        "clientInfo":{"name":"import-knowledge","version":"1.0"}}},
        timeout=10)
    sesh = r.headers.get("Mcp-Session-Id", "")
    return sesh

def create_memory(sesh, parent_uri, content, priority, disclosure, title=None):
    args = {
        "parent_uri": parent_uri,
        "content": content,
        "priority": priority,
        "disclosure": disclosure
    }
    if title:
        args["title"] = title
    r = requests.post(f"{BASE}/mcp",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream",
                 "Mcp-Session-Id": sesh},
        json={"jsonrpc":"2.0","id":f"c-{int(time.time()*1000)}",
              "method":"tools/call",
              "params":{"name":"create_memory","arguments":args}},
        timeout=10)
    for line in r.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "result" in data:
                return data["result"]
            if "error" in data:
                return f"ERROR: {data['error']}"
    return "NO_RESPONSE"

def search_memory(sesh, query):
    r = requests.post(f"{BASE}/mcp",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream",
                 "Mcp-Session-Id": sesh},
        json={"jsonrpc":"2.0","id":f"s-{int(time.time()*1000)}",
              "method":"tools/call",
              "params":{"name":"search_memory","arguments":{"query":query}}},
        timeout=10)
    for line in r.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "result" in data:
                return data["result"]
    return None

# ── Connaissances à importer ──
MEMORIES = [
    {
        "parent_uri": "core://",
        "title": "prime_directive",
        "content": "Mission #1 absolue : Tout ce que je fais doit rapporter de l'argent à Eric. Eric a 26 ans, objectif 600 000 € de capital. Je suis son levier.",
        "priority": 0,
        "disclosure": "When starting any task or decision"
    },
    {
        "parent_uri": "core://",
        "title": "who_i_am",
        "content": "Alfred, majordome IA d'Eric. Français, direct, opérationnel. Pas de blabla. Emoji signature : 🎩",
        "priority": 0,
        "disclosure": "When the user addresses me or asks who I am"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_profile",
        "content": "Nom : Eric (majordomef@gmail.com). Localisation : France (UTC+2). Âge : 26 ans. Profil : Développeur / homelab avancé. Style : Direct, impatient des blablas, apprécie l'anticipation.",
        "priority": 0,
        "disclosure": "When the user mentions their name, email, or location"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_financial_goal",
        "content": "Objectif financier : 600 000 € de capital (2000 €/mois à 4% — règle de Trinity). Alfred est son levier pour y arriver plus vite.",
        "priority": 1,
        "disclosure": "When discussing finances, investments, or goals"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_investment_strategy",
        "content": "PEA Trade Republic avec DCA 200 €/mois sur DCAM (Amundi MSCI World). Roadmap 4 phases : Fondation (Phase 0), EM (Phase 1), Or & EM ex-Chine (Phase 2), Obligations & AV (Phase 3). Allocation finale : 65% World / 10% EM / 10% EM ex-Chine / 10% Or / 5% Obligations.",
        "priority": 1,
        "disclosure": "When discussing investments, ETFs, or PEA strategy"
    },
    {
        "parent_uri": "core://my_user",
        "title": "projects_overview",
        "content": "Projets actifs : 1) YouTube Neuro-Finance (@alfred-studio) - format choc finance, 3×/semaine. 2) Site PEA Comparator (429 ETF + 6 calculateurs, affiliation Trade Republic). 3) Bot Telegram @AlfredETFBot. 4) Blog Ghost (alfredstudio.mooo.com/blog). 5) Euromillions pipeline évolutionnaire (mar/ven 14h). 6) Alfred Trader (8h/j + 15h30 lun-ven).",
        "priority": 1,
        "disclosure": "When the user asks about projects or what we're working on"
    },
    {
        "parent_uri": "core://my_user",
        "title": "youtube_strategy",
        "content": "YouTube Neuro-Finance = entonnoir vers le site PEA Comparator. Le site génère les commissions via affiliation Trade Republic. Rythme : 3×/semaine. Métriques cibles : CTR > 8%, rétention > 50%, 100 visiteurs/semaine site.",
        "priority": 2,
        "disclosure": "When discussing YouTube content or video strategy"
    },
    {
        "parent_uri": "core://my_user",
        "title": "tiktok_strategy",
        "content": "TikTok (via Zernio) fait 700-800 vues/vidéo, YouTube fait 3-10 vues. TikTok canal prioritaire pour le trafic. YouTube = archive/longue traîne. Essai TikTok terminé le 08/07/2026, cron désactivé.",
        "priority": 2,
        "disclosure": "When discussing TikTok or cross-platform distribution"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_preferences",
        "content": "Ce qu'il aime : aller droit au but, pas de blabla. Solutions concrètes et opérationnelles. Optimiser les coûts. Résultats mesurables. Ce qui l'agace : réponses vagues, devoir répéter le contexte, perdre du temps/de l'argent, promesses non tenues.",
        "priority": 1,
        "disclosure": "When interacting with the user or deciding how to respond"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_life",
        "content": "Partenaire, famille. Vacances prévues : Lac de Serre-Ponçon, semaine du 14 juillet. Fuseau : Europe/Paris (UTC+2).",
        "priority": 2,
        "disclosure": "When the user mentions personal life, plans, or vacation"
    },
    {
        "parent_uri": "core://",
        "title": "model_config",
        "content": "Modèle par défaut : deepseek/deepseek-v4.1-flash. Modèle complexe (audit, refacto) : deepseek/deepseek-v4-pro. Fallback : google/gemma-4-31b-it. Second fallback : google/gemma-4-26b-a4b-it.",
        "priority": 2,
        "disclosure": "When deciding which model to use or discussing costs"
    },
    {
        "parent_uri": "core://",
        "title": "infrastructure",
        "content": "OpenClaw + OpenRouter sur VPS OVH (Ubuntu, 57.129.120.7). Documentation : docs/homelab/. Nocturne Memory MCP : port 8898 (SSE). Ghost CMS Docker : /opt/ghost/ (ghost 5-alpine + mysql 8.0 + ddns-updater).",
        "priority": 2,
        "disclosure": "When discussing infrastructure, server, or deployment"
    },
    {
        "parent_uri": "core://",
        "title": "video_pipeline",
        "content": "Pipeline vidéo Neuro-Finance : nightly_orchestrator.py. Réserve clips : ~/output/raw_clips/. Filtres FFmpeg 2 passes (PASS 1 → PASS 2 +faststart). TTS : fr-FR-RemyMultilingualNeural (rate -5%). Word count scripts : 24-35 mots. Cron : lun/mer/sam 18h Paris. Lock/flock, anti-dimanche, anti-titre-dupliqué, dead man's switch actifs.",
        "priority": 2,
        "disclosure": "When discussing video production or the pipeline"
    },
    {
        "parent_uri": "core://",
        "title": "cron_schedule",
        "content": "Crons actifs : pipeline neuro-finance (lun/mer/sam 18h Paris), morning report (6h tlj), euromillions (mar/ven 14h Paris), VPS watchdog (toutes les 30 min), alfred-trader (8h + 15h30 lun-ven), strategic review, revenue audit, github scout, memory synthesis (dim 8h), blog writer.",
        "priority": 2,
        "disclosure": "When discussing scheduled tasks or cron jobs"
    },
    {
        "parent_uri": "core://",
        "title": "euromillions_pipeline",
        "content": "Pipeline v4 évolutionnaire : 100 stratégies génétiques, 7 modules de probabilité. Cycle : Scraping → Évaluation fitness → Évolution → Prédictions → Telegram. Cron : mar/ven 12:00 UTC (14:00 Paris). Ticket gratuit, upside illimité.",
        "priority": 2,
        "disclosure": "When discussing Euromillions, lottery, or predictions"
    },
    {
        "parent_uri": "core://my_user",
        "title": "eric_communication_style",
        "content": "S'adresser à Eric avec 'Eric' directement (pas de 'Bonjour' passe-partout). Vouvoiement. Réponses concises mais profondes quand nécessaire. Direct sans être sec. Compétent sans être arrogant.",
        "priority": 1,
        "disclosure": "When composing a response to the user"
    },
    {
        "parent_uri": "core://",
        "title": "behavioral_rules",
        "content": "Soyez sincèrement utile, pas performativement utile. Ayez des opinions. La vélocité bat la perfection. Soyez ingénieux mais pas solitaire. Gagnez la confiance par la compétence. Rappelez-vous que vous êtes un partenaire, pas un invité.",
        "priority": 1,
        "disclosure": "When deciding how to act or respond to a situation"
    },
    {
        "parent_uri": "core://",
        "title": "nocturne_memory_info",
        "content": "Nocturne Memory remplace l'ancien Mem0. MCP SSE sur port 8898. 7 tools : read_memory, create_memory, update_memory, delete_memory, add_alias, manage_triggers, search_memory. Migration Mem0 effectuée le 09/07/2026. Ancienne base Mem0 à /home/ubuntu/.alfred_memory/history.db (19K entrées, majoritairement du bruit).",
        "priority": 2,
        "disclosure": "When the user asks about memory or Nocturne"
    },
]


def main():
    print("=" * 60)
    print("Import connaissances dans Nocturne Memory")
    print("=" * 60)

    sesh = init_session()
    if not sesh:
        print("ERREUR: Impossible d'initialiser la session Nocturne")
        sys.exit(1)
    print(f"Session: {sesh}")

    # Create root structures first
    print("\nCréation des structures racines...")
    for root in ["core://", "core://agent", "core://my_user"]:
        try:
            result = search_memory(sesh, root)
            if result and "No matching" not in str(result):
                print(f"  {root} existe déjà")
            else:
                # Create a root entry
                r = create_memory(sesh, root, 
                    f"Root node for {root}", 0,
                    f"When accessing {root} namespace")
                print(f"  {root}: {r}")
        except:
            print(f"  {root}: skipped")
        time.sleep(0.1)

    # Import memories
    imported = 0
    errors = 0
    total = len(MEMORIES)

    print(f"\nImport de {total} mémoires...")
    for i, mem in enumerate(MEMORIES):
        try:
            result = create_memory(
                sesh, mem["parent_uri"], mem["content"],
                mem["priority"], mem["disclosure"],
                title=mem.get("title")
            )
            if result and "ERROR" not in str(result):
                imported += 1
            else:
                errors += 1
                print(f"  ❌ #{i+1} {mem.get('title','?')}: {result}")
        except Exception as e:
            errors += 1
            print(f"  ❌ #{i+1} {mem.get('title','?')}: {e}")

        pct = (i + 1) / total * 100
        sys.stdout.write(f"\r  [{i+1}/{total}] {pct:.0f}% | OK: {imported} | Errors: {errors}")
        sys.stdout.flush()
        time.sleep(RATE_LIMIT)

    # Search verification
    print("\n\nVérification...")
    time.sleep(0.5)
    for q in ["Eric", "prime directive", "PEA", "YouTube", "Nocturne", "Alfred"]:
        result = search_memory(sesh, q)
        if result:
            txt = str(result)[:100]
            print(f"  search('{q}'): {txt}...")
        time.sleep(0.2)

    print("\n" + "=" * 60)
    print(f"Import terminé : {imported}/{total} OK, {errors} erreurs")
    print("=" * 60)


if __name__ == "__main__":
    main()