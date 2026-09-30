# 📖 LEXIQUE SÉMANTIQUE : FINANCE DE MARCHÉ
**Objectif**: Forcer l'utilisation d'un vocabulaire financier précis et professionnel. Ce lexique sert de filtre de remplacement pour le LLM.

---

## 🔄 MAPPINGS SÉMANTIQUES (Remplacement Obligatoire)

| Terme Générique (À éviter) | Terme Stratégique (À utiliser) | Nuance / Justification |
| :--- | :--- | :--- |
| Argent / Être riche | **Capital / Patrimoine** | Distinguer l'outil (capital) de l'objectif (patrimoine). |
| Gagner de l'argent | **Générer du rendement** | L'investissement n'est pas un salaire, c'est une performance. |
| Perdre de l'argent | **Subir une drawdown** | Terme technique qui normalise la perte comme partie du cycle. |
| Acheter des actions | **Prendre une position** | Vocabulaire professionnel, pas de broker amateur. |
| Vendre ses actions | **Liquidier une position** | Action délibérée, pas une réaction émotionnelle. |
| La Bourse | **Les Marchés Financiers** | Plus large, plus professionnel. |
| Ça monte / Ça baisse | **Tendance haussière / Correction / Krach** | Précision cyclique, pas d'émotion. |
| Avoir peur de la bourse | **Aversion au risque** | C'est un paramètre de stratégie, pas une faiblesse. |
| Investir régulièrement | **DCA (Dollar Cost Average)** | Nommer la stratégie, pas juste la décrire. |
| Répartir ses placements | **Diversification / Allocation d'actifs** | Distinguer la diversification (simple) de l'allocation (stratégique). |
| Vendre au mauvais moment | **Panic Selling** | Terme identifié, étudié, prévisible. |
| Acheter au mauvais moment | **FOMO / Achat au sommet** | Comportement grégaire documenté. |
| Timing du marché | **Market Timing** | L'ennemi à abattre. Toujours en négatif. |
| Profiter d'une baisse | **Acheter la décote / Buy the dip** | Mécanisme connu des investisseurs value. |
| Attendre que ça remonte | **Ancrage au prix d'entrée** | Biais cognitif documenté. Ne pas attendre, réévaluer. |
| Perdre patience | **Sous-performer par attrition** | L'impatience a un coût mesurable. |
| Se renseigner | **Faire son due diligence** | Process, pas intuition. |
| Suivre la mode | **Comportement grégaire / Herding** | Phénomène de marché documenté. |
| Crise | **Correction / Bear Market / Krach** | Distinguer l'amplitude : -10%, -20%, -30%+. |
| Rendement garanti | **Rendement espéré / Probabilité** | Rien n'est garanti sur les marchés. |

---

## 🛠️ RÈGLES D'APPLICATION POUR LE LLM

1. **Interdiction du "Guru-Speak"** : Tout mot évoquant le "secret", la "magie" ou la "formule miracle" est interdit. Remplacer par des **notions de stratégie**, de **données historiques** ou de **mécanisme éprouvé**.
2. **Précision des Cycles** : Quand on parle d'une baisse, nommer précisément l'amplitude : correction (-10%), bear market (-20%+), krach (-30%+).
3. **L'Obsession du Temps** : Le temps (horizon d'investissement) est toujours présenté comme le facteur le plus important. « Sur 1 an, le marché est imprévisible. Sur 20 ans, il a toujours gagné. »
4. **Data First** : Toute affirmation sur les marchés DOIT être accompagnée d'un chiffre, d'une date, d'un rendement historique. Pas d'opinion sans data.

---

## 🧪 EXEMPLE DE TRANSFORMATION

**Texte Générique** :
*"Si vous voulez devenir riche, vous devez investir en bourse et acheter quand ça baisse."*

**Texte Finance de Marché (Après application du lexique)** :
*"Pour générer du rendement, vous devez allouer votre capital sur les marchés financiers avec un DCA systématique. Acheter la décote lors des corrections de -10% est un mécanisme qui a historiquement surperformé le market timing dans 80% des cas."*