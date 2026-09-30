# Read the original file
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo-clone/index.html', 'r') as f:
    html = f.read()

# 1. Change lang from en to fr
html = html.replace('lang="en"', 'lang="fr"', 1)

# 2. Add dark theme overrides at the end of the existing CSS
# Find the closing </style> tag and insert dark overrides before it
css_end = html.find('</style>')
if css_end >= 0:
    dark_overrides = '''
/* ── Dark Theme Overrides (PEA Comparator inspired) ──────────────── */
html,body{background:#0a0e1a!important;color:#e8e0d0!important;}
.app{background:#0a0e1a!important;}
.tab-bar{background:#0d1225!important;border-top:1px solid rgba(212,168,67,0.15)!important;}
.tab.active{background:rgba(212,168,67,0.2)!important;}
.tab-lbl{color:#d4a843!important;}
.tab.active .tab-ico svg path,.tab.active .tab-ico svg line,.tab.active .tab-ico svg rect,.tab.active .tab-ico svg circle,.tab.active .tab-ico svg polyline,.tab.active .tab-ico svg polygon{stroke:#d4a843!important;fill:none!important;}
.tab.active .tab-ico svg [fill="#a89e95"]{fill:#d4a843!important;}
.acc-card,.summary-card,.cash-card,.form-section,.month-nav{background:#131a2e!important;border:1px solid rgba(255,255,255,0.06)!important;}
.modal{background:#131a2e!important;border:1px solid rgba(212,168,67,0.2)!important;}
.sheet{background:#131a2e!important;}
.total-big{color:#d4a843!important;}
.total-big .curr{color:#d4a843!important;opacity:0.7!important;}
.date-lbl{color:#6b7280!important;}
.delta.up{color:#34d399!important;}
.delta.down{color:#ef4444!important;}
.delta.flat{color:#6b7280!important;}
.overlay-btn{background:#131a2e!important;border-color:rgba(212,168,67,0.2)!important;color:#9ca3af!important;}
.overlay-btn.on-inc{border-color:#34d399!important;color:#34d399!important;background:rgba(52,211,153,0.1)!important;}
.overlay-btn.on-exp{border-color:#ef4444!important;color:#ef4444!important;background:rgba(239,68,68,0.1)!important;}
.modal-btn.cancel{background:#1a2240!important;color:#9ca3af!important;border-color:rgba(255,255,255,0.08)!important;}
.modal-btn.confirm{background:#d4a843!important;color:#0a0e1a!important;}
input,select,textarea{background:#0d1225!important;color:#e8e0d0!important;border-color:rgba(212,168,67,0.2)!important;}
input:focus,select:focus,textarea:focus{border-color:#d4a843!important;}
.sec{color:#6b7280!important;}
'''
    html = html[:css_end] + dark_overrides + html[css_end:]

# 3. Add spouse salary field in account info section
# Find the account info verified div
verified_div = html.find('acctInfoVerified')
if verified_div >= 0:
    # Find the end of the verified div
    verified_end = html.find('</div>', verified_div)
    verified_end = html.find('</div>', verified_end + 1)
    verified_end = html.find('</div>', verified_end + 1)
    if verified_end >= 0:
        spouse_html = '''
      <div style="margin-top:16px;">
        <div class="date-lbl" style="font-size:12px;color:#d4a843;margin-bottom:6px;letter-spacing:0.05em;text-transform:uppercase;">Revenu conjoint (€)</div>
        <div style="display:flex;align-items:center;gap:8px;">
          <input type="number" id="acctInfoSpouseSalary" oninput="saveSpouseSalary()" placeholder="0" min="0" step="100" style="width:140px;text-align:center;padding:10px;border:2px solid rgba(212,168,67,0.2);border-radius:12px;font-size:18px;font-weight:700;color:#d4a843;outline:none;background:#0d1225;">
          <span style="font-size:16px;font-weight:600;color:#6b7280;">€ / mois</span>
        </div>
        <div style="font-size:10px;color:#6b7280;margin-top:4px;">Le revenu du conjoint sera cumulé au vôtre pour le budget 50/30/20</div>
      </div>'''
        html = html[:verified_end+6] + spouse_html + html[verified_end+6:]

# 4. Add JS for spouse salary
save_func = html.find('function saveAccountName()')
if save_func >= 0:
    func_end = html.find('}', save_func)
    func_end = html.find('}', func_end + 1)
    if func_end >= 0:
        spouse_js = '''

function saveSpouseSalary(){
  const val = parseFloat(document.getElementById('acctInfoSpouseSalary').value) || 0;
  try { window.__kkRealLocalStorage.setItem('kk_spouseSalary', String(val)); } catch(e){}
}'''
        html = html[:func_end+1] + spouse_js + html[func_end+1:]

# 5. Load spouse salary on account info page
load_line = html.find("document.getElementById('acctInfoFirstName').value")
if load_line >= 0:
    line_end = html.find('\n', load_line)
    if line_end >= 0:
        load_code = '\n  document.getElementById("acctInfoSpouseSalary").value = (window.__kkRealLocalStorage&&window.__kkRealLocalStorage.getItem("kk_spouseSalary")) || "0";'
        html = html[:line_end+1] + load_code + html[line_end+1:]

# 6. Add spouseSalary to default data
profile_data = html.find('month_spending_budget:0')
if profile_data >= 0:
    html = html[:profile_data] + 'spouseSalary:0, ' + html[profile_data:]

# Save
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo-clone/index.html', 'w') as f:
    f.write(html)

print('Refactoring v2 complete!')
print(f'New file size: {len(html)} chars')
