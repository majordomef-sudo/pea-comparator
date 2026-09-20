# HUMAN_TODO.md — Actions humaines requises (ne pas automatiser sans accord)

## 1. Domaine & DNS (bloquant pour le SEO)
- [ ] Acheter le domaine **.fr** (ex. alfred-invest.fr) et configurer DNS + certificat.
- [ ] Rediriger alfredstudio.mooo.com vers le nouveau domaine (301) une fois en place.
- [ ] Soumettre le domaine privilégié dans Google Search Console + soumettre /sitemap.xml.

## 2. Identité légale (pages créées avec placeholders TODO_LEGAL)
- [ ] Renseigner dans les 5 pages légales : raison sociale, SIRET, forme juridique, siège, directeur de publication, hébergeur, email de contact, DPO.
- [ ] Vérifier si un statut **CIF / conseiller** est nécessaire (site pédagogique sans conseil personnalisé → probablement non, mais à valider avec un professionnel).
- [ ] Page /affiliation : confirmer le programme Trade Republic (montant de commission, identifiant) pour remplacer le texte générique.

## 3. Blog Ghost (cf. BLOG_CLEANUP.md pour le détail)
- [ ] **Unpublish des 50 posts « marche-du-* »** + doublons (l'API admin renvoie 401 : clé staff invalide — régénérer une Admin API key ou agir depuis l'UI /blog/ghost).
- [ ] Créer/renommer l'auteur « Rédaction Alfred Invest » (les articles signés « AlfredIA » posent un problème de crédibilité).
- [ ] Traduire le thème Casper (chrome EN : Latest / See all / Read more) vers un thème custom FR.
- [ ] Retirer les dates « [14/09] » des H1 (garder la date en métadonnées).

## 4. Emails & contacts
- [ ] Fournir un email de contact public (majordomef@gmail.com est privé) pour les pages légales.

## 5. Data ETF
- [ ] Vérifier FR0010892216 (Amundi PEA Nasdaq-100) auprès d'Amundi (vrai ISIN de référence).
- [ ] Lancer la passe de fraîcheur des frais/encours (scraper justETF) — certains champs encours semblent périmés (ex. DCAM).

