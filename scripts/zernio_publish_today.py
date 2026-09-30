import sys, os, json
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace')
key=''
for line in open('/home/ubuntu/.secrets/env'):
    if line.startswith('export ZERNIO_API_KEY='):
        key=line.split('=',1)[1].strip().strip(chr(34)).strip(chr(39)); break
os.environ['ZERNIO_API_KEY']=key
from zernio import Zernio
c=Zernio(api_key=key)

# Lister les 8 derniers posts pour trouver la video du jour (failed tiktok avec media)
posts = c.posts.list(limit=8)
raw = posts.model_dump() if hasattr(posts,'model_dump') else posts
items = raw.get('posts', []) if isinstance(raw, dict) else raw

print('--- POSTS RECENTS ---')
target=None
for p in items:
    if not isinstance(p, dict):
        p = p.model_dump() if hasattr(p,'model_dump') else {}
    pid = p.get('field_id') or p.get('id') or p.get('_id')
    plats = p.get('platforms', []) or []
    st = [ (pl.get('platform'), pl.get('status')) for pl in plats if isinstance(pl, dict) ]
    print(' ', pid, '|', st, '| media:', bool(p.get('mediaItems')))
    # cible: post dont le tiktok a fail et qui a une media video
    if any((pl.get('platform')=='tiktok' and pl.get('status')=='failed') for pl in plats if isinstance(pl, dict)) and p.get('mediaItems'):
        target=p

if not target:
    print('AUCUN POST FAIL TIKTOK AVEC MEDIA - abandon')
    sys.exit(0)

pid = target.get('field_id') or target.get('id') or target.get('_id')
media_url = str(target['mediaItems'][0]['url'])
content = target.get('content') or ''
print()
print('=== PUBLICATION DIRECTE TIKTOK ===')
print('SOURCE:', pid)
print('MEDIA:', media_url[:80])

resp = c.posts.create(
    content=content,
    platforms=[{'platform':'tiktok','accountId':'6a2f0c8e5f7d1751abb33fb3'}],
    media_items=[{'url': media_url, 'type': 'video'}],
    publish_now=True,
    is_draft=False,
)
b = resp.model_dump() if hasattr(resp,'model_dump') else resp
print('RESP_MSG:', b.get('message') if isinstance(b,dict) else resp)
if isinstance(b,dict) and b.get('post'):
    pp=b['post']
    plats = pp.get('platforms', []) if isinstance(pp,dict) else []
    for pl in plats:
        if isinstance(pl,dict):
            print('PLAT:', pl.get('platform'), '|', pl.get('status'), '| err:', (pl.get('errorMessage') or '')[:100])
