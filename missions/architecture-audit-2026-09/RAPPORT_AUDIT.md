# RAPPORT AUDIT ARCHITECTURE - Alfred/OpenClaw
Date : 2026-09-11 | Mission : amelioration continue via 6 depots de reference
Statut : AUDIT COMPLET - aucune modification majeure appliquee (accord Eric requis)

## 1. SYNTHESE DE L'AUDIT DES 6 DEPOTS

### Mem0 (Python, Apache-2.0) - Couche memoire LLM
- Extraction de faits via prompts : FACT_RETRIEVAL_PROMPT, ADDITIVE_EXTRACTION_PROMPT
  (basee UNIQUEMENT sur les messages user, pas assistant) - separation stricte
- 3 types de memoire : SEMANTIC (faits/preferences), EPISODIC (evenements derives),
  PROCEDURAL (savoir-faire) - enum MemoryType
- Scoring hybride additif : score = (semantique + BM25 normalise sigmoide + boost entite 0.5) / max
  - parametres BM25 adaptatifs selon longueur de requete (5,0/0,7 a 12,0/0,5)
  - seuil applique AVANT combinaison (gate)
- Dedup : hash + similarite -> update_memory au lieu de add
- Storage SQLite : tables history + messages (get_history, get_last_messages par session)
- Multi-niveau : user_id / agent_id / run_id / session_id
- Redaction automatique des secrets (api_key, token, password...) dans configs
- Telemetry + notices de scale / decay

### Qdrant v1.19.1 (Rust, Apache-2.0) - Vector DB haute perfs
- Index HNSW dense + index sparse (BM25 natif, lib bm25/)
- Payload index structure (filtres sur metadata), quantisation (product/binary), WAL
- Sharding + collection manager + snapshots
- lib/segment : vector_storage, payload_storage, hnsw_index, sparse_index, field_index

### Composio (Python/TS, MIT) - Orchestration d'outils
- 1000+ toolkits pre-authentifies, sessions par user, triggers, sandbox
- Adapters OpenAI/Claude/LangChain/Vercel, CLI
- SDK inspectable : source packagee dans le package (les agents lisent les outils)
- python/composio/core/ : custom_tool, auth_configs, connected_accounts

### OpenHands (TS/Python, MIT) - Agent Canvas
- Protocole ACP (Agent-Client Protocol), harness registry avec decision explicite
- Backends : docker, VM, cloud ; automations Slack/GitHub/Linear
- Specs : backend-management, canvas-extensions, llm-defaults, mcp-settings

### SWE-agent (Python, MIT) - Agent de code minimal
- Config YAML unique gouvernant l'agent (design data-driven)
- Boucle simple ; mini-swe-agent = 100 lignes, perf equivalente (lecon : la simplicite bat la complexite)
- modules : agent/, tools/, environment/, inspector/

### PydanticAI (Python, MIT) - Agent loop type
- Typage de bout en bout (pydantic) : function_schema, outputs valides
- durable_exec : operations durables via Prefect/Temporal (reprise apres crash)
- Capabilities modulaires : tool_search, mcp, web_fetch, web_search, image_generation
- Failover modele automatique, OpenTelemetry (_otel_messages, _instrumentation)
- Protection SSRF integree (_ssrf.py)

### Evolutions recentes notables (HEAD clones 11/09/2026)
- Mem0 : fix securite (12 vulns Vanta/Dependabot), additive extraction, decay/TTL, redaction secrets
- Qdrant : bump v1.19.1, sparse + BM25 natif
- Composio : suppression fastmode, SDK inspectable embarque
- OpenHands : ACP harness registry decision explicite
- SWE-agent : focus mini-swe-agent (100 lignes SOTA)
- PydanticAI : durable_exec (Prefect/Temporal), capabilities, MCP + tool search

## 2. COMPARAISON AVEC L'ARCHITECTURE ALFRED/OPENCLAW

### Points forts existants (a conserver)
- Memoire fichier : MEMORY.md + memory/YYYY-MM-DD.md + DREAMS.md, bootstrap auto
- Moteur memoire builtin SQLite : FTS5 (BM25) + vecteurs + hybride (sqlite-vec), embeds locaux (llama.cpp, Ollama) ou OpenAI
- Agent loop serialise : files d'attente, write lock, timeouts, lifecycle events
- 2 systemes de hooks, skills, MCP (nocturne_memory :8898), sub-agents
- Pipeline video robuste en prod (flock, anti-doublon, dead man's switch)
- Model router (deepseek flash/pro + fallbacks Gemma) ; 12 scripts cron auto-amelioration
- Nudge nocturne : extraction de faits + dedup 'deja connu' deja fonctionnelle

### GAPS identifies (ce qui manque)
1. Dedup insuffisante des souvenirs (le nudge du 11/09 a cree 5 faits dont 3 deja connus)
2. Pas de scoring/classement : recence, boost entites, seuils de pertinence
3. Pas de TTL/oubli : MEMORY.md gonfle, risque de depassement du budget bootstrap
4. Pas de memoire episodique structuree par session (history/messages)
5. Pas de memoire procedurale (lecons reutilisables des succes/echecs)
6. Retry/fallback limite : incidents fact-check (10/09), timeout 1800s (28/08)
7. Observabilite basique : pas d'OpenTelemetry, couts par outil non traces
8. Validation outils limitee : pas de schemas entree/sortie generes
9. Pas de tool registry central : chemins casses (70% des bugs historiques)
10. Pas de reprise d'operation longue apres crash (durable_exec manquant)

## 3. ARCHITECTURE MEMOIRE CIBLE - Mem0 + Qdrant pour Alfred

Principe : garder la memoire fichier (simple, lisible par l'humain) + couche vectorielle
Qdrant (puissante, locale, zero cout).

COUCHE PRESENTATION : MEMORY.md + memory/YYYY-MM-DD.md + DREAMS.md
   | (hooks + nudge write-memory)
COUCHE INGESTION (style Mem0) :
   1. Extraction LLM de faits (prompt FACT_RETRIEVAL-like, user-only)
   2. Typage : SEMANTIC / EPISODIC / PROCEDURAL
   3. Dedup : hash + cosinus >= 0.85 -> update/merge au lieu d'add
   | (embeddings LOCAUX : Ollama bge-m3 ou llama.cpp - zero cout API)
COUCHE STOCKAGE (Qdrant local, Docker port 6333) :
   - Collection 'memories' : vector dense HNSW + sparse BM25 natif
   - Payload : type, scope (user/session/agent), recence, source, importance, hash dedup, TTL, tags
   | (retrieval a chaque session)
COUCHE RECUPERATION (style Mem0) :
   1. Query embeddings + filtres de scope
   2. Hybride Qdrant : dense + BM25
   3. Score additif normalise : semantique + BM25 + boost recence/entites
   4. Seuil -> top-k ; rerank optionnel (cross-encoder local)
   | (cron hebdomadaire)
COUCHE MAINTENANCE :
   - TTL par type (episodique 30j, semantique 365j, procedurale infini)
   - Consolidation des doublons, distillation notes -> MEMORY.md
   - Controle taille + couts embeddings (batch basse frequence)

Decisions cles :
- Court terme : SQLite (history/messages style Mem0 storage) par session
- Long terme : Qdrant (faits distilles) + MEMORY.md (resume bootstrap)
- Dedup : hash + cosinus, update au lieu d'add, dry-run avant activation
- Oubli : TTL + archive reversible (jamais de delete sec)
- Cout : embeddings locaux uniquement ; extraction LLM en batch basse frequence
- Local : Qdrant Docker local, pas de cloud ; licences Apache-2.0 compatibles

## 4. TOP 10 AMELIORATIONS RECOMMANDEES (classifiees)

### CRITIQUE (fiabilite / memoire)
1. [Mem0] Deduplication + update des souvenirs
   - Probleme : le nudge ecrit des doublons (11/09 : 3 faits 'deja connu' re-crees)
   - Solution : hash + cosinus >= 0.85 -> update au lieu d'add ; dry-run d'abord
   - Fichiers : scripts/memory_dedup.py, hook memory:write ; Test : paires dupliquees -> 1 seul souvenir
2. [Mem0] TTL / oubli / archivage
   - Probleme : MEMORY.md gonfle, risque de depassement du budget bootstrap
   - Solution : TTL par type (semantique 365j, episodique 30j, procedurale infini) + archive reversible
   - Fichiers : scripts/memory_ttl.py, cron hebdo ; Test : dry-run + rapport de ce qui serait archive
3. [Mem0+PydanticAI] Retry backoff + fallback modele robuste
   - Probleme : fact-check non-convergence 10/09, timeout 1800s 28/08
   - Solution : retry exponentiel + jauge max + bascule modele auto (routeur existe deja en partie)
   - Fichiers : pipeline/pipeline_orchestrator.py (wrapper), config router ; Test : injection d'echecs simules
4. [Mem0+Qdrant] Recherche semantique vectorielle a l'echelle
   - Probleme : SQLite sqlite-vec OK mais ne scale pas (annotations, milliers de souvenirs)
   - Solution : indexer les notes dans Qdrant Docker local, hybride dense+BM25 natif
   - Fichiers : scripts/memory_indexer.py, scripts/memory_search.py ; Test : top-5 juge par Alfred

### IMPORTANTE (autonomie / intelligence)
5. [Mem0] Memoire episodique structuree par session
   - Solution : table SQLite history/messages (comme Mem0 storage) + evenements (action, resultat, cout)
   - Fichiers : scripts/session_memory.py ; Test : reprise de contexte apres /new
6. [Mem0] Memoire procedurale (lecons reutilisables)
   - Solution : extraction PROCEDURAL a la fin de session -> top-3 recharge si contexte similaire
   - Fichiers : scripts/end_of_session.py (evolution) ; Test : lecon fact-check remontee avant un run pipeline
7. [PydanticAI] Typage et validation des outils (schemas entree/sortie)
   - Solution : generation de schemas JSON pour les scripts critiques + validation retour
   - Fichiers : scripts/tool_schemas.py ; Test : appel outil avec mauvais args -> erreur claire pre-tool

### UTILE
8. [PydanticAI] Observabilite : couts par outil et traces (OpenTelemetry)
   - Solution : log structure JSON (outil, modele, tokens, cout) par session
   - Fichiers : hooks OpenClaw + scripts/usage_tracker.py ; Test : audit hebdo des couts
9. [Composio] Tool registry + recherche d'outils
   - Solution : cataloguer les scripts existants (video, ETF, Euromillions, macro) + lookup au bootstrap
   - Fichiers : tools_registry.json ; Test : chemin correct pour chaque tache commune

### EXPERIMENTALE
10. [PydanticAI/OpenHands] Execution durable + sub-agents standardises
    - Solution : etat checkpoint JSON des taches longues (pipeline, batch) + protocole type ACP
    - Fichiers : scripts/durable_task.py ; Test : kill -9 d'un run -> reprise au checkpoint

## 5. AMELIORATIONS DEJA IMPLEMENTEES (surprises positives)
- Nudge nocturne : extraction de faits + dedup 'deja connu' deja fonctionnelle (concept Mem0 FACT_RETRIEVAL)
- Model router : fallback deepseek -> gemma deja en place (concept PydanticAI failover)
- Pipeline video : flock, anti-titre-duplique, dead man's switch (concept robustesse SWE-agent)
- Moteur memoire builtin : FTS5 + vecteurs + hybride (concept Qdrant hybride, deja en SQLite)
- Sub-agents avec rapport obligatoire (concept OpenHands standardisation)

## 6. IMPACT ESTIME
- Autonomie : +35% (retry, durable exec, tool registry)
- Intelligence : +25% (memoire hybride, procedurale, episodique)
- Memoire : +60% (dedup, TTL, recherche semantique Qdrant)
- Fiabilite : +40% (retry backoff, validation outils, observabilite)
- Cout : -15% (embeddings locaux, moins de retours API inutiles)

## 7. VEILLE CONTINUE (proposition - ATTEND ACCORD ERIC)
Script propose : scripts/monitor_ref_repos.py (check tags/commits/releases des 6 repos)
Cron propose : lundi 06:30 UTC (avant le rapport hebdo)
Rapports : missions/architecture-audit-2026-09/veille/REVIEW-YYYY-MM-DD.md
