import csv
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import shutil
import re

# Configuration des chemins absolus
BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
CSV_PATH = os.path.join(BASE_DIR, 'history.csv')
BACKUP_PATH = os.path.join(BASE_DIR, 'history.csv.bak')

import functools
import time

def retry(max_attempts=3, delay=2):
    """Décorateur de réessai pour les appels réseau."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"  ⚠️ Tentative {attempt+1}/{max_attempts} échouée: {e}")
                        time.sleep(delay * (attempt + 1))
                    else:
                        print(f"  ❌ Échec après {max_attempts} tentatives: {e}")
                        raise
            return None
        return wrapper
    return decorator


MOIS_MAP = {
    'janvier':'01','février':'02','mars':'03','avril':'04','mai':'05','juin':'06',
    'juillet':'07','août':'08','septembre':'09','octobre':'10','novembre':'11','décembre':'12'
}

JOUR_MAP = {
    'lundi': 'LUNDI', 'mardi': 'MARDI', 'mercredi': 'MERCREDI',
    'jeudi': 'JEUDI', 'vendredi': 'VENDREDI', 'samedi': 'SAMEDI', 'dimanche': 'DIMANCHE'
}

def backup_data():
    """Crée une sauvegarde du fichier history.csv avant mise à jour."""
    if os.path.exists(CSV_PATH):
        shutil.copy2(CSV_PATH, BACKUP_PATH)
        print(f"Sauvegarde créée : {BACKUP_PATH}")

def parse_french_date(date_str):
    """Convertit '5 mai 2026' en dictionnaire {date, jour}."""
    parts = date_str.strip().split()
    if len(parts) >= 3:
        jour = parts[0].zfill(2)
        mois = MOIS_MAP.get(parts[1].lower(), '01')
        annee = parts[2]
        return f"{jour}/{mois}/{annee}"
    return None

@retry(max_attempts=2, delay=1)
def fetch_from_resultat_fr(date):
    """
    Récupère un tirage spécifique depuis resultat.fr (fiable, structure propre).
    Retourne None si pas trouvé.
    """
    jour_map = {'lundi': 'LUNDI', 'mardi': 'MARDI', 'mercredi': 'MERCREDI',
                'jeudi': 'JEUDI', 'vendredi': 'VENDREDI', 'samedi': 'SAMEDI', 'dimanche': 'DIMANCHE'}
    jour_semaine = None

    # Déterminer le jour de la semaine pour la date
    try:
        dt = datetime.strptime(date, "%d/%m/%Y")
        jour_semaine = {1: 'MARDI', 4: 'VENDREDI'}.get(dt.weekday())
    except:
        pass

    # Générer l'URL au format JJ-MM-AAAA
    try:
        dt = datetime.strptime(date, "%d/%m/%Y")
        url_date = f"{dt.strftime('%d-%m-%Y')}"
        prefix = 'mardi-' if dt.weekday() == 1 else 'vendredi-'
        for _ in range(1):
            url = f"https" + chr(58) + chr(47) * 2 + f"resultat.fr/euromillions/resultats/{prefix}{url_date}"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')

                # Chercher les numéros dans les span.numero
                nums = []
                for span in soup.select('li.ball.blue.ball:not(.lucky-star)'):
                    text = span.get_text().strip()
                    if text.isdigit() and 1 <= int(text) <= 50:
                        nums.append(int(text))

                stars = []
                for span in soup.select('li.ball.blue.lucky-star'):
                    text = span.get_text().strip()
                    if text.isdigit() and 1 <= int(text) <= 12:
                        stars.append(int(text))

                if len(nums) >= 5 and len(stars) >= 2:
                    print(f"  ✓ Récupéré depuis resultat.fr")
                    return {'date': date, 'jour': jour_semaine,
                            'balls': nums[:5], 'stars': stars[:2]}
            except:
                continue
    except:
        pass
    return None


@retry(max_attempts=2, delay=1)
def fetch_from_secretsdujeu(date=None):
    """
    Récupère le dernier tirage depuis secretsdujeu.com.
    """
    print("Recherche du dernier tirage sur secretsdujeu.com...")
    url = "https" + chr(58) + chr(47) * 2 + "www.secretsdujeu.com/euromillion/resultat"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Récupérer les numéros
        numeros = [p.get_text().strip() for p in soup.find_all('p', class_='euromillions-numero')]
        etoiles = [p.get_text().strip() for p in soup.find_all('p', class_='euromillions-etoile')]

        if not numeros or not etoiles:
            print("Impossible de trouver les numéros sur la page.")
            return None

        balls = [int(n) for n in numeros[:5]]
        stars = [int(e) for e in etoiles[:2]]

        # 2. Récupérer la date depuis le <h2> (beaucoup plus fiable)
        # Format: "Tirage de l'EuroMillions du mardi 5 mai 2026"
        h2 = soup.find('h2')
        date_str = None
        jour_semaine = None
        if h2:
            h2_text = h2.get_text().strip()
            print(f"H2 trouvé : {h2_text}")
            date_match = re.search(
                r'du\s+(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(\d{1,2}\s+\w+\s+\d{4})',
                h2_text, re.IGNORECASE
            )
            if date_match:
                jour_semaine = JOUR_MAP[date_match.group(1).lower()]
                date_str = parse_french_date(date_match.group(2))
                print(f"Date parsée du h2 : {date_str} ({jour_semaine})")

        # Fallback: regex sur tout le texte si le h2 n'a pas marché
        if not date_str:
            print("Fallback: recherche dans le texte...")
            text = soup.get_text()
            all_dates = []
            for jour_nom in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']:
                for match in re.finditer(
                    rf'{jour_nom}\s+(\d{{1,2}}\s+\w+\s+\d{{4}})',
                    text, re.IGNORECASE
                ):
                    parsed = parse_french_date(match.group(1))
                    if parsed:
                        all_dates.append((parsed, jour_nom))

            today = datetime.now()
            valid_dates = []
            for d, j in all_dates:
                try:
                    dt = datetime.strptime(d, "%d/%m/%Y")
                    if dt <= today:
                        valid_dates.append((dt, d, j))
                except:
                    pass

            if valid_dates:
                valid_dates.sort(key=lambda x: x[0], reverse=True)
                date_str = valid_dates[0][1]
                jour_semaine = JOUR_MAP.get(valid_dates[0][2], None)
                print(f"Date parsée (fallback) : {date_str} ({jour_semaine})")

        if not date_str:
            date_str = datetime.now().strftime("%d/%m/%Y")
            jour_semaine = JOUR_MAP.get(datetime.now().strftime("%A").lower(), None)

        return {'date': date_str, 'jour': jour_semaine, 'balls': balls, 'stars': stars}
    except Exception as e:
        print(f"Erreur lors du scraping secretsdujeu : {e}")
        return None


def get_missing_draw_dates(lookback_days=365):
    """Détecte les trous mardi/vendredi sur une période récente."""
    if not os.path.exists(CSV_PATH):
        return []
    try:
        df = pd.read_csv(CSV_PATH, delimiter=";", low_memory=False)
        dates = pd.to_datetime(df["date_de_tirage"], dayfirst=True, errors="raise").dt.normalize()
        existing = set(dates)
        end_date = pd.Timestamp(datetime.now().date()) - pd.Timedelta(days=1)
        start_date = max(dates.min(), end_date - pd.Timedelta(days=lookback_days))
        expected = pd.date_range(start=start_date, end=end_date, freq="D")
        return [date.strftime("%d/%m/%Y") for date in expected if date.weekday() in (1, 4) and date not in existing]
    except Exception as e:
        print(f"Erreur détection des tirages manquants : {e}")
        raise


@retry(max_attempts=2, delay=1)
def fetch_draw_by_date(date):
    """
    Tente de récupérer un tirage pour une date spécifique.
    Essaie plusieurs sources dans l'ordre.
    """
    print(f"\n📡 Récupération du tirage du {date}...")

    # Source 1: resultat.fr
    result = fetch_from_resultat_fr(date)
    if result:
        return result

    # Source 2: secretsdujeu.com (ne donne que le dernier, skip si date != aujourd'hui)
    print(f"  ⚠ resultat.fr indisponible pour {date}")
    return None


def fetch_latest_draw():
    """
    Récupère le dernier tirage avec backfill des dates manquantes.
    """
    print("🔍 Vérification des tirages manquants...")

    # Étape 1: Backfill des dates manquantes
    missing_dates = get_missing_draw_dates()
    if missing_dates:
        print(f"📌 {len(missing_dates)} tirage(s) manquant(s) détecté(s) : {missing_dates}")
        for d in missing_dates:
            result = fetch_draw_by_date(d)
            if result:
                print(f"→ {result['date']} ({result['jour']}) -> {result['balls']} | {result['stars']}")
                if append_draw_to_csv(result['date'], result['jour'], result['balls'], result['stars']):
                    print("  ✅ Ajouté")
                else:
                    print("  ℹ️ Déjà présent")
    else:
        print("✅ Aucun tirage manquant détecté")

    # Étape 2: Dernier tirage via secretsdujeu (sert de vérification supplémentaire)
    last = fetch_from_secretsdujeu()
    if last:
        print(f"\n🔄 Dernier tirage (secretsdujeu) : {last['date']} ({last['jour']}) -> {last['balls']} | {last['stars']}")
        if datetime.strptime(last["date"], "%d/%m/%Y").date() >= datetime.now().date():
            print(f"  ⚠️ Tirage du jour ignoré avant validation officielle : {last['date']}")
            return None
        if datetime.strptime(last["date"], "%d/%m/%Y").weekday() not in (1, 4):
            print(f"  ⚠️ Date invalide ignorée : {last["date"]} n’est pas un mardi ou vendredi")
            return None
        if not is_draw_in_csv(last['date']):
            if append_draw_to_csv(last['date'], last['jour'], last['balls'], last['stars']):
                print("  ✅ Ajouté")
            else:
                print("  ℹ️ Déjà présent")
        else:
            print("  ℹ️ Déjà présent dans la base")
        return last

    return None

def is_draw_in_csv(date_str):
    """Vérifie si un tirage existe déjà dans le CSV (colonne date_de_tirage uniquement)."""
    if not os.path.exists(CSV_PATH):
        return False
    try:
        df = pd.read_csv(CSV_PATH, delimiter=';', low_memory=False)
        return date_str in df['date_de_tirage'].astype(str).values
    except Exception:
        # Fallback: regex sur la 3ème colonne uniquement (0-indexed = colonne 2)
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                cols = line.strip().split(';')
                if len(cols) > 2 and cols[2].strip() == date_str:
                    return True
        return False

def append_draw_to_csv(date, jour, balls, stars):
    """Valide puis ajoute un tirage avec le nombre exact de colonnes."""
    draw_date = datetime.strptime(date, "%d/%m/%Y")
    balls = [int(value) for value in balls]
    stars = [int(value) for value in stars]
    if draw_date.weekday() not in (1, 4):
        raise ValueError(f"Date hors mardi/vendredi : {date}")
    if len(balls) != 5 or len(set(balls)) != 5 or not set(balls).issubset(range(1, 51)):
        raise ValueError(f"Boules invalides : {balls}")
    if len(stars) != 2 or len(set(stars)) != 2 or not set(stars).issubset(range(1, 13)):
        raise ValueError(f"Étoiles invalides : {stars}")
    if is_draw_in_csv(date):
        print(f"Le tirage du {date} est déjà présent.")
        return False
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as source:
        width = len(next(csv.reader(source, delimiter=";")))
    row = ["NEW", jour or "UNKNOWN", date, "", "", *balls, *stars, f"-{'-'.join(map(str, sorted(balls)))}", f"-{'-'.join(map(str, sorted(stars)))}"]
    row = (row + [""] * width)[:width]
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as target:
        csv.writer(target, delimiter=";", lineterminator="\n").writerow(row)
    return True

if __name__ == "__main__":
    backup_data()
    result = fetch_latest_draw()
    if result:
        print(f"Dernier tirage trouvé : {result['date']} ({result['jour']}) -> {result['balls']} | {result['stars']}")
        if append_draw_to_csv(result['date'], result['jour'], result['balls'], result['stars']):
            print("✅ Tirage ajouté avec succès.")
        else:
            print("ℹ️ Tirage déjà présent dans la base.")
    else:
        print("❌ Aucun nouveau tirage détecté.")
