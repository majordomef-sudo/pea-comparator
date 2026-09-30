"""Market Scraper v2.1 - Yahoo Finance + Scrapling"""
import json, os
from datetime import datetime
from scrapling import Fetcher

WS = os.path.expanduser("~/.openclaw/workspace")
DATA_DIR = os.path.join(WS, "data", "market")

INDICES = [
    ("^FCHI","CAC 40","FR"),("^GDAXI","DAX","DE"),
    ("^STOXX50E","Euro Stoxx 50","EU"),("^FTSE","FTSE 100","UK"),
    ("^SPX","S&P 500","US"),("^IXIC","Nasdaq","US"),
    ("^DJI","Dow Jones","US"),("BTC-EUR","Bitcoin","CRYPTO"),
]

TOP_ETFS = [
    ("LU1681043599","Amundi MSCI World","CW8"),
    ("FR0010315770","BNP Easy MSCI World","WLD"),
    ("IE00B4L5Y983","iShares Core MSCI World","IWDA"),
    ("FR0010900076","Amundi PEA MSCI World","CW8"),
]


def fetch_indices():
    try:
        import yfinance as yf
        results = []
        for symbol,name,region in INDICES:
            try:
                t = yf.Ticker(symbol)
                hist = t.history(period="5d")
                if hist is not None and len(hist) >= 2:
                    last = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    change = ((last-prev)/prev)*100
                    results.append({"nom":name,"symbole":symbol,"valeur":round(last,2),
                        "variation":round(change,2),"region":region,
                        "date":hist.index[-1].strftime("%Y-%m-%d")})
            except Exception as e:
                results.append({"nom":name,"symbole":symbol,"erreur":str(e)[:50]})
        return results
    except ImportError:
        return [{"erreur":"yfinance non installe"}]


def fetch_top_etfs():
    try:
        import yfinance as yf
        results = []
        for isin,name,ticker in TOP_ETFS:
            try:
                t = yf.Ticker(isin)
                info = t.info
                hist = t.history(period="1mo")
                entry = {"isin":isin,"nom":name,"ticker":ticker}
                if hist is not None and len(hist) >= 5:
                    closes = hist["Close"]
                    entry["prix"] = round(closes.iloc[-1], 2)
                    entry["variation_mensuelle"] = round((closes.iloc[-1]/closes.iloc[0]-1)*100, 2)
                if info:
                    entry["encours"] = info.get("totalAssets")
                    entry["categorie"] = info.get("category")
                results.append(entry)
            except Exception as e:
                results.append({"isin":isin,"nom":name,"erreur":str(e)[:50]})
        return results
    except ImportError:
        return [{"erreur":"yfinance non installe"}]


def fetch_news():
    fetcher = Fetcher()
    headlines = []
    urls = {"boursorama":"https://www.boursorama.com/actualite-economique/"}
    for source,url in urls.items():
        try:
            resp = fetcher.get(url, timeout=10)
            if resp.status != 200: continue
            for h in resp.find_all("h2")[:5]+resp.find_all("h3")[:5]:
                text = h.get_all_text(" ").strip()
                if len(text) > 20:
                    headlines.append({"source":source,"titre":text[:120]})
        except Exception as e:
            print(f"  News {source}: {e}")
    return headlines


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Market Scraper v2.1")
    indices = fetch_indices()
    print(f"  {len(indices)} indices")
    etfs = fetch_top_etfs()
    print(f"  {len(etfs)} ETFs")
    news = fetch_news()
    print(f"  {len(news)} actualites")
    output = {"date":datetime.now().isoformat(),"indices":indices,"etfs":etfs,"news":news}
    today = datetime.now().strftime("%Y%m%d")
    fp = os.path.join(DATA_DIR, f"market_{today}.json")
    with open(fp,"w") as f: json.dump(output,f,indent=2,ensure_ascii=False)
    lp = os.path.join(DATA_DIR, "market_latest.json")
    with open(lp,"w") as f: json.dump(output,f,indent=2,ensure_ascii=False)
    print(f"Saved: {fp}")

if __name__ == "__main__":
    main()