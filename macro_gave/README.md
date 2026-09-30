# Pipeline Macro Gave - Documentation

## Vue d ensemble
Pipeline automatise de suivi macroeconomique style Charles Gave.
Detecte les changements de regime economique (Quandrants Q1-Q4), notamment la transition Q2 (croissance+inflation) -> Q3 (recession+inflation / stagflation).

## Architecture (modules independants et remplacables)
DATA SOURCES (Eurostat, BCE SDMX, seed de reference)
  -> DATA COLLECTOR (collector.py + collectors/)
  -> DATA VALIDATOR (validator.py : fraicheur, DATA UNAVAILABLE)
  -> NORMALIZER (normalizer.py : tendances 1/3/6 mois)
  -> MACRO DATABASE (db.py : SQLite append-only)
  -> INDICATOR ENGINE (indicator_engine.py : score 0-100 par indicateur)
  -> SCORING ENGINE (scoring_engine.py : score par categorie + pondere global)
  -> REGIME DETECTOR (regime_detector.py : quadrant Q1-Q4 + confiance)
  -> TRANSITION DETECTOR (transition_detector.py : score 0-100)
  -> ALLOCATION SIGNAL (allocation_signal.py : ANALYTIQUE, jamais d ordre)
  -> REPORT GENERATOR (report_generator.py : rapport texte)
  -> TELEGRAM (telegram_alert.py : alertes anti-spam)
  -> DASHBOARD (dashboard/build_dashboard.py : HTML autonome)

## Installation
python3 -c "from macro_gave import db; db.init_db()"

## Utilisation
python3 -m macro_gave.run_pipeline        # collecte + analyse + rapport + alertes
python3 -m macro_gave.backtest           # test detecteur sur 4 scenarios
python3 -m macro_gave.dashboard.build_dashboard  # genere dashboard/index.html

## Donnees
- data/seed_reference.json : valeurs de reference (checklist Gave juillet 2026).
  ATTENTION : valeurs de reference, a remplacer par les vraies collectes (Eurostat/BCE).
  Editez ce fichier manuellement si la collecte automatique ne trouve rien.
- Ne jamais inventer de donnee : si trop ancienne -> DATA UNAVAILABLE + confiance reduite.

## Configuration
Tous les seuils sont dans config.py (et surchargeables via config.override.json).
Seuils initiaux : PMI 50/48, inflation services 3.5%, transition 25/50/75, poids des categories...

## Alertes Telegram
- Only on : changement de quadrant, +15pts transition, nouveau signal rouge, PMI ou services sous seuil.
- Ne jamais executer d ordre : l allocation est une recommandation analytique.

## Cron (a installer)
Editer crontab -e :
0 10 1 * * cd /home/ubuntu/.openclaw/workspace && python3 -m macro_gave.run_pipeline >> /home/ubuntu/output/logs/macro_gave.log 2>&1

## Evolution
- Ajouter de nouvelles zones (US, Asie) : dupliquer les modules collectors avec d autres sources.
- Les regles du backtest sont stockees separement des parametres optimises.