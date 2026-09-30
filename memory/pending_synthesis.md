# Demande de Synthèse Hebdomadaire

Date: 2026-09-19

L'assistant doit analyser les logs suivants et mettre à jour MEMORY.md avec les faits saillants, décisions et leçons apprises.


--- 2026-09-13.md ---
# 2026-09-13 — Session : Carrousel TikTok Neuro-Finance (analyse + création + publication)

## Contexte
Eric envoie un lien TikTok (vm.tiktok.com/ZGdQS6p3Q) → post PHOTO carrousel de @a.dieu.la.gloire44 : « Ce que l'école aurait dû t'enseigner » (9 slides : 1 intro + 8 thèmes, chacun avec 1 livre). Stats : 1175 lectures, 20 likes, 13 saves, 0 commentaires. Compte : 237 abonnés.

## Livrables créés (terminés ✅)
1. **Analyse du post** : format carrousel photo = format rentable en reach organique TikTok (saves > likes, ratio 0.65), angle « ce que l'école n'a pas appris » = psycho-finance.
2. **8 thèmes + livres retenus** (ordre stratégique, finance en #1) :
   1. Éducation financière → L'Homme le plus riche de Babylone (Clason)
   2. Biais cognitifs → Système 1 / Système 2 (Kahneman)
   3. Décisions → Thinking in Bets (Annie Duke)
   4. Habitudes → Le Pouvoir des habitudes (Duhigg)
   5. Métacognition → Apprendre à résister (Houdé)
   6. Neuroplasticité → Mindset (Dweck)
   7. Épigénétique → Le Gène (Mukherjee)
   8. Géopolitique → Comprendre le monde (Boniface)
3. **Carrousel 9 slides** (1080×1440, PNG, Pillow) → `output/carousel_20260913/` (slides + contact_sheet.jpg)
4. **PUBLIÉ sur TikTok** via Zernio : compte tiktok majordomef/Alfred_Finance, post photo carrousel :
   https://www.tiktok.com/@majordomef/video/7684997713787669763 (publié 12:36 UTC)
   Légende (limitée 90 caractères, TikTok photo) : « L'école ne t'a jamais appris ça 🧠💸 — 8 leçons + 1 livre chacune »
   Hashtags : neurofinance, educationfinanciere, psychologie, investissement, livres, financepersonnelle
5. **Commentaire épinglé prêt** (8 liens recherche Amazon + CTA site) → `output/carousel_20260913/commentaire_epingle.txt` — à coller manuellement par Eric (l'épinglage se fait dans l'app TikTok).

## Leçons techniques (importantes)
- **TikTok photo posts** : yt-dlp ne les gère pas (« Unsupported URL »). Solution : télécharger le HTML de la page (lien court vm.tiktok.com → résolution 3xx → page /photo/...) et extraire imagePost JSON + stats (playCount, diggCount, collectCount) depuis le HTML.
- **Zernio peut publier des carrousels photo TikTok** : uploader chaque image via `client.media.upload()` puis `posts.create()` avec `media_items=[{"url":..., "type":"image"} × N]`. Fonctionne.
- **Contrainte TikTok photo via Zernio** : le `content` du post devient le TITRE du slideshow → **limité à 90 caractères**. Un content long échoue avec erreur explicite. Description complète impossible → passer par commentaire épinglé pour le CTA + liens.
- **Zernio ne peut PAS poster de commentaire public** : les méthodes comments sont inbox-only (reply_to_inbox_post, pin_inbox_comment...). Pour commenter/épingler un post : action manuelle app TikTok.
- **ASIN/ISBN introuvables ce jour** : OpenLibrary timeout, Google Books 429, DuckDuckGo/Bing vides, Amazon.fr bloque. Liens de secours = recherche Amazon `https://www.amazon.fr/s?k=...`.
- **Pas de tag Amazon Associates configuré** : AFFILIATION_DB.json ne contient que des placeholders EXAMPLE. En attente du tag d'Eric pour liens trackés (amazon.fr/dp/ASIN?tag=XXX). Affiliation réelle actuelle = Trade Republic (refnocode.trade.re/pgbqgk3f) via PEA Comparator → CTA alfredstudio.mooo.com.
- **Pièges récurrents** : (1) `\n` dans les heredocs exec/Python se fait manger → utiliser chr(10) ou éviter les échappements ; (2) Pillow `d.rectangle([x1,y1],[x2,y2])` → erreur « multiple values for fill » → utiliser tuple unique 4 valeurs `(x0,y0,x1,y1)`.

## En attente / prochaines actions
- [ ] Tag Amazon Associates d'Eric → régénérer les 8 liens affiliés + re-collage commentaire
- [ ] Eric colle/épingle le commentaire préparé (30s dans l'app TikTok)
- [ ] (Optionnel) mettre alfredstudio.mooo.com en bio TikTok
## Décision (12:58 UTC) — Affiliation livres AMAZON ABANDONNÉE pour l'instant
- Eric : « On laisse tomber l'affiliation des livres pour l'instant, peut-être plus tard ».
- Le commentaire épinglé préparé (commentaire_epingle.txt) reste VALIDE tel quel : liens de recherche Amazon sans tag, cliquables → Eric peut l'épingler sans modification.
- Pas de création de compte Amazon Associates pour l'instant. Si réactivé un jour : tag attendu d'Eric → régénérer liens amazon.fr/dp/ASIN?tag=XXX.
- Monétisation principale inchangée : Trade Republic (refcode) via alfredstudio.mooo.com (bio TikTok + site).


--- 2026-09-18.md ---

## Audit 20 points PEA Comparator (18/09) — tout corrigé
- Audit : 13/20 initial -> 20/20 après corrections (leçons TikTok @buildwithmathias appliquées).
- Corrections : CGU liée au footer (index+guide), gzip_types nginx décommentés (JS/CSS -50%), banner orphelin retiré, formulaire newsletter + honeypot + consent RGPD + bannière cookies, contraste --text-tertiary foncé (#8a9bb0->#64748b), cache-bust CSS bumpé v=1789743470.
- Root cause newsletter (IMPORTANT) : le proxy newsletter-proxy/server.js appelait /ghost/api/admin/members/ SANS prefixe /blog ni headers X-Forwarded-* -> Ghost 404 silencieux (success factice). Fix : path /blog/ghost/api/admin/members/ + headers Host/X-Forwarded-Proto/Host/Prefix + readApiKey accepte STAFF|INTEGRATION (cle GHOST_ADMIN_API_KEY_STAFF utilisee). Valide E2E : inscription creee puis membre test nettoye (204).
- Backups : /tmp/audit_fix_backup/ (index.html, style.css, nginx.conf, server.js, banner).
## Checklist réutilisable « 20 points avant lancement site » (source : TikTok @buildwithmathias, extraite par OCR 18/09)
Source vidéo : vm.tiktok.com/ZGdQu4ape/ (38,7s) — checklist écran extraite par OCR (39 frames + crops ciblés).
Les 20 points : 1. Page RGPD — 2. Page CGU/mentions légales — 3. API hors front-end — 4. Force HTTPS — 5. Bannière cookies — 6. Meta title — 7. Image réseaux sociaux (OG) — 8. Favicon — 9. Sitemap + robots.txt — 10. Textes images (alt) — 11. Compresser les images — 12. Vitesse des pages — 13. Contraste — 14. Site responsive — 15. Page 404 personnalisée — 16. Répare les liens cassés — 17. Valide les formulaires — 18. Anti-spam — 19. Outil analytics — 20. Un seul CTA clair.
Réutilisable pour tout futur site (PEA Comparator, blog Ghost, landing pages). L'OCR de vidéos TikTok = pattern récurrent chez Eric (2e fois : « une fille IA » 16/09 puis celle-ci).

## Méthode extraction prompts TikTok (validée 2×)
1. Résoudre vm.tiktok.com via yt-dlp → URL complète + métadonnées
2. Télécharger la vidéo + extraire frames 1fps (ffmpeg)
3. OCR tesseract (fra+eng) sur toutes les frames
4. Items masqués par horodatage → crop chirurgical ciblé (localiser via TSV bbox puis recadrer) — l'item 15 était masqué par l'horodatage, retrouvé par crop de la bande y≈865-985 sur les frames 26-36

## Fix newsletter mis à jour (18/09 après-midi)
- Proxy : newsletter-proxy/server.js (service systemd alfred-newsletter-proxy, port 3001, nginx /api/newsletter → 3001)
- Lire et NE PAS reverter : readApiKey accepte STAFF|INTEGRATION ; path /blog/ghost/api/admin/members/ ; headers Host + X-Forwarded-Proto/Host/Prefix ; success seulement si réponse Ghost 2xx (messages « Inscription réussie » / « Merci ! »)
- Test E2E du jour : inscription créée et membre test nettoyé (204) — ne pas recréer de membre test sans le nettoyer
## Refonte esthétique PEA Comparator (18/09 après-midi) — LIVRÉE commit 997d508
- Mission Eric (16:17) : refonte esthétique UNIQUEMENT (HTML/CSS/assets), zéro logique métier, commit clair.
- **Livré** : commit **997d508** « design: identité unique, grille outils, CSS tokens » (17 fichiers, +2493/−1064), repo = workspace git (web/pea-comparator, origin GitHub pea-comparator). NOTA : /var/www/html n'est PAS un repo git — le site déployé est synchronisé vers web/pea-comparator pour le versioning.
- **Identité figée appliquée** : nom « Alfred » (plus de 🎩, plus de « Alfred AI »), 1 accent #0F766E (teal profond), neutres fond #F7F6F3 / encre #12141A / secondaire #5C6570 / cartes #FFFFFF / bordure #E6E1D8 ; vert gain / rouge perte seulement dans les data ; Inter 400-700 (pas de 900) + JetBrains Mono + tabular-nums pour chiffres/ISIN/TER.
- **Changements clés** : style.css réécrit de A à Z (@import en tête, :root unique, media queries TOUTES fermées — avant : 5 non fermées/déséquilibre 603 vs 598), grille outils ≥2 colonnes dès 768px, skeleton shimmer, header sans lien d'affiliation ni 📺, FAQ convertie en accordéons natifs `<details>`, CTA TR unique bas de page (bouton blanc sur bandeau teal), 0 emoji chrome UI, favicon.svg + alfred-mark.svg (323 o) + og-image.jpg 1200×630 nouvelle marque, pea-comparator.xyz purgé (guide, 404), app.min.js NON touché (simulateurs intacts, vérifié).
- Blog : public servi par Ghost (thème à part) ; articles statiques /var/www/html/blog/*.html nettoyés et alignés (partagent style.css).
- Backups : /tmp/pea_design_backup_20260918/ (+ /tmp/pea_redesign_backup/).

## ⚠️ LEÇON TECHNIQUE CRITIQUE (outil exec/tool_search_code) — cause de ~30 appels ratés ce jour
- **Ne JAMAIS mettre de backslash seul dans les commandes** passées à tool_search_code : le parseur JS interprète `\x{...}`, `\d`, `\b` comme séquences d'échappement → erreurs « Invalid or unexpected token » / « Unexpected end of input » AVANT même l'exécution shell.
- **Fiables** : commandes simples sur 1 ligne ; heredocs COURTS `cat > /tmp/x.py <<'FIXEOF'` (contenu sans backslash ni emoji littéral) ; `printf '%b' "lignes\navec\\néchappés" | sudo tee fichier` ; `python3 -c 'code sans guillemets doubles'` (quotes simples bash + doubles quotes python dedans, OK).
- Pour détecter emojis/unicode : utiliser des plages numériques Python `ord(c)` (0x1F000 <= ord(c) <= 0x1FAFF) plutôt que regex `\x{...}`.
- `sudo python3` nécessaire pour écrire dans /var/www/html (fichiers root/www-data) ; backup AVANT toute modif.
- Les gros heredocs (>~1,5-2 Ko) et les `\n` dans les strings python à l'intérieur de printf échouent : préférer chr(10) ou découper.
## Refonte PEA Comparator — livraison finale + push GitHub + thème Ghost (18/09 soir)
- **Livré à Eric :** refonte esthétique complète commitée (`997d508` local) ET **pushée proprement** sur GitHub : remote `main` = `6976f4c` (« design: identité unique, grille outils, CSS tokens », 17 fichiers, +2493/−1064). Vérifié par `git ls-remote origin main`.
- **⚠️ Découverte sécurité majeure :** le push direct des 13 commits locaux jamais poussés était **BLOQUÉ par le secret scanning GitHub** : un **token Telegram du bot** (format `8725265760:AAH...`) avait été committé par accident dans `memory/archive/2026-04-15-1425.md` (introduit dans le commit 4b65a71, présent dans 5+ commits). **Jamais poussé → rien n'a fuité** (GitHub a refusé).
- **Solution adoptée :** `git worktree add` basé sur `origin/main` (7a6e906) → copie des fichiers web à jour → commit propre `6976f4c` → push fast-forward. Le token reste SEULEMENT dans l'historique git local. Eric informé : recommander **régénérer le token** + purger l'historique local plus tard (il a demandé si je le fais — pas encore tranché).
- Les 13 commits locaux contiennent aussi node_modules (136 entrées), mp4 25 Mo, .git = 1,9 Go → ne JAMAIS pousser tel quel ; nettoyage = chantier futur.

## Thème Ghost (point 8 mission) — fait
- Blog public servi par Ghost (conteneur ghost-blog, MySQL `ghost` dans ghost-mysql, thème actif « source »). La « code injection » Ghost (settings `codeinjection_head/foot`) contenait l'ANCIENNE identité or/bleu `#d4a843`, `#0f172a` → **remplacée par les tokens Alfred** (`#0F766E` teal, fond ivoire...) — vérifié live : 29 occurrences `0F766E`, 0 `d4a843`. Blog redémarré (docker restart ghost-blog) pour prise en compte.
- **Encoding corrigé :** mojibake `libertÃ©`/`sÃ©lection` (double-encodage cp1252→utf8) réparé sur tous les posts PUBLIÉS (title/html/mobiledoc/lexical). Reste 1 brouillon non publié (6a3d9b83 « Mes 3 ETF Préférés ») avec résidus — invisible au public, correct.
- Backup DB Ghost : `/tmp/ghost_backup_20260918.sql`. Backup site : `/tmp/pea_design_backup_20260918/`.

## LEÇONS TECHNIQUES (supplément au flush de 22:24)
- **printf '%b' interprète les `%`** : pour du SQL avec `LIKE '%...%'` dans un script python généré via printf, utiliser `chr(39)` pour les quotes et **éviter les `%`** (préférer `REGEXP`/`INSTR` ou `chr(37)`) sinon les requêtes partent fausses (les LIKE ont donné des comptages corrompus ce jour-là, ex. `%25C3%` au lieu de `%C3%`).
- Les **backticks MySQL (`key`)** dans du SQL passé par commande shell → erreurs « key: command not found » : générer via fichier .sql ou `chr(96)` dans python.
- MySQL Ghost : mot réservé `key` → toujours backtick ; ajouter `--default-character-set=utf8mb4` pour lire les accents.
- Requêtes d'UPDATE sur colonnes inexistantes (meta_title etc.) → erreur 1054 → vérifier `SHOW COLUMNS` d'abord (posts Ghost = title, html, plaintext, custom_excerpt, mobiledoc, lexical, codeinjection_*).
## HOTFIX 22:24 — Overlay Score Alfred bloquant (bug introduit par MA refonte)
- Eric signale (capture) : page bloque sur l'overlay blanc « Score Alfred - Methodologie », impossible de fermer.
- Root cause : mon style.css reecrit avait `.modal-overlay{display:flex}` INCONDITIONNEL ; la mecanique JS (scoreModal/leadModal/etfModal) repose sur `.modal-overlay.active{display:flex}` + display:none par defaut (comportement d'origine). Resultat : tous les overlays visibles en permanence, la croix ne fait rien (elle retire .active qui ne controle plus rien). En plus j'avais vide les boutons (plus de ✕).
- Fix : display:none par defaut + .modal-overlay.active{display:flex} + .modal-overlay.active .modal{transform:translateY(0)} ; croix ✕ restaurees (3 boutons index.html) ; cache-bust CSS bump style.css?v=1789744101 (index + top-etf).
- Verifie live : 200 OK, CSS servi contient .modal-overlay.active{display:flex}, v=1789744101 servi.
- Commit 7445f87 + push GitHub (remote main = 7445f87, worktree /tmp/wt-fix retire).
- LECON : quand on reecrit un CSS, verifier les composants a ETAT (modal via classe .active) ; toujours garder la mecanique display:none + etat .active.{display:flex}, et le contenu des boutons (croix ✕).
## HOTFIX 22:24 — Overlay « Score Alfred » bloquant (bug introduit par la refonte du jour)
- **Symptôme (signalé par Eric ~22:24, avec capture d'écran) :** page « Score Alfred — Méthodologie » recouverte d'un overlay/modal blanc impossible à fermer (« je tombe sur cette page et je ne peux pas en sortir »).
- **Root cause :** mon `style.css` réécrit (refonte 16:17) avait `.modal-overlay{...display:flex...}` **inconditionnel**, alors que la mécanique JS (modals `etfModal`, `leadModal`, `scoreModal` + classe `active`) n'affiche le modal que via **`.modal-overlay.active{display:flex}`** + `display:none` par défaut (comportement du CSS d'avant, présent dans `/tmp/pea_design_backup_20260918/style.css`). Résultat : les 3 overlays affichés en permanence dès l'arrivée sur la page, et la croix (qui retire `.active`) ne faisait rien.
- **Deuxième défaut (même racine) :** les boutons de fermeture avaient été vidés (`<button ...></button>` au lieu de `>✕</button>`) → aucune croix visible.
- **Fix appliqué (prod live /var/www/html) :** `display:none` par défaut + `.modal-overlay.active{display:flex}` + `.modal-overlay.active .modal{transform:translateY(0)}` ; croix ✕ restaurées (3 boutons dans index.html) ; **cache-bust CSS bumpé `style.css?v=1789744101`** (index.html + top-etf.html) pour forcer le rechargement navigateur.
- **Vérifié live :** HTTP 200 ; CSS servi contient `.modal-overlay.active{display:flex}` ; cache-bust `v=1789744101` servi. rapporté à Eric (Ctrl+Shift+R).
- **Push GitHub :** fix commité `7445f87` et poussé (remote `main` = `7445f87`) — via worktree propre `/tmp/wt-fix` (retiré après push), même méthode que `6976f4c` (l'historique local reste non poussable : token Telegram dans `memory/archive/2026-04-15-1425.md`, secret scanning GitHub).
- **LEÇON CRITIQUE :** ne jamais changer la mécanique d'affichage des composants à état (modals/accordéons/overlays pilotés par classe `.active` ou JS) lors d'un restyle ; après réécriture CSS, vérifier les états par défaut (`display:none`) ET la présence des icônes/éléments d'action (croix ✕). Le CSS d'avant est la référence : `/tmp/pea_design_backup_20260918/`.
