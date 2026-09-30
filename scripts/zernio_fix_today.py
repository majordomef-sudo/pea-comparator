import sys, os
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace')
key=''
for line in open('/home/ubuntu/.secrets/env'):
    if line.startswith('export ZERNIO_API_KEY='):
        key=line.split('=',1)[1].strip().strip(chr(34)).strip(chr(39)); break
os.environ['ZERNIO_API_KEY']=key
from zernio import Zernio
c=Zernio(api_key=key)

# 1) SUPPRIMER le brouillon en double cree a 17:51 (6a8f279e) - status pending
try:
    r = c.posts.delete('6a8f279efc984f33b0731da8')
    print('DELETE DRAFT:', getattr(r,'message','OK'))
except Exception as e:
    print('DELETE DRAFT ERR:', str(e)[:150])

# 2) RETRY publication DIRECTE du post du jour (6a8f123e) - tiktok avait fail (saturation)
try:
    r = c.posts.retry('6a8f123e63fab5966eee899a')
    print('RETRY_MSG:', getattr(r,'message',r))
    if getattr(r,'post',None):
        for pl in (r.post.platforms or []):
            print('PLAT:', pl.platform, '|', getattr(pl,'status','?'))
except Exception as e:
    print('RETRY ERR:', str(e)[:200])
