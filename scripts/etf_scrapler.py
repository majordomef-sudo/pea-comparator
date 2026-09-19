"""ETF Scrapler v2.4 - yfinance + Scrapling JustETF avec mapping ISIN → ticker"""
import json, re, os, time
from datetime import datetime
from scrapling import Fetcher

WS = os.path.expanduser("~/.openclaw/workspace")
PEA_ETFS = os.path.join(WS, "web", "pea-comparator", "etf-data.js")
BATCH = 20

# Mapping exchange codes JustETF → suffixe Yahoo Finance
EXCHANGE_MAP = {
    "xpar": ".PA",   # Euronext Paris
    "xetra": ".DE",  # Xetra Frankfurt
    "xams": ".AS",   # Euronext Amsterdam
    "xmli": ".MI",   # Borsa Italiana Milan
    "xmad": ".MC",   # Madrid
    "xlux": ".LU",   # Luxembourg (rare sur Yahoo)
    "xswx": ".SW",   # SIX Swiss
    "xlse": ".L",    # London Stock Exchange
    "xbru": ".BR",   # Euronext Brussels
    "xlis": ".LS",   # Euronext Lisbon
}

DEFAULT_SUFFIX = ".DE"  # Fallback Xetra


def load():
    """Parse ETF data file - handles JSON array in JS variable"""
    with open(PEA_ETFS) as f:
        c = f.read()
    start = c.index("[", c.index("PEA_ETFS"))
    end = c.rindex("];") + 1
    return json.loads(c[start:end])


def save(etfs):
    with open(PEA_ETFS) as f:
        c = f.read()
    nj = json.dumps(etfs, indent=2, ensure_ascii=False)
    start = c.index("[", c.index("PEA_ETFS"))
    end = c.rindex("];") + 1
    new_c = c[:start] + nj + c[end:]
    with open(PEA_ETFS, "w") as f:
        f.write(new_c)


def fetch_yahoo(isin, ticker=None):
    """Fetch ETF data from Yahoo Finance using ticker (fallback ISIN)"""
    try:
        import yfinance as yf
        # Use ticker if available, otherwise try ISIN (won't work for EU ETFs)
        symbol = ticker if ticker else isin
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="5y")
        r = {}
        if info:
            p = info.get("currentPrice") or info.get("regularMarketPrice")
            if p: r["prix"] = round(p, 2)
            n = info.get("longName") or info.get("shortName", "")
            if n: r["nom"] = n
            f = info.get("annualReportExpenseRatio")
            if f: r["frais"] = f"{f*100:.2f}".replace(".", ",")
        if hist is not None and len(hist) >= 20:
            closes = hist["Close"]
            if "prix" not in r:
                r["prix"] = round(closes.iloc[-1], 2)
            for lbl, days in [("perf1", 252), ("perf3", 756), ("perf5", 1260)]:
                if len(closes) >= days:
                    pct = (closes.iloc[-1] / closes.iloc[-days] - 1) * 100
                    r[lbl] = f"{pct:.1f}"
        if r: return r
        return {"error": "no data"}
    except Exception as e:
        return {"error": str(e)[:80]}


def fetch_justetf(isin):
    """Fetch ETF ticker + name from JustETF using Scrapling.
    Returns ticker (Yahoo format) and name if found."""
    try:
        f = Fetcher()
        r = f.get(f"https://www.justetf.com/en/etf-profile.html?isin={isin}", timeout=15)
        if r.status != 200:
            return {"error": f"HTTP {r.status}"}

        result = {}

        # Extract name from h1
        title = r.find("h1")
        if title:
            result["nom"] = title.text[:80]

        # Extract ticker from the identifier-value element
        ticker_el = r.css("[data-testid='etf-profile-header_identifier-value-ticker']")
        if ticker_el and ticker_el[0].text and ticker_el[0].text.strip():
            ticker_raw = ticker_el[0].text.strip()
            result["ticker_raw"] = ticker_raw
        else:
            # Fallback: try trade-data panel
            ticker_el2 = r.css("[data-testid*='ticker']")
            for el in ticker_el2:
                tid = el.attrib.get("data-testid", "")
                text = el.text.strip() if el.text else ""
                if text and "row-" in tid and text.isupper() and len(text) <= 10:
                    result["ticker_raw"] = text
                    break

        # Determine exchange suffix from the ticker row's data-testid
        if "ticker_raw" in result:
            for el in r.css("[data-testid*='ticker']"):
                tid = el.attrib.get("data-testid", "")
                text = el.text.strip() if el.text else ""
                if text == result["ticker_raw"] and "row-" in tid:
                    # Extract exchange code: e.g., "etf-trade-data-panel_row-xpar_ticker" → "xpar"
                    match = re.search(r"row-([a-z]+)_", tid)
                    if match:
                        exchange_code = match.group(1)
                        suffix = EXCHANGE_MAP.get(exchange_code, DEFAULT_SUFFIX)
                        result["ticker"] = f"{result['ticker_raw']}{suffix}"
                        break

        # If we have raw ticker but no suffix found, try to find any row- exchange
        if "ticker_raw" in result and "ticker" not in result:
            for el in r.css("[data-testid*='row-']"):
                tid = el.attrib.get("data-testid", "")
                match = re.search(r"row-([a-z]+)_", tid)
                if match:
                    exchange_code = match.group(1)
                    if exchange_code in EXCHANGE_MAP:
                        suffix = EXCHANGE_MAP.get(exchange_code, DEFAULT_SUFFIX)
                        result["ticker"] = f"{result['ticker_raw']}{suffix}"
                        break

        return result if result else {"error": "no data scraped"}
    except Exception as e:
        return {"error": str(e)[:80]}


def process(etf, idx, total):
    """Process a single ETF - new flow:
    1. Try JustETF to get ticker + name
    2. Try yfinance with ticker to get perf5, prix, frais"""
    isin = etf["isin"]
    if etf.get("perf5") not in ("N/A", "", None): return None
    skip_bg = ["BG"]
    if isin[:2] in skip_bg: return None
    print(f"  [{idx}/{total}] {isin} ", end="", flush=True)

    # Step 1: Try JustETF to get ticker + name
    justetf_data = fetch_justetf(isin)
    ticker = None

    if justetf_data and "error" not in justetf_data:
        updates = []
        # Save ticker if found
        if "ticker" in justetf_data and "ticker" not in etf:
            etf["ticker"] = justetf_data["ticker"]
            ticker = justetf_data["ticker"]
            updates.append("ticker")
        # Save name if missing (rare, but just in case)
        if "nom" in justetf_data and justetf_data["nom"] and            (etf.get("nom", "").strip() in ("N/A", "", None)):
            etf["nom"] = justetf_data["nom"]
            updates.append("nom")
        if updates:
            print(f"OK JustETF: {updates} ", end="")
        else:
            # Check if ticker was already known (from previous run)
            if etf.get("ticker"):
                ticker = etf["ticker"]
            print(f"JustETF: name exists, ticker={ticker or 'none'} ", end="")

    # Step 2: Try yfinance with ticker (or ISIN as last resort)
    yahoo_data = fetch_yahoo(isin, ticker=ticker)
    if yahoo_data and "error" not in yahoo_data:
        updates = []
        for k in ["perf5", "perf3", "perf1", "prix", "frais", "nom"]:
            if k in yahoo_data:
                # perf5, perf3, perf1: always update
                if k.startswith("perf"):
                    etf[k] = yahoo_data[k]
                    updates.append(k)
                # prix, frais: update if not already set
                elif k not in etf or etf.get(k, "") in ("N/A", "", None):
                    etf[k] = yahoo_data[k]
                    updates.append(k)
        if updates:
            print(f"+ yfinance: {updates}")
            return True
        else:
            print(f"(yfinance: all fields known)")

    print("no data")
    return False


import re, json, os, sys, time, html
from datetime import datetime

def fetch_fundamentals(isin):
    """Enrichit un ETF avec les fondamentaux justETF : encours, devise, dist/cap, date creation, indice, vol, replication."""
    try:
        f = Fetcher()
        r = f.get(f"https://www.justetf.com/en/etf-profile.html?isin={isin}", timeout=15)
        if r.status != 200:
            return {"error": f"HTTP {r.status}"}
        s = r.body.decode("utf-8", "ignore")
    except Exception as e:
        return {"error": str(e)[:80]}

    def grab(tid):
        m = re.search(r'data-testid="' + re.escape(tid) + r'"[^>]*>([\s\S]*?)</', s)
        if not m: return None
        return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip()[:90]

    result = {}
    # Encours : "EUR 1,465   m" / "EUR 2,3 Mrd" / "USD 500 b"
    m = re.search(r'data-testid="etf-profile-header_fund-size-value-wrapper"[^>]*>([\s\S]*?)</div>', s)
    if m:
        raw = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
        raw = re.sub(r"\s+", " ", raw).strip()
        mm = re.match(r"([A-Z]{3})?\s*([\d.,]+)\s*([Mm]|Mrd|[Bb]n?)?", raw)
        if mm:
            try:
                num = float(mm.group(2).replace(",", ""))
                unit = (mm.group(3) or "m").lower()
                if unit in ("mrd", "b", "bn"): num *= 1000
                result["encours_mio"] = round(num, 1)
                result["encours_devise"] = mm.group(1) or "EUR"
            except Exception:
                pass
    for tid, key in [
        ("tl_etf-basics_value_fund-currency", "devise"),
        ("etf-profile-header_distribution-policy-value", "distribution"),
        ("etf-profile-header_inception-date-value", "date_creation"),
        ("tl_etf-basics_value_index-name", "indice"),
        ("tl_etf-basics_value_volatility", "volatilite"),
        ("tl_etf-basics_value_replication", "replication"),
        ("tl_etf-basics_value_replication-method", "repl_method"),
        ("tl_etf-basics_value_fund-provider", "emetteur_full"),
        ("tl_etf-basics_value_domicile-country", "domicile"),
        ("tl_etf-basics_value_currency-hedge", "hedge"),
    ]:
        v = grab(tid)
        if v and v not in ("-", ""):
            result[key] = v
    return result if result else {"error": "no data scraped"}


def process_fundamentals(etf, idx, total):
    """Remplit encours, devise, distribution, date_creation, indice, vol, replication (un seul passage par ETF)."""
    if etf.get("encours_mio"):
        return False  # déjà enrichi
    isin = etf.get("isin", "")
    if isin[:2] in ("BG",):
        return False
    print(f"  [{idx}/{total}] FUND {isin} ", end="", flush=True)
    d = fetch_fundamentals(isin)
    if not d or "error" in d:
        print("no data")
        return False
    upd = []
    for k in ("encours_mio", "encours_devise", "devise", "distribution", "date_creation",
              "indice", "volatilite", "replication", "repl_method", "emetteur_full", "domicile", "hedge"):
        if d.get(k) not in (None, "", "N/A", "?"):
            if etf.get(k) in (None, "", "N/A", "?"):
                etf[k] = d[k]
                upd.append(k)
    print("OK:", upd if upd else "rien de neuf")
    return bool(upd)


def build_min():
    """Régénère etf-data.min.js depuis la source + déploie sur /var/www/html (le site sert le min !)."""
    WS = os.path.expanduser("~/.openclaw/workspace")
    src_path = os.path.join(WS, "web", "pea-comparator", "etf-data.js")
    dst_path = os.path.join(WS, "web", "pea-comparator", "etf-data.min.js")
    c = open(src_path, encoding="utf-8").read()
    start = c.index("[", c.index("PEA_ETFS"))
    end = c.rindex("];") + 1
    data = json.loads(c[start:end])
    out = "const ETF_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\nwindow.PEA_ETFS = ETF_DATA;\n"
    open(dst_path, "w", encoding="utf-8").write(out)
    # déploiement live (sudo NOPASSWD OK)
    os.system("sudo cp " + dst_path + " /var/www/html/etf-data.min.js")
    # cache-bust : bumper le ?v= dans index.html (source + live) pour forcer le rechargement navigateurs
    import time as _t, subprocess
    newhash = str(int(_t.time()))
    for ip in (os.path.join(WS, "web", "pea-comparator", "index.html"), "/var/www/html/index.html"):
        try:
            h = open(ip, encoding="utf-8").read()
        except PermissionError:
            h = subprocess.run(["sudo", "cat", ip], capture_output=True, text=True).stdout
        try:
            m = re.search(r"etf-data\.min\.js\?v=[0-9]+", h)
            if m:
                h2 = h.replace(m.group(0), "etf-data.min.js?v=" + newhash)
                if h2 != h:
                    src_tmp = os.path.join(WS, ".cachebust.tmp")
                    open(src_tmp, "w", encoding="utf-8").write(h2)
                    os.system("sudo cp " + src_tmp + " " + ip)
                    os.remove(src_tmp)
                    print(f"  cache-bust: etf-data.min.js?v={newhash} ({ip.split('/')[-1]})")
        except Exception as e:
            print("  cache-bust skip:", ip, str(e)[:50])
    print(f"  build_min: {len(data)} ETF -> etf-data.min.js déployé")



def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, default=BATCH)
    p.add_argument("--fundamentals", type=int, default=0, help="passe fondamentaux: N ETF sans encours")
    p.add_argument("--build-min", action="store_true", help="regenerer et deployer etf-data.min.js")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--specific", type=str)
    p.add_argument("--refresh-all", action="store_true")
    args = p.parse_args()
    print(f"ETF Scrapler v2.4 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    etfs = load()
    print(f"  {len(etfs)} ETFs loaded")
    if args.specific:
        batch = [e for e in etfs if e["isin"] == args.specific]
        if not batch:
            print("ISIN not found")
            return
    else:
        valid = [e for e in etfs if e["isin"][:2] not in ("BG",)]
        missing = [e for e in valid if e.get("perf5") in ("N/A", "", None)]
        print(f"  {len(missing)} need perf5 (excluding BG)")
        batch = missing if args.refresh_all else missing[:args.batch]
    count = 0
    # ---- Passe fondamentaux (encours, devise, dist/cap, date, indice, vol) ----
    if args.fundamentals and not args.specific:
        missing = [e for e in etfs if e.get("isin", "")[:2] not in ("BG",) and not e.get("encours_mio")]
        print(f"  {len(missing)} ETF sans encours (excl. BG)")
        batch = missing[:args.fundamentals]
        print(f"Fundamentals: traitement de {len(batch)} ETF")
        for i, e in enumerate(batch):
            if process_fundamentals(e, i + 1, len(batch)):
                count += 1
            time.sleep(1.0)  # soyez gentil avec justETF
        if not args.dry_run and count > 0:
            save(etfs)
            print("Saved to etf-data.js (fundamentals)")
        if args.build_min and not args.dry_run:
            build_min()
        return

    print(f"Processing {len(batch)} ETFs")
    for i, e in enumerate(batch):
        if process(e, i + 1, len(batch)):
            count += 1
        time.sleep(0.5)  # Be nice to JustETF & Yahoo
    print(f"Done: {count}/{len(batch)} enriched")
    if not args.dry_run and count > 0:
        save(etfs)
        print("Saved to etf-data.js")
    if args.build_min and not args.dry_run:
        build_min()


if __name__ == "__main__":
    main()

