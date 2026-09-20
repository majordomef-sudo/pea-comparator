# BLOG_CLEANUP.md — Plan de purge du blog Ghost (2026-09-20)

> Contexte : le blog (Ghost 5.130.6, thème Casper défaut) publie 86 posts dont **50 "Marche du ..."** quotidiens quasi vides et plusieurs **copies dupliquées**. L'API admin a retourné 401 (clé staff invalide pour l'API) : les actions ci-dessous sont à exécuter dans l'admin Ghost (https://alfredstudio.mooo.com/blog/ghost) ou via une clé Admin API régénérée. La statique du site (sitemap.xml) a été nettoyée côté workspace/déployée.

---

## 1. Postes "Marche du …" (50 posts) → UNPUBLISH

Ces posts sont des copies hebdomadaires quasi vides. **Action : unpublish** (pas delete) pour garder l'historique → sélectionner les 50 slugs ci-dessous (recherche "Marche du"), Settings → Unpublish. Ils sortiront automatiquement du sitemap Ghost.

Slugs concernés (préfixe commun) :
- `/blog/marche-du-*` — 50 URLs, du 2026-07-15 au 2026-09-18 (intégrale liste au format sitemap dans `/tmp/blog_posts.txt` ; filtre : grep marche-du)

Si unpublish manuel trop long : régénérer une clé Admin API (Ghost admin → Integrations → + Add custom integration) puis :
```bash
# Boucle d'unpublish via API (remplacer KEY)
ghost_put() { curl -sk -X PUT "https://alfredstudio.mooo.com/blog/ghost/api/admin/posts/$1/" -H "Authorization: Ghost $KEY" -H "Content-Type: application/json" -d '{"posts":[{"status":"draft","updated_at":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'"}]}' ; }
# 1. GET posts publiés, filtrer slug *marche-du*, 2. PUT status=draft
```

## 2. Copie dupliquées des articles de fond → garder UNE version canonique

| Sujet | Copies (slugs) | Garder (canonique) |
|---|---|---|
| L'art du DCA | 21-07, 21-07-2, 01-08, 15-07 (4 slugs sur sitemap posts) | la plus récente (01-08 ou 15-07) ; unpublish les autres |
| 5 erreurs investisseur | 27-07, 10-08, 31-08 (3 slugs) | garder la plus récente (31-08) ; unpublish les autres ; ajouter canonical vers elle |
| ETF capitalisant vs distribuant | 27-07, 13-07, 24-08 (3 slugs) | garder 24-08 ; unpublish les autres |
| Harry Browne portefeuille permanent | 01-09, 15-09 (2 slugs) | garder 15-09 ; unpublish 01-09 |
| L'investissement passif | 06-07, 07-09 (2 slugs) | garder 07-09 ; unpublish 06-07 |
| Inflation et pouvoir d'achat | 20-07, 01-07 (2 slugs) | garder la plus récente ; unpublish l'autre |

**Après unpublish des doublons** : sur l'article conservé, ajouter dans l'éditeur Ghost (Settings → Advanced → Meta data) :
`<link rel="canonical" href="https://alfredstudio.mooo.com/blog/URL-CANONIQUE/" />`

## 3. Chrome du thème EN → FR (thème Casper)

Le thème Casper (défaut) affiche des libellés anglais : "Latest", "See all", "Read more", "Previous/Next", "Subscribe".
**Action** : copier le thème vers un thème custom "alfred-invest-fr" puis traduire :
```bash
docker exec ghost-blog bash -c "cp -r /var/lib/ghost/content/themes/casper /var/lib/ghost/content/themes/alfred-invest-fr"
# + édition des partials ~/content/themes/alfred-invest-fr/partials/*.hbs et *.hbs :
#   home.hbs "Latest" -> "Dernières analyses"
#   post-card.hbs "Read more" -> "Lire la suite"
#   pagination.hbs "Newer/Older Posts" -> "Plus récents / Plus anciens"
#   header: nav "Home" -> "Accueil"
docker exec ghost-blog bash -c "rm -rf /var/lib/ghost/content/themes/casper"  # optionnel après activation
# Activer : Admin Ghost -> Settings -> Theme -> Activate alfred-invest-fr
```

## 4. Bylines, dates, noindex

- **Bylines** : remplacer l'auteur "AlfredIA" par "Rédaction Alfred Invest" (Admin → Team → créer/renommer l'utilisateur). Ajouter en bas de chaque article: « *Cet article a pu être rédigé avec l'aide d'outils d'IA, puis relu par un humain.* »
- **Dates dans les H1** : plusieurs titres contiennent "[14/09]" — retirer ces mentions des titres visibles (la date reste dans les métadonnées Ghost). Articles concernés : tous ceux portant une date de publication différente de leur sujet (ex. l-impact-de-la-psychologie-14-09).
- **noindex** : pour les pages restantes "Calculateur"/pages outils Ghost (calculateur-fire-*, etc.) : Settings → Advanced → Meta data → Index: No (si elles ne devaient pas être des posts).

## 5. Sitemap statique (déjà fait côté site)

Le sitemap racine (https://alfredstudio.mooo.com/sitemap.xml) ne référence plus les posts blog : il contient 10 URLs (accueil, blog/, top-etf, bonus-pea, methodologie + 6 pages légales). Ghost continue de générer son propre sitemap sous /blog/sitemap.xml — il se nettoiera automatiquement après les unpublish.

## 6. Vérification post-opération

```bash
curl -sk "https://alfredstudio.mooo.com/blog/sitemap-posts.xml" | grep -c marche-du   # attendu : 0
curl -sk "https://alfredstudio.mooo.com/blog" | grep -io "see all|read more" | head  # attendu : vide après thème FR
```

---
*Généré le 2026-09-20. Aucune action destructive n'a été réalisée sur Ghost (401 API) ; la liste intégrale des slugs est dans /tmp/blog_posts.txt.*

