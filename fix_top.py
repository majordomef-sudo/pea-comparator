import re
path='top-etf.html'
t=open(path,encoding='utf-8',errors='replace').read()
marker='<div class=etf-decision>'
parts=t.split(marker)
def lab(s):
    if s is None: return '—'
    if s>=74: return 'Très bon'
    if s>=64: return 'Bon'
    if s>=54: return 'Moyen'
    if s>=44: return 'Faible'
    return 'Très faible'
def last_score(seg):
    i=seg.rfind('/100</div>')
    if i<0: return None
    k=seg.rfind('>',0,i)
    try: return int(seg[k+1:i].strip())
    except: return None
out=[parts[0]]
for p in parts[1:]:
    sc=last_score(out[-1])
    end=p.find('</div>')
    out.append(marker+' '+lab(sc)+p[end:])
open(path,'w',encoding='utf-8').write(''.join(out))
print('Vendre:', ''.join(out).count('Vendre'))
