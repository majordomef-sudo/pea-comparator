# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
css = open("style.css", encoding="utf-8").read()
add = """
/* B2 - table mobile en cartes + filtres sticky */
@media(max-width:700px){
  .etf-filters{position:sticky;top:0;z-index:20;background:var(--bg,#f8fafc);padding:8px 0}
  #etfTable thead{display:none}
  #etfTable tbody tr{display:block;border:1px solid var(--border);border-radius:10px;margin-bottom:10px;padding:8px 10px}
  #etfTable tbody td{display:flex;justify-content:space-between;align-items:center;border:none;padding:5px 4px;border-bottom:1px solid var(--border)}
  #etfTable tbody td:before{content:attr(data-lab);font-weight:600;color:var(--muted);font-size:.72rem;text-transform:uppercase;margin-right:12px}
  #etfTable tbody tr td:last-child{border-bottom:none}
}
"""
if "B2 - table mobile" not in css:
    css = css + add
    open("style.css", "w", encoding="utf-8").write(css)
    print("CSS B2 ajoute")
else:
    print("CSS B2 deja present")
