# Analyse des hooks - chaine Alfred AI

Perimetre : 44 videos publiees du 24/07/2026 au 27/09/2026 (43 + celle du jour).
Source hooks : 32 scripts JSON conserves dans ~/output/script-PROD_*.json. 12 hooks manquants (scripts purges, telechargement yt-dlp bloque par YouTube).
Source performance : API YouTube Data v3 (vues, likes, commentaires, duree, date de publication) + state/yt_stats_history.json (44 passages) pour la vitesse de vues.

## Limite de methode (a lire avant de conclure)
- Aucune donnee de retention disponible : le token OAuth n'a pas le scope yt-analytics.readonly. On ne mesure donc PAS le taux de decrochage reel des 3 premieres secondes.
- Le proxy utilise est le nombre de vues : faible (0 a 147), n=32, et 3 valeurs extremes portent l'essentiel de la moyenne. Aucune causalite solide, seulement des structures et des tendances.

## 1. Le constat structurel : le hook n'est pas un hook
- Duree du 1er segment : de 14,2 s a 23,1 s, moyenne 17,7 s. 32/32 videos depassent 12 s.
- Longueur de la 1ere phrase : 5 a 30 mots, moyenne 12 mots, soit environ 4,6 s avant la fin de la premiere idee.
- Consequence : le spectateur doit ecouter un paragraphe entier avant de savoir de quoi parle la video. Sur Shorts, la decision se prend entre 1,5 s et 3 s.
- Duree totale : 39 videos sur 44 depassent 60 s (66 s a 81 s). Ce n'est pas bloquant depuis 2024 (Shorts jusqu'a 3 min) mais cela aggrave le poids du premier segment.

## 2. Types d'ouverture et resultats
- question seule : n=22, vues moyennes 5.2, mediane 3, max 22
- hook indisponible : n=12, vues moyennes 21.7, mediane 6, max 147
- constat 3e personne : n=7, vues moyennes 32.1, mediane 5, max 128
- affirmation vous : n=2, vues moyennes 3.0, mediane 4, max 4
- nominal neutre : n=1, vues moyennes 4.0, mediane 4, max 4

Lecture : la question seule est le reflexe dominant (22/32 = 69 pour cent des hooks) et c'est la classe la plus plate : mediane 3 vues, plafond 22. Les 2 seules videos au-dessus de 70 vues partagent une autre structure : un constat a la 3e personne suivi immediatement d'une bascule sur vous (Vous pensez X, mais Y).

## 3. Le score interne de hook ne discrimine rien
- Distribution de state/auto-reflection/hook_history.json : 7.0 pour 25 videos sur 50, 8.0 pour 19, 9.0 pour 1. Quatre valeurs possibles pour 50 mesures.
- Correlation inverse avec les vues : score 7.0 -> 20,8 vues de moyenne ; score 8.0 -> 11,4. Le score note mieux ce qui marche moins bien.
- Conclusion : ce score doit etre ignore comme signal de decision (il vient de l'ancien bug whisper, corrige le 30/07, mais aucune recalibration n'a ete faite).

## 4. Le test A/B est mort depuis le 30/07
- ab_001 (chiffre choc contre question) : status running, videos_a = 0, videos_b = 0, results vide. Aucune video n'a jamais ete assignee.
- Observation quand meme disponible sur les donnees reelles : pattern chiffre_choc n=6 -> 1,8 vue de moyenne ; pattern contraire n=4 -> 39,8.

## 5. Tableau des 44 videos

| Date | Vues | Duree | Pattern interne | Ouverture | 1ere phrase | Hook (s) | Verdict |
|---|---|---|---|---|---|---|---|
| 07-24T16:15 | 6 | 66s | - | hook indisponible | - | - | faible |
| 07-27T16:07 | 4 | 49s | - | hook indisponible | - | - | faible |
| 07-28T16:04 | 2 | 48s | - | hook indisponible | - | - | ECHEC |
| 07-28T16:30 | 3 | 60s | - | hook indisponible | - | - | faible |
| 07-29T18:23 | 6 | 66s | - | hook indisponible | - | - | faible |
| 07-30T16:06 | 1 | 44s | - | hook indisponible | - | - | ECHEC |
| 08-01T21:13 | 6 | 57s | - | hook indisponible | - | - | faible |
| 08-11T16:44 | 21 | 62s | montage_rapide | hook indisponible | - | - | correct |
| 08-22T21:24 | 147 | 80s | montage_rapide | hook indisponible | - | - | MODELE |
| 08-23T06:27 | 30 | 70s | montage_rapide | hook indisponible | - | - | correct |
| 08-23T19:28 | 33 | 70s | montage_rapide | hook indisponible | - | - | correct |
| 08-25T16:41 | 1 | 69s | montage_rapide | question seule | Pourquoi certains d'entre vous paniquent à la moindre baisse alors que d'autres restent totalem | 16.2 | ECHEC |
| 08-25T20:47 | 0 | 69s | montage_rapide | question seule | Pourquoi certains d'entre vous paniquent à la moindre baisse alors que d'autres restent totalem | 16.2 | ECHEC |
| 08-26T16:20 | 5 | 73s | montage_rapide | constat 3e personne | Une grande partie des conseils diffusés sur les réseaux sociaux peut négliger la gestion du ris | 19.6 | faible |
| 08-27T16:11 | 2 | 68s | montage_rapide | question seule | Pourquoi ouvrez-vous votre application bancaire toutes les heures ? | 15.0 | ECHEC |
| 08-28T16:35 | 1 | 69s | montage_rapide | hook indisponible | - | - | ECHEC |
| 08-29T16:16 | 0 | 70s | chiffre_choc | question seule | Pourquoi achetez-vous parfois au sommet ? | 18.5 | ECHEC |
| 08-30T04:15 | 1 | 69s | montage_rapide | constat 3e personne | De nombreux particuliers échouent parce qu'ils cherchent un gain immédiat. | 16.9 | ECHEC |
| 08-31T04:26 | 0 | 66s | montage_rapide | question seule | Pourquoi pensez-vous sincèrement pouvoir prédire le point bas des marchés financiers ? | 15.8 | ECHEC |
| 09-01T04:15 | 0 | 69s | montage_rapide | question seule | Pourquoi ignorez-vous systématiquement le coût réel de vos placements ? | 17.7 | ECHEC |
| 09-02T04:13 | 4 | 77s | montage_rapide | affirmation vous | Votre cerveau vous ment sur les marchés financiers. | 15.4 | faible |
| 09-03T05:13 | 0 | 72s | montage_rapide | question seule | Croyez-vous vraiment que placer votre capital sur les marchés financiers est gratuit ? | 18.5 | ECHEC |
| 09-04T04:24 | 4 | 74s | montage_rapide | nominal neutre | La part des gains prélevée par le fisc et les prélèvements sociaux dépend de la durée du contra | 23.1 | faible |
| 09-05T05:00 | 2 | 76s | montage_rapide | question seule | Pourquoi votre cerveau vous ment-il sur chaque décision financière ? | 17.7 | ECHEC |
| 09-06T04:17 | 3 | 78s | montage_rapide | question seule | Pourquoi une large majorité des traders amateurs enregistrent-ils des pertes ? | 19.6 | faible |
| 09-07T04:14 | 2 | 68s | montage_rapide | question seule | Et si votre obsession pour l'activité était précisément ce qui détruit votre patrimoine ? | 17.3 | ECHEC |
| 09-08T04:12 | 0 | 69s | chiffre_choc | question seule | Vous consultez vos positions 40 fois par jour ? | 20.0 | ECHEC |
| 09-09T04:17 | 22 | 75s | montage_rapide | question seule | Pourquoi la poursuite acharnée du capital peut-elle mener à la drawdown ? | 16.9 | correct |
| 09-10T17:32 | 8 | 65s | montage_rapide | question seule | Et si votre plus gros ennemi était votre propre écran ? | 15.4 | faible |
| 09-11T04:24 | 19 | 81s | montage_rapide | question seule | Croyez-vous vraiment maîtriser vos investissements ? | 20.0 | correct |
| 09-12T05:33 | 76 | 63s | montage_rapide | constat 3e personne | De nombreux particuliers suivent aveuglément des conseils collectifs avant de subir une drawdow | 16.5 | MODELE |
| 09-13T04:15 | 12 | 68s | montage_rapide | question seule | Pourquoi agir sans cesse ? | 16.9 | correct |
| 09-14T04:26 | 9 | 73s | montage_rapide | constat 3e personne | Une grande partie de vos décisions financières peut être influencée par vos émotions plutôt que | 20.4 | faible |
| 09-15T05:11 | 12 | 71s | contraire | question seule | Et si votre pire ennemi sur les marchés financiers, c'était votre propre cerveau ? | 19.2 | correct |
| 09-17T04:17 | 4 | 69s | montage_rapide | question seule | Pourquoi votre capital chute-t-il quand les actualités sont excellentes ? | 16.2 | faible |
| 09-18T04:23 | 128 | 76s | contraire | constat 3e personne | De nombreux investisseurs surévaluent leur capacité à prédire les marchés. | 20.0 | MODELE |
| 09-19T04:09 | 11 | 75s | contraire | question seule | Et si votre plus grande force devenait votre pire ennemi ? | 19.2 | correct |
| 09-21T05:48 | 3 | 68s | - | question seule | Pourquoi les soldes en bourse sont-ils le piège préféré des investisseurs ? | 16.2 | faible |
| 09-23T06:53 | 0 | 75s | chiffre_choc | question seule | Pourquoi cherchez-vous absolument à ne jamais faire d'erreur ? | 22.3 | ECHEC |
| 09-24T04:13 | 3 | 68s | chiffre_choc | constat 3e personne | De nombreux choix financiers subissent des biais émotionnels. | 14.2 | faible |
| 09-24T19:28 | 3 | 70s | chiffre_choc | constat 3e personne | Imaginons que de nombreuses décisions aléatoires puissent aboutir à un gain. | 16.2 | faible |
| 09-25T04:11 | 8 | 74s | contraire | question seule | Et si votre meilleure décision financière consistait à ne rien faire ? | 14.6 | faible |
| 09-26T05:17 | 5 | 67s | chiffre_choc | question seule | Si vous placez 1000€ par mois durant 10 ans, croyez-vous vraiment qu'une répartition précise sa | 17.7 | faible |
| 09-27T04:09 | 2 | 71s | montage_rapide | affirmation vous | Votre PEA contient peut-être un produit que vous ne comprenez pas. | 16.5 | ECHEC |

## 6. Le hook qui a marche (a copier)

Deux videos depassent 70 vues et partagent exactement la meme architecture :

1. Le paradoxe de l'intelligence financiere (128 vues) : De nombreux investisseurs surevaluent leur capacite a predire les marches. Vous pensez que votre intelligence vous protege ? C'est une erreur fatale.
2. Le danger des salons de discussion (76 vues) : De nombreux particuliers suivent aveuglement des conseils collectifs avant de subir une drawdown massive. Vous pensez etre entoure d'experts, mais vous etes simplement dans une chambre d'echo.

Structure : groupe + comportement observable (constat sec, pas de question), puis bascule sur vous avec un retournement (Vous pensez X, mais Y). Cherchez aussi la video a 147 vues (hook indisponible) : c'est la seule autre exception.

## 7. Reecritures proposees (12 echecs)

Regle appliquee : 2 phrases maximum, 16 mots maximum au total (environ 6 s), un constat verifiable d'abord, la bascule sur vous ensuite. Zero question en ouverture seule, zero jargon anglais.

- Le secret des investisseurs qui dorment sur leurs deux oreilles (1 vues)
  - avant : Pourquoi certains d'entre vous paniquent à la moindre baisse alors que d'autres restent totalement sereins ?
  - apres : Ils ne surveillent pas leurs positions. Ils ont automatisé. C'est tout.
- Le secret des investisseurs qui dorment sur leurs deux oreilles (0 vues)
  - avant : Pourquoi certains d'entre vous paniquent à la moindre baisse alors que d'autres restent totalement sereins ?
  - apres : Ils ne surveillent pas leurs positions. Ils ont automatisé. C'est tout.
- Vérifier vos comptes 20 fois par jour (2 vues)
  - avant : Pourquoi ouvrez-vous votre application bancaire toutes les heures ?
  - apres : Votre appli bancaire est une machine à sous. Vous tirez la poignée 20 fois par jour.
- Pourquoi vous achetez au plus haut et vendez au plus bas (0 vues)
  - avant : Pourquoi achetez-vous parfois au sommet ?
  - apres : En 2008, le S&P 500 a perdu 38 %. Les volumes avaient explosé juste avant.
- La science du rendement (1 vues)
  - avant : De nombreux particuliers échouent parce qu'ils cherchent un gain immédiat.
  - apres : Le rendement n'est pas une science. C'est une durée. Et vous la raccourcissez.
- Le piège du prix bas (0 vues)
  - avant : Pourquoi pensez-vous sincèrement pouvoir prédire le point bas des marchés financiers ?
  - apres : Attendre la baisse est une décision. Elle a un prix. Personne ne vous le facture.
- Le piège invisible des frais (0 vues)
  - avant : Pourquoi ignorez-vous systématiquement le coût réel de vos placements ?
  - apres : 0,5 % de frais par an. Sur 30 ans, ça efface 14 % de votre capital final.
- Le coût caché des marchés financiers (0 vues)
  - avant : Croyez-vous vraiment que placer votre capital sur les marchés financiers est gratuit ?
  - apres : Le vrai coût de la bourse n'est pas en euros. Il est en décisions ratées.
- Votre intuition financière est votre pire ennemie (2 vues)
  - avant : Pourquoi votre cerveau vous ment-il sur chaque décision financière ?
  - apres : Quand le cours chute, votre corps veut vendre. Ce réflexe coûte plus cher que la chute.
- L'inaction : Votre meilleur actif (2 vues)
  - avant : Et si votre obsession pour l'activité était précisément ce qui détruit votre patrimoine ?
  - apres : Un compte oublié bat souvent un compte surveillé. Ce n'est pas une blague.
- Pourquoi surveiller les cours vous appauvrit (0 vues)
  - avant : Vous consultez vos positions 40 fois par jour ?
  - apres : 66 000 comptes suivis : les plus actifs ont gagné le moins. Vous consultez les vôtres combien de fois par jour ?
- L'erreur de l'évitement (0 vues)
  - avant : Pourquoi cherchez-vous absolument à ne jamais faire d'erreur ?
  - apres : Ne jamais perdre est un objectif. C'est aussi la meilleure façon de ne rien gagner.
- Les ETF synthétiques vont-ils sortir de votre PEA ? (2 vues)
  - avant : Votre PEA contient peut-être un produit que vous ne comprenez pas.
  - apres : Votre ETF ne détient peut-être pas les actions qu'il promet. Vérifiez la réplication.

## 8. Correctifs pipeline proposes

1. Segment 1 : passer de 38-55 mots a 16-24 mots, 2 phrases maximum, la fin de la premiere phrase avant 3 s. C'est le correctif a plus fort effet attendu : il agit sur 100 pour cent des videos.
2. Interdire la question en ouverture seule. Autoriser la question uniquement en 2e phrase, apres un constat.
3. Interdire l'ouverture generique (De nombreux, Une grande partie, La plupart) SAUF si elle est immediatement suivie de Vous pensez ... mais ... (la seule structure associee aux vues elevees).
4. Interdire le jargon anglophone dans le premier segment (drawdown, etc.). Attention : les 2 meilleures videos l'emploient, donc ce point est a tester, pas a trancher.
5. Recalibrer ou supprimer le hook_score interne : il ne distingue plus rien (4 valeurs pour 50 videos, correlation inverse).
6. Relancer le test A/B avec une vraie assignation : A = question seule, B = constat + bascule vous, mesure a J+2 sur les vues (et sur la retention des que le scope analytics est disponible).
7. Instrumentation prioritaire : reautoriser l'OAuth avec le scope yt-analytics.readonly pour obtenir averageViewPercentage. Sans cela, on continuera a juger des hooks avec un proxy de vues a 3 valeurs extremes.

Points d'attention annexes
- Les 12 hooks manquants ne sont pas analysables : scripts purges avant le 25/08 et telechargement bloque (Sign in to confirm you are not a bot). Si on veut les couvrir un jour, il faut des cookies YouTube.
- Horaires de publication constates en septembre : 04h09 a 06h53 UTC (06h00-09h00 Paris), alors que le cahier des charges indique 16h00 UTC. A verifier separement.

## 9. Correctifs appliques (27/09/2026)

Fichier modifie : pipeline/pipeline_orchestrator.py (1577 lignes apres patch). Backups horodates : .bak_hook_court_20260927_0908, .bak_hook_bench_20260927_0912, .bak_hook_nonbloquant_20260927_0913, .bak_hook_calibrage_20260927_0915. Compilation Python validee apres chaque etape.

Changements :
- Regle de longueur : segment 1 (accroche) = 16 a 24 mots, segments 2 a 4 = 36 a 55 mots, total 124 a 189 mots (avant : 36-55 par segment, 160-195 au total).
- Structure imposee : phrase 1 = constat sec sans question (10 a 12 mots, pose des les 3 premieres secondes), phrase 2 = bascule sur le spectateur du type Vous pensez X, mais Y. Question interdite en ouverture. Le constat a la 3e personne n est autorise que s il est immediatement suivi du retournement sur vous.
- Nouvelles fonctions : count_words, word_counts_ok, hook_structure_issues. Le nombre de mots reste bloquant. La structure de l accroche est bloquante sur les 2 premieres tentatives, puis simple avertissement : une video rejetee est un revenu perdu, le pipeline ne doit pas mourir pour un hook imparfait.
- Le prompt de correction apres fact-check ne peut plus rallonger l accroche.

Calibrage corrige par le benchmark :
- Mon premier seuil (premiere phrase de 10 mots maximum) rejetait la 2e meilleure video de la chaine (14 mots, 76 vues). Seuil releve a 14 mots ; l objectif demande au LLM reste 10 a 12.
- Le jargon anglophone a ete retire des criteres bloquants pour la meme raison (les 2 meilleures videos emploient drawdown). Il reste deconseille dans le prompt.

Preuves :
- 3 generations reelles (deepseek-v4.1-flash) : 20/48/47/44, 21/51/53/54, 23/46/49/38 mots, soit 3/3 conformes, structure 3/3 OK. Exemple produit : Les frais de gestion paraissent minuscules sur un releve. Vous pensez les controler, mais ils rongent votre capital chaque jour.
- Benchmark sur les 32 accroches historiques : 32/32 rejetees telles quelles (elles durent toutes 14 a 23 secondes, c est le but). Sur leurs 2 premieres phrases seulement : 6/32 passent, dont les 2 meilleures videos (128 et 76 vues). La regle conserve donc la structure gagnante au lieu de la bannir. Les 22 ouvertures par question echouent : comportement voulu.

Non fait, en attente de decision :
- Reautoriser OAuth avec le scope yt-analytics.readonly pour mesurer la vraie retention.
- Relancer le test A/B avec assignation reelle (ab_001 mort depuis le 30/07, 0 video assignee).
- Recalibrer ou supprimer le hook_score interne (4 valeurs pour 50 videos, correlation inverse avec les vues).


## 10. La vraie mesure est arrivee : retention (27/09, apres OAuth analytics)

OAuth reautorise avec le scope yt-analytics.readonly (token minimal 4 scopes, pas de Gmail/AdSense). Scripts : skills/youtube_upload/retention_report.py (donnees), tmp_hooks/ret_join.py et ret_stat.py (croisements). Sorties : state/retention.json (34 videos, 90 j), state/retention_joined.json.

### Chiffres de la chaine (90 jours, 34 videos, pondere par les vues)
- 593 vues, mediane 5 vues par video.
- **35,7 % de la video vue en moyenne**, soit **25,6 s** regardees.
- 42 % des videos perdent le spectateur AVANT 15 s (dont 18 % avant 5 s). Seules 32 % depassent 40 s.

### Ce qui invalide une partie de l'analyse du matin
- **Le danger des salons de discussion (76 vues) : 3 secondes vues, 5 % de retention.** Le spectateur part avant meme d'entendre l'argument.
- **Le paradoxe de l'intelligence financiere (128 vues) : 14 s, 18,9 %.**
- Ce sont les DEUX videos dont j'avais fait le "modele de hook gagnant" ce matin (constat 3e personne + bascule Vous pensez X, mais Y). Sur les vues elles gagnent ; sur l'attention elles sont parmi les pires de la chaine. Le modele a ete construit sur un proxy (les vues), pas sur l'attention reelle.
- A l'inverse, les videos qui retiennent : Le secret bancaire sur vos placements (30 vues, 75 s REGARDEES pour 70 s de video = 108 %, relectures), Moins vous regardez vos actions (108,6 %), La meilleure strategie pourrait etre de ne rien faire (12 vues, 66 %), Pour etre riche, arretez de vouloir etre riche (22 vues, 51,8 %).

### Correlations (n=22)
- vues <-> %vu : **-0,275** (partiellement mecanique : plus de portee = audience plus froide).
- vues <-> duree vue : -0,266.
- nombre de mots de la 1re phrase <-> %vu : **+0,063** (rien).

### Question vs affirmation sur le sous-echantillon fiable (>= 10 vues, n=7)
- 1re phrase = question : n=5, %vu moyen **37,7**, mediane 35,2 (min 6,1 / max 66,0).
- 1re phrase = affirmation : n=2, %vu moyen **12,0** (5,0 et 18,9).
- **Conclusion : l'interdiction des questions en ouverture, ajoutee le matin meme, n'est PAS soutenue par les donnees.** Elle doit etre retiree (n=7 reste faible, mais rien ne la justifie).

### Decisions qui decoulent
1. Conserver l'accroche courte (16-24 mots) : elle ne change pas la retention (corr. 0,06) mais elle sert les 42 % qui partent entre 5 et 15 s.
2. **Retirer l'interdiction de la question en ouverture** : laisser les deux formes coexister (question / constat + bascule) et laisser le test A/B trancher.
3. **Le test A/B doit se mesurer sur la retention, plus sur les vues** : ab_001 etait mort depuis le 30/07 et mal concu.
4. Ne pas durcir d'autres regles sur n=7 : collecter 2 a 3 semaines de retention avant toute generalisation.


## 11. Point 2 applique : test A/B reel, mesure sur la retention (27/09)

### Ce qui a change dans pipeline/pipeline_orchestrator.py (backup .bak_ab_retention_20260927_1046, compile OK, 81296 octets)
- **Interdiction de la question RETIREE.** Les deux formes d'ouverture sont autorisees et s'affrontent : variante A = question directe, variante B = constat sec puis bascule sur vous.
- **Assignation reelle** : pick_hook_variant() alterne A/B de facon deterministe par jour (26/09=B, 27/09=A, 28/09=B, 29/09=A). La variante est imposee au LLM dans le prompt (VARIANTE IMPOSEE AUJOURD HUI).
- **Journalisation** : record_ab_assignment() ecrit chaque affectation (date, variante, titre, word_counts) dans state/auto-reflection/ab-testing.json. C'est le trou corrige : ab_001 etait 'running' depuis le 30/07 avec **0 video assignee**.
- hook_structure_issues(segments, variant) verifie desormais la conformite a la variante imposee (A : 1re phrase = question ; B : 1re phrase = constat + presence de vous/votre/vos). La structure ne bloque toujours que les 2 premieres tentatives.

### Tests passes (preuve, pas promesse)
- Alternance : 26/09 -> B, 27/09 -> A, 28/09 -> B, 29/09 -> A.
- 6 cas de validation : question en variante A -> OK ; constat en variante A -> REJET ; constat + bascule en variante B -> OK ; question en variante B -> REJET ; **accroche de la video a 3 s de retention -> REJET** (pas de bascule sur vous + constat a la 3e personne sans retournement) ; accroche neutre conforme -> OK.
- Journalisation testee en dossier temporaire : videos_a=1, videos_b=1, metric enregistree.

### Mesure : scripts/ab_retention.py (nouveau)
- Metrique : **averageViewPercentage** (retention YouTube Analytics 90 j), plus jamais les vues.
- Sortie : state/ab_retention.json + bloc results dans state/auto-reflection/ab-testing.json.
- Seuils de decision : ecart >= 5 points de retention ET >= 5 videos par bras, sinon NON CONCLUANT.
- **Baseline retrospective (n=22 accroches connues, dont 7 >= 10 vues)** : variante A (question) 37,7 % de retention moyenne (n=5) ; variante B (constat/bascule) 12,0 % (n=2, mais 102 vues moyennes -> confond de portee). Ecart +25,7 points, mais **bras B sous 5 videos -> non concluant**.
- Prospectif : 0 video assignee a ce stade ; la 1re affectation reelle arrive au prochain passage du pipeline.

### Suite
- Point 3 : recalibrer le hook_score interne sur la retention reelle (aujourd'hui 4 valeurs possibles pour 50 videos, correlation inversee avec les vues).


## 12. Point 3 applique : le score interne est branche sur la retention (27/09)

### Le probleme
- hook_score etait produit par le Hook Microscope (skills/video-analysis, _score_hook via hook_reflection.log_hook_score) : **4 valeurs possibles pour 50 videos** (6,0 / 7,0 / 8,0 / 9,0) et **anti-correle aux vues** (score 7 -> 20,8 vues ; score 8 -> 11,4).
- L'alerte d'auto-reflection se declenchait sur un seuil arbitraire de 6,5/10 : elle ne pouvait pas detecter une video que personne ne regarde.

### Ce qui remplace
- **scripts/retention_score.py** : score 0-10 calcule en **percentile de la chaine** a partir de averageViewPercentage (YouTube Analytics). Echelle : 5 = mediane de la chaine, 10 = meilleure video, 0 = pire. Plus de constante inventee.
- Reference actuelle : **11 videos a >= 10 vues, retention mediane 34,5 % vu** (p25 18,9 / p75 51,8).
- **Drapeau de fiabilite** : une video sous 10 vues recoit un score indicatif mais est ecartee du classement (fini les 10/10 a 2 vues).
- Sortie state/retention_scores.json + enrichissement de state/auto-reflection/hook_history.json (appariement nom de fichier local vers titre via les JSON de script du pipeline : **20 entrees sur 50** rattachees a une retention reelle).

### Les deux consommateurs rebranches
- **hook_reflection._analyze_trend** juge desormais sur retention_score (3 videos consecutives sous 5,0 = sous la mediane -> alerte et ajustement du prompt). Repli sur hook_score uniquement s'il n'existe aucune donnee de retention.
- **learning.get_prompt_lessons()** (injecte dans le prompt du pipeline via LEARNING_INJECTION) ajoute un bloc de 884 caracteres : retention mediane de la chaine, top 3 des ouvertures qui ont retenu, top 3 de celles qui ont fait partir, et la priorite des 15 premieres secondes.
- Exemple de ce que le modele lit maintenant : gagnantes [108,29 % vu] "Le secret bancaire sur vos placements", [66,01 %] "Et si votre pire ennemi sur les marches financiers, c'etait votre propre cerveau ?" ; perdantes [5,0 %] "De nombreux particuliers suivent aveuglement des conseils collectifs avant de subir une drawdown massive." et [6,1 %] "Pourquoi agir sans cesse ?". Consigne : **imiter la structure, ne jamais recopier le texte**. Boucle fermee : la phrase que j'avais designee comme modele ce matin est maintenant citee au modele comme contre-exemple.
- A noter : 2 des 3 meilleures ouvertures sont des questions, ce qui confirme le retrait de l'interdiction.

### Verifications
- 3 retentions faibles (4,2 / 3,1 / 2,0) avec hook_score 8,0 -> **alerte**, metric = retention_score.
- 3 retentions solides (7,0) avec hook_score 6,0 -> **pas d'alerte** (l'ancien seuil aurait crie au loup).
- 2 faibles + 1 bonne -> pas d'alerte (pas de faux positif).
- Historique sans retention -> repli propre sur hook_score.
- Bloc d'injection genere et affiche (884 car.).

### Automatisation
- Cron ajoute : 20 2 * * * (chaque nuit a 02h20 UTC) -> retention_report.py (rafraichit state/retention.json depuis l'API) puis retention_score.py. Log : /home/ubuntu/output/logs/retention.log.
- Crontab sauvegarde avant modification : /tmp/crontab_backup_20260927_1055_before_retention.txt (86 -> 87 lignes).
- Backups des modules : hook_reflection.py.bak_retention_20260927_1053, learning.py.bak_retention_20260927_1053.

### Reste ouvert
- Verifier demain que la 1re affectation A/B (variante B le 28/09) est bien journalisee.
- Laisser tourner 2 a 3 semaines avant toute conclusion A/B (seuils : >= 5 points d'ecart ET >= 5 videos par bras).
- Le seuil de fiabilite (10 vues) et les percentiles deviendront plus stables avec le volume.
