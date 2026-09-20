# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
d = open("methodologie.html", encoding="utf-8").read()
# 1) Date coherente dans la section 5
n1 = d.count("<strong>15/09/2026</strong>")
d = d.replace("<strong>15/09/2026</strong>", "<strong>20/09/2026</strong>")
print("date section 5 corrigee:", n1)
# 2) Changelog avant le footer
chg = """
<h2>9. Historique des changements</h2>
<div class="card">
<ul style="padding-left:20px;line-height:1.7">
<li><strong>20/09/2026</strong> — Version 1.0 publiée : pondérations Qualité de l\u2019indice 25 / Réplication 20 / Coûts (TER) 15 / Solidité du fonds 15 / Émetteur 10 / Potentiel futur 15 (total plafonné à 100). Données rafraîchies : 437 ETF, sources DICI/PRIIPs &amp; justETF.</li>
<li><strong>19/09/2026</strong> — Consolidation : labels de qualité alignés sur les seuils (Très bon 74+, Bon 64–73, Moyen 54–63, Faible 44–53, Très faible &lt;44), suppression des libellés d\u2019achat/vente.</li>
</ul>
</div>
"""
if "Historique des changements" not in d:
    i = d.find("<footer")
    d = d[:i] + chg + chr(10) + d[i:]
    open("methodologie.html", "w", encoding="utf-8").write(d)
    print("changelog ajoute")
else:
    print("changelog deja present")
# verif
d2 = open("methodologie.html", encoding="utf-8").read()
print("plus de 15/09:", "strong>15/09/2026" not in d2)
print("20/09 present:", d2.count("20/09/2026"))
