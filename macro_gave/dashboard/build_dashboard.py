"""Dashboard HTML autonome. Matrice Gave 2x2 + marqueur de fiabilite."""
import sys, os, json, html
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from macro_gave import db

def _sources_meta():
    conn = db._conn()
    rows = conn.execute("SELECT source FROM indicators ORDER BY id DESC LIMIT 16").fetchall()
    conn.close()
    real = sum(1 for r in rows if r["source"].startswith("Eurostat API"))
    seed = sum(1 for r in rows if r["source"].startswith("REFGEN"))
    return real, seed

def _pill_lite(v):
    c = "#e74c3c" if v < 50 else ("#f39c12" if v < 70 else "#00e676")
    return "<b style=color:" + c + ">" + str(v) + "/100</b>"

def _matrice_gave(q):
    """Matrice Gave 2x2 : croissance x inflation, position actuelle."""
    cells = [
        ("Q2", "Croissance haute / Inflation haute", "Energie, matieres premieres"),
        ("Q1", "Croissance haute / Inflation basse", "Actions cycliques, valeurs"),
        ("Q3", "Croissance basse / Inflation haute (stagflation)", "Or, cash, actifs reels"),
        ("Q4", "Croissance basse / Inflation basse (deflation)", "Obligations longues, or, cash"),
    ]
    out = []
    for k, label, win in cells:
        active = (q == k)
        bg = "#1a3a2a" if active else "#161b22"
        bd = "2px solid #00e676" if active else "1px solid #30363d"
        loc = "LOCPIN " if active else ""
        out.append(
            '<div style="background:' + bg + ';border:' + bd + ';border-radius:8px;padding:10px;margin:6px;min-height:70px">'
            + '<div style="font-weight:600">' + loc + label + '</div>'
            + '<div style="color:#8b949e;font-size:12px;margin-top:4px">' + win + '</div></div>'
        )
    grid = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">' + ''.join(out) + '</div>'
    return '<div class=card><h2>Matrice Gave (position actuelle)</h2>' + grid + '</div>'

def _trend(snaps):
    rows = ""
    for s in snaps[:12]:
        try:
            rg = json.loads(s["regimes"])
            qq, cc = rg.get("quadrant", "?"), rg.get("confidence", 0)
        except Exception:
            qq, cc = "?", 0
        rows += ("<tr><td>" + html.escape(s["created_at"][:10]) + "</td><td>" + qq
                 + "</td><td>" + str(cc) + "</td><td>" + str(s["global_score"])
                 + "</td><td>" + str(s["transition_score"]) + "</td></tr>")
    head = "<table border=1 cellspacing=0><tr><th>Date</th><th>Q</th><th>Conf</th><th>Global</th><th>Transition</th></tr>"
    return head + rows + "</table>" if rows else "<p>pas d historique</p>"

def build(out=None):
    snaps = db.recent_snapshots(24)
    alerts = db.recent_alerts(20)
    s = snaps[0] if snaps else None
    q, conf, gs, ts = "?", 0, 0, 0
    if s:
        try:
            rg = json.loads(s["regimes"])
            q, conf = rg["quadrant"], rg["confidence"]
            gs, ts = s["global_score"], s["transition_score"]
        except Exception:
            pass
    real_n, seed_n = _sources_meta()
    conf_disp = conf
    if seed_n > 0 and real_n > 0:
        conf_disp = round(conf * 0.85)
    badge_seed = ""
    if seed_n > 0 and real_n > 0:
        badge_seed = ("<div class=warn>Z Partiellement estime : " + str(seed_n)
                      + " indicateurs seed (PMI/Brent/TTF/BCE) vs " + str(real_n)
                      + " reels (Eurostat). Quadrant fiable, score pondere approximatif.</div>")
    elif seed_n > 0 and real_n == 0:
        badge_seed = "<div class=warn>W 100% seed : a confirmer avec API reelle.</div>"
    alerts_html = "".join("<div class=a><b>[" + html.escape(a["level"]).upper() + "]</b> "
                          + html.escape(a["message"]) + "</div>" for a in reversed(alerts)) or "<div>Pas d alerte</div>"
    page = "<!DOCTYPE html><html lang=fr><head><meta charset=utf-8><title>Macro Regime</title>"
    page += "<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;padding:24px}.card{background:#161b22;padding:18px;border-radius:10px;margin:10px}h1{color:#58a6ff}.q{color:#00e676;font-size:64px}.warn{color:#f39c12;padding:8px;border:1px solid #f39c12;border-radius:6px}</style></head><body>"
    page += "<h1>MACRO REGIME DASHBOARD</h1>"
    page += "<div class=card><h2>Regime actuel</h2><div class=q>" + q + "</div>Confiance "
    page += _pill_lite(conf_disp) + " (brut " + str(conf) + ") | Global " + _pill_lite(gs) + " | Transition " + _pill_lite(ts) + "</div>"
    page += badge_seed
    page += _matrice_gave(q)
    page += "<div class=card><h2>Historique snapshots</h2>" + _trend(snaps) + "</div>"
    page += "<div class=card><h2>Alertes</h2>" + alerts_html + "</div></body></html>"
    out = out or (Path(__file__).parent / "index.html")
    out.write_text(page, encoding="utf-8")
    return str(out)

if __name__ == "__main__":
    print("Dashboard genere: " + build())
