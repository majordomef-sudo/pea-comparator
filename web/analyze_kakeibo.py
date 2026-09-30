import os
import json
import requests

# Read the full Kakeibo code
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo-clone/index.html', 'r') as f:
    kakeibo_code = f.read()

# Read PEA Comparator CSS
with open('/home/ubuntu/.openclaw/workspace/web/pea-comparator/index.html', 'r') as f:
    pea_code = f.read()

# Extract PEA CSS
pea_start = pea_code.find('<style>')
pea_end = pea_code.find('</style>')
pea_css = pea_code[pea_start+7:pea_end] if pea_start >= 0 else ''

# Truncate kakeibo code to fit in context (about 100k chars)
# We need head (HTML structure), CSS, and JS structure
lines = kakeibo_code.split('\n')
head = '\n'.join(lines[:2000])
css_start = kakeibo_code.find('<style>')
css_end = kakeibo_code.find('</style>')
css = kakeibo_code[css_start:css_end+8] if css_start >= 0 else ''
# Get first 5000 lines of the script section
script_start = kakeibo_code.find('<script>', css_end) if css_end >= 0 else kakeibo_code.find('<script>')
script = kakeibo_code[script_start:script_start+80000] if script_start >= 0 else ''

# Supabase URL
supabase_match = kakeibo_code.find('supabase.co')
supabase_text = kakeibo_code[max(0,supabase_match-100):supabase_match+100] if supabase_match >= 0 else 'not found'

print(f'Total kakeibo lines: {len(lines)}')
print(f'Total kakeibo chars: {len(kakeibo_code)}')
print(f'Head chars: {len(head)}')
print(f'CSS chars: {len(css)}')
print(f'Script chars: {len(script)}')
print(f'Supabase: {supabase_text}')

# Build the prompt for deepseek
prompt = f'''Tu es un expert en refonte de PWA budget tracker. Analyse ce code Kakeibo (1.3MB, 20k lignes, single HTML PWA) et produis un plan de refonte complet.

## Code source Kakeibo (extrait)

### HEAD (HTML structure, 2000 premieres lignes)
{head[:15000]}

### CSS complet
{css[:5000]}

### JS (début)
{script[:20000]}

### Supabase
{supabase_text}

## Design de référence PEA Comparator (à reproduire)
{pea_css[:3000]}

## INSTRUCTIONS
1. Analyse l'architecture du code (pages, composants, données, auth)
2. Propose un plan de refonte complet pour adapter le site à Eric (France, EUR)
3. Design: dark theme #0a0e1a, gold accents #d4a843, glass cards #131a2e, font Inter, rounded 16px
4. Ajouter un champ "salaire conjoint" dans le profil
5. French: catégories fr, devise EUR, format dates jj/mm/aaaa
6. Donne moi le code CSS complet à remplacer (le nouveau style)
7. Donne les modifications HTML nécessaires pour le salaire conjoint
8. Donne les modifications JS nécessaires

Réponds en JSON structuré avec: css, html_changes, js_changes, analysis'''

print(f'\nPrompt chars: {len(prompt)}')

# Save prompt to file
with open('/tmp/kakeibo_prompt.txt', 'w') as f:
    f.write(prompt)

print('\nPrompt saved to /tmp/kakeibo_prompt.txt')
