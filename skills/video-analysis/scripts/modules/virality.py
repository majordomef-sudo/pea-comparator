"""
Module viralité — score prédictif basé sur métriques combinées

Facteurs :
1. Ratio motion/statique
2. Durée plan moyenne
3. Taux transitions/min
4. Hook présent
5. CTA présent
6. Émotion forte
7. Données chiffrées

Pondération heuristique (inspirée des analyses académiques de viralité YouTube)
"""

def compute_virality_score(scenes: dict, motion: dict, audio: dict,
                           content: dict) -> dict:
    """Calcule un score de viralité prédictif /20"""
    result = {
        "factors": {},
        "score": 0,
        "details": [],
    }

    score = 0
    details = []

    # Facteur 1: Ratio motion/statique (max 3)
    mr = motion.get("motion_static_ratio", 0.5)
    if 0.3 <= mr <= 0.7:
        score += 3
        details.append(f"✅ Ratio motion idéal ({mr:.0%})")
    elif 0.15 <= mr <= 0.85:
        score += 1.5
        details.append(f"⚠️  Ratio motion acceptable ({mr:.0%})")
    else:
        details.append(f"❌ Ratio motion extrême ({mr:.0%})")

    # Facteur 2: Durée plan moyenne (max 4)
    avg_shot = scenes.get("avg_shot_duration", 10)
    if 3 <= avg_shot <= 7:
        score += 4
        details.append(f"✅ Durée plan idéale ({avg_shot:.1f}s)")
    elif 2 <= avg_shot <= 10:
        score += 2
        details.append(f"⚠️  Durée plan acceptable ({avg_shot:.1f}s)")
    else:
        details.append(f"❌ Durée plan trop longue/courte ({avg_shot:.1f}s)")

    # Facteur 3: Taux transitions/min (max 4)
    tpm = scenes.get("transitions_per_min", 0)
    if tpm >= 10:
        score += 4
        details.append(f"✅ Rythme dynamique ({tpm:.1f} trans/min)")
    elif tpm >= 6:
        score += 3
        details.append(f"⚠️  Rythme modéré ({tpm:.1f} trans/min)")
    elif tpm >= 3:
        score += 1.5
        details.append(f"⚠️  Rythme lent ({tpm:.1f} trans/min)")
    else:
        details.append(f"❌ Rythme très lent ({tpm:.1f} trans/min)")

    # Facteur 4: Hook (max 3)
    hook = content.get("hook", {})
    if hook.get("has_hook"):
        score += 3
        details.append("✅ Hook fort en ouverture")
    elif hook.get("hook_score", 0) > 0:
        score += 1
        details.append("⚠️  Hook partiel")

    # Facteur 5: CTA (max 2)
    cta = content.get("cta", {})
    if cta.get("has_cta"):
        score += 2
        details.append("✅ CTA présent")
    else:
        details.append("❌ Pas de CTA")

    # Facteur 6: Émotion forte (max 2)
    emotion = content.get("emotion", {}) or {}
    primary_emo = emotion.get("primary_emotion", "non identifiée")
    strong_emotions = {"peur", "urgence", "surprise", "ambition"}
    if primary_emo in strong_emotions:
        score += 2
        details.append(f"✅ Émotion forte: {primary_emo}")
    elif primary_emo != "non identifiée":
        score += 1
        details.append(f"⚠️  Émotion modérée: {primary_emo}")

    # Facteur 7: Données chiffrées (max 2)
    data_count = content.get("data_count", 0)
    if data_count >= 3:
        score += 2
        details.append(f"✅ {data_count} données chiffrées (crédibilité)")
    elif data_count >= 1:
        score += 1
        details.append(f"⚠️  1 donnée chiffrée")

    result["score"] = round(min(20, max(0, score)), 1)
    result["factors"] = {
        "motion_ratio": mr,
        "avg_shot_duration": avg_shot,
        "transitions_per_min": tpm,
        "has_hook": hook.get("has_hook", False),
        "has_cta": cta.get("has_cta", False),
        "primary_emotion": emotion.get("primary_emotion", "?"),
        "data_count": data_count,
    }
    result["details"] = details

    return result