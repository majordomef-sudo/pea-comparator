# -*- coding: utf-8 -*-
import os, json, re
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)

FAQ = [
("Qu\u2019est-ce qu\u2019un ETF PEA ?", "Un ETF (Exchange Traded Fund) est un fonds indiciel cot\u00e9 en bourse. Les ETF \u00e9ligibles PEA respectent la r\u00e9glementation fran\u00e7aise et b\u00e9n\u00e9ficient d\u2019une fiscalit\u00e9 avantageuse (exon\u00e9ration d\u2019imp\u00f4t sur le revenu apr\u00e8s 5 ans)."),
("Quel ETF PEA choisir selon mon objectif ?", "Il n\u2019existe pas de meilleur ETF en absolu : tout d\u00e9pend de votre objectif. Exposition mondiale : Amundi MSCI World ou iShares Core MSCI World. \u00c9tats-Unis : S&P 500 ou Nasdaq. Europe : Euro Stoxx 50 ou MSCI Europe. \u00c9mergents : Amundi PEA Emergent. Comparez frais, encours et r\u00e9plication via le Score Alfred (outil p\u00e9dagogique, pas un conseil personnalis\u00e9)."),
("Quels sont les frais \u00e0 surveiller ?", "Le TER (Total Expense Ratio) est le principal. Un bon ETF PEA affiche souvent un TER entre 0,10 % et 0,30 %. Au-del\u00e0 de 0,50 %, l\u2019impact sur le long terme devient significatif : utilisez notre simulateur d\u2019impact des frais."),
("PEA ou assurance-vie ?", "Le PEA est fiscalement avantageux apr\u00e8s 5 ans (pr\u00e9l\u00e8vements sociaux uniquement). L\u2019assurance-vie offre plus de flexibilit\u00e9 (fonds euros, transmission). Comparez sur le long terme avec notre outil PEA vs AV vs CTO."),
("R\u00e9plication physique ou synth\u00e9tique : quelle diff\u00e9rence ?", "Un ETF physique ach\u00e8te r\u00e9ellement les titres de l\u2019indice ; un ETF synth\u00e9tique utilise un swap avec une contrepartie bancaire. Les deux sont des fonds indiciels UCITS. R\u00e9glementairement, l\u2019\u00e9ligibilit\u00e9 PEA des ETF \u00e0 r\u00e9plication synth\u00e9tique \u00e9volue : v\u00e9rifiez la fiche du fonds et l\u2019\u00e9ligibilit\u00e9 \u00e0 jour (source : r\u00e9glementation en vigueur, DIC/PRIIPs)."),
("Comment savoir si un ETF est \u00e9ligible au PEA ?", "L\u2019\u00e9ligibilit\u00e9 PEA figure dans le DIC/PRIIPs et aupr\u00e8s de votre courtier. Sur Alfred Invest, chaque fiche ETF affiche le badge PEA issu des donn\u00e9es (DICI/PRIIPs, justETF, mise \u00e0 jour du 20/09/2026). V\u00e9rifiez toujours aupr\u00e8s de votre courtier avant d\u2019investir."),
("ETF capitalisant ou distribuant : lequel choisir ?", "Un ETF capitalisant r\u00e9investit automatiquement les dividendes (adapt\u00e9 au long terme en PEA) ; un ETF distribuant verse des revenus. En PEA, la capitalisation est souvent privil\u00e9gi\u00e9e, mais tout d\u00e9pend de votre objectif de revenus et de votre horizon."),
("Tracking difference vs TER : qu\u2019est-ce qui compte ?", "Le TER est le co\u00fbt annuel affich\u00e9 du fonds. La tracking difference mesure l\u2019\u00e9cart r\u00e9el entre la performance de l\u2019ETF et celle de son indice (frais, swap, pr\u00eat de titres). C\u2019est la tracking difference qui refl\u00e8te le co\u00fbt r\u00e9el support\u00e9 par l\u2019investisseur."),
("Combien d\u2019ETF peut-on avoir dans un PEA ?", "Le PEA n\u2019impose pas de nombre maximal d\u2019ETF : le plafond de versements est de 150 000 \u20ac. Alfred Invest r\u00e9f\u00e9rence 437 ETF \u00e9ligibles ; la diversit\u00e9 d\u00e9pend de votre strat\u00e9gie, pas d\u2019une obligation de quantit\u00e9."),
("Qu\u2019est-ce que le Score Alfred ?", "Une note p\u00e9dagogique /100 qui combine plusieurs crit\u00e8res (qualit\u00e9 de l\u2019indice, r\u00e9plication, co\u00fbts, solidit\u00e9 du fonds, \u00e9metteur, potentiel futur) selon une m\u00e9thode transparente et document\u00e9e : voir la page M\u00e9thodologie. C\u2019est un signal indicatif, pas une recommandation d\u2019achat."),
("Alfred Invest est-il un conseiller en investissement ?", "Non. Alfred Invest est un site p\u00e9dagogique ind\u00e9pendant : il ne fournit pas de conseil personnalis\u00e9 et n\u2019est ni un CIF, ni un CGP. Toute d\u00e9cision d\u2019investissement vous appartient."),
("D\u2019o\u00f9 viennent vos donn\u00e9es ETF ?", "Les donn\u00e9es (frais, SRI, performance, encours, r\u00e9plication) proviennent des documents officiels DIC/PRIIPs et de justETF, avec une date de mise \u00e0 jour affich\u00e9e (20/09/2026). En cas de diff\u00e9rence, faites foi aux documents officiels du fonds."),
]

def qhtml():
    out = []
    for q, a in FAQ:
        out.append('<details class="faq-item"><summary>' + q + '</summary><p>' + a + '</p></details>')
    return "\n      ".join(out)

d = open("index.html", encoding="utf-8").read()

# remplacer le contenu du faq-grid
start = d.find('<div class="faq-grid">')
end = d.find('</div>', start) + len('</div>')
if start > 0 and end > start:
    new_grid = '<div class="faq-grid">\n      ' + qhtml() + '\n      </div>'
    d = d[:start] + new_grid + d[end:]
    print("FAQ grid remplace: 12 questions")
else:
    print("WARN: faq-grid introuvable")

# JSON-LD FAQPage avant </head>
if "FAQPage" not in d:
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    script = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + '</script>'
    d = d.replace("</head>", script + "\n</head>")
    print("JSON-LD FAQPage ajoute")

open("index.html", "w", encoding="utf-8").write(d)
print("OK B5")
