#!/usr/bin/env python3
import argparse, json, sys, subprocess, requests
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
COST_LOG = Path.home() / "output" / "logs" / "llm_costs.jsonl"
SECRETS = Path.home() / ".secrets" / "env"
def load_secrets():
    s = {}
    if SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if "=" in line:
                line = line.replace("export ", "").strip()
                k, v = line.split("=", 1)
                s[k] = v.strip(chr(34)).strip(chr(39))
    return s
def fetch_or(api_key):
    try:
        r = subprocess.run(["curl","-s","https://openrouter.ai/api/v1/auth/key",
            "-H","Authorization: Bearer "+api_key], capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout)
        kd = d.get("data",{})
        return {"total":kd.get("usage",0),"daily":kd.get("usage_daily",0),
                "weekly":kd.get("usage_weekly",0),"monthly":kd.get("usage_monthly",0)}
    except Exception as e:
        print("[WARN] OpenRouter: "+str(e), file=sys.stderr)
        return None
def load_local(days=30):
    if not COST_LOG.exists(): return []
    cutoff = datetime.now() - timedelta(days=days)
    costs = []
    try:
        with open(COST_LOG) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    e = json.loads(line)
                    ts = datetime.fromisoformat(e["ts"])
                    if ts >= cutoff: e["_ts"]=ts; costs.append(e)
                except: continue
    except: pass
    return costs
def compute(costs, or_usage=None):
    now = datetime.now()
    td_start = now.replace(hour=0,minute=0,second=0,microsecond=0)
    mo_start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    total=today=this_month=0.0
    by_model=defaultdict(lambda: {"cost":0.0,"calls":0,"tokens_in":0,"tokens_out":0})
    tin=tout=0
    for e in costs:
        c=e.get("cost_usd",0); m=e.get("model","unknown"); ts=e.get("_ts",now)
        pt=e.get("prompt_tokens",0); ct=e.get("completion_tokens",0)
        total+=c; tin+=pt; tout+=ct
        by_model[m]["cost"]+=c; by_model[m]["calls"]+=1
        by_model[m]["tokens_in"]+=pt; by_model[m]["tokens_out"]+=ct
        if ts>=td_start: today+=c
        if ts>=mo_start: this_month+=c
    if or_usage and not costs:
        total=or_usage["total"]; today=or_usage["daily"]; this_month=or_usage["monthly"]
    if or_usage and costs:
        total=max(total,or_usage["total"]); today=max(today,or_usage["daily"])
        this_month=max(this_month,or_usage["monthly"])
    return {"total":round(total,4),"today":round(today,4),"this_month":round(this_month,4),
            "by_model":dict(by_model),"tin":tin,"tout":tout,"count":len(costs),"or":or_usage}
def fmt(report, days=30):
    lines = []
    lines.append("RAPPORT COUTS LLM")
    lines.append("Periode: %s derniers jours" % days)
    lines.append("Date: "+datetime.now().strftime("%Y-%m-%d %H:%M UTC"))
    lines.append("")
    lines.append("Aujourd hui: $%.4f" % report["today"])
    lines.append("Ce mois: $%.4f" % report["this_month"])
    lines.append("Total periode: $%.4f" % report["total"])
    lines.append("")
    lines.append("Appels: %d" % report["count"])
    lines.append("Tokens in: %s" % format(report["tin"],","))
    lines.append("Tokens out: %s" % format(report["tout"],","))
    lines.append("")
    or_ = report.get("or")
    if or_:
        lines.append("OpenRouter (donnees reelles):")
        labels = [("Total cumule","total"),("Aujourd hui","daily"),("Cette semaine","weekly"),("Ce mois","monthly")]
        for k,v in labels:
            lines.append("  %s: $%.4f" % (k, or_[v]))
        lines.append("")
    if report["by_model"]:
        lines.append("Par modele (logs locaux):")
        for m,s in sorted(report["by_model"].items(), key=lambda x:x[1]["cost"], reverse=True):
            sn = m.split("/")[-1] if "/" in m else m
            lines.append("  %s: $%.4f (%d appels, %s/%s tokens)" % (sn, s["cost"], s["calls"],
                format(s["tokens_in"],","), format(s["tokens_out"],",")))
    if days>0 and report["total"]>0:
        lines.append("Projete mensuel: ~$%.2f" % (report["total"]/days*30))
    elif or_ and or_["total"]>0:
        lines.append("Projete mensuel: ~$%.2f" % or_["monthly"])
    return chr(10).join(lines) + chr(10)
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tg", action="store_true")
    p.add_argument("--days", type=int, default=30)
    a = p.parse_args()
    s = load_secrets()
    api_key = s.get("OPENROUTER_API_KEY","")
    or_ = fetch_or(api_key) if api_key else None
    costs = load_local(days=a.days)
    r = compute(costs, or_usage=or_)
    text = fmt(r, days=a.days)
    print(text, end="")
    if a.tg:
        try:
            bt = s.get("TELEGRAM_BOT_TOKEN")
            ci = s.get("TELEGRAM_CHAT_ID")
            if bt and ci:
                requests.post("https://api.telegram.org/bot"+bt+"/sendMessage",
                    data={"chat_id":ci,"text":text}, timeout=10)
        except: pass
if __name__ == "__main__":
    main()
