import re

# Read the full file
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo-clone/index.html', 'r') as f:
    html = f.read()

# 1. Change lang from en to fr
html = html.replace('lang="en"', 'lang="fr"', 1)

# 2. Replace the CSS with dark theme
new_css = '''<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root{color-scheme:only dark;}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
html,body{background:#0a0e1a;color:#e8e0d0;font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;height:100%;overflow:hidden;}
.app{display:flex;flex-direction:column;height:100vh;height:-webkit-fill-available;background:#0a0e1a;max-width:430px;margin:0 auto;position:relative;}
.scroll{flex:1;overflow-y:auto;padding:8px 16px 0;padding-bottom:calc(72px + max(8px,env(safe-area-inset-bottom)));-webkit-overflow-scrolling:touch;}
.scroll::-webkit-scrollbar{display:none;}
.page{display:none;}.page.active{display:block;}
@keyframes kkConfettiFall{0%{transform:translateY(0) translateX(0) rotate(0deg);opacity:1;}100%{transform:translateY(105vh) translateX(var(--kk-drift)) rotate(540deg);opacity:0;}}
@keyframes kkSlideFromRight{from{transform:translateX(30px);opacity:.35}to{transform:translateX(0);opacity:1}}
@keyframes kkSlideFromLeft{from{transform:translateX(-30px);opacity:.35}to{transform:translateX(0);opacity:1}}
.tab-bar{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:430px;display:flex;align-items:center;justify-content:space-around;padding:10px 0;padding-bottom:max(10px,env(safe-area-inset-bottom));border-top:1px solid rgba(212,168,67,0.15);background:#0d1225;z-index:300;}
.tab{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;cursor:pointer;padding:6px 12px;border-radius:16px;transition:background 0.18s;}
.tab.active{background:rgba(212,168,67,0.2);padding:6px 18px;}
.tab-lbl{font-size:9px;color:#d4a843;letter-spacing:0.03em;text-transform:uppercase;font-weight:700;display:none;}
.tab.active .tab-lbl{display:block;}
.tab-ico{display:flex;align-items:center;justify-content:center;transition:transform 0.22s cubic-bezier(0.34,1.45,0.6,1);}
.tab-ico svg{width:32px;height:32px;}
.tab.active .tab-ico{transform:translateY(-2px) scale(1.1);}
.tab.active .tab-ico svg path, .tab.active .tab-ico svg line, .tab.active .tab-ico svg rect, .tab.active .tab-ico svg circle, .tab.active .tab-ico svg polyline, .tab.active .tab-ico svg polygon{stroke:#d4a843!important;fill:none;}
.tab.active .tab-ico svg [fill="#a89e95"]{fill:#d4a843!important;}
.page{display:none;padding-top:8px;}.page.active{display:block;}
#pageStats{padding-top:18px;}
.date-lbl{font-size:9px;color:#6b7280;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:3px;}
.total-big{font-size:38px;font-weight:700;color:#d4a843;letter-spacing:-1.5px;line-height:1;}
.total-big .curr{font-size:18px;color:#d4a843;font-weight:400;opacity:0.7;}
.delta{font-size:12px;margin:2px 0 2px;}
.delta.up{color:#34d399;}.delta.down{color:#ef4444;}.delta.flat{color:#6b7280;}
.overlay-row{display:flex;gap:6px;margin-bottom:10px;}
.overlay-btn{background:#131a2e;border:1px solid rgba(212,168,67,0.2);border-radius:20px;padding:5px 12px;font-size:11px;color:#9ca3af;cursor:pointer;}
.overlay-btn.on-inc{border-color:#34d399;color:#34d399;background:rgba(52,211,153,0.1);}
.overlay-btn.on-exp{border-color:#ef4444;color:#ef4444;background:rgba(239,68,68,0.1);}
.chart-wrap{width:100%;height:140px;margin-bottom:12px;}
.sec{font-size:10px;color:#6b7280;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;margin-top:6px;}
.acc-card{background:#131a2e;border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:14px 16px;margin-bottom:10px;}
.summary-card{flex:1;background:#131a2e;border:1px solid rgba(255,255,255,0.06);border-radius:18px;padding:12px 13px;}
.cash-card{background:#131a2e;border:1px solid rgba(255,255,255,0.06);border-radius:18px;padding:14px 16px;margin-bottom:12px;}
.month-nav{display:flex;align-items:center;background:#131a2e;border:1px solid rgba(255,255,255,0.06);border-radius:14px;overflow:hidden;}
.form-section{background:#131a2e;border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:16px;margin-bottom:12px;}
.modal{background:#131a2e;border:1px solid rgba(212,168,67,0.2);border-radius:24px;padding:22px;width:100%;max-width:390px;max-height:86vh;overflow-y:auto;}
.modal-btn{flex:1;padding:13px;border:none;border-radius:14px;font-size:14px;font-weight:700;cursor:pointer;}
.modal-btn.cancel{background:#1a2240;color:#9ca3af;border:1.5px solid rgba(255,255,255,0.08);}
.modal-btn.confirm{background:#d4a843;color:#0a0e1a;}
.sheet{position:fixed;bottom:-100%;left:50%;transform:translateX(-50%);width:100%;max-width:430px;background:#131a2e;border-radius:24px 24px 0 0;padding:16px 20px;z-index:600;transition:bottom 0.34s cubic-bezier(0.32,0.72,0,1);}
/* Keep all other CSS classes - just override colors */
.acc-card{background:#131a2e;color:#e8e0d0;}
.acc-card .card-title{color:#d4a843;}
input,select,textarea{background:#0d1225;color:#e8e0d0;border:1px solid rgba(212,168,67,0.2);border-radius:12px;padding:10px 14px;font-size:14px;font-family:'Inter',sans-serif;}
input:focus,select:focus,textarea:focus{border-color:#d4a843;outline:none;}
button{font-family:'Inter',sans-serif;}
</style>'''

# Replace the CSS (from <style> to </style>)
css_start = html.find('<style>')
css_end = html.find('</style>', css_start) + 8
if css_start >= 0 and css_end > css_start:
    html = html[:css_start] + new_css + html[css_end:]

# 3. Add spouse salary field in account info section
# Find the account info name fields
spouse_salary_html = '''
      <div style="margin-top:16px;">
        <div class="date-lbl" style="margin-bottom:6px;font-size:12px;color:#d4a843;">Revenu conjoint (€)</div>
        <div style="display:flex;align-items:center;gap:8px;">
          <input type="number" id="acctInfoSpouseSalary" oninput="saveSpouseSalary()" placeholder="0" min="0" step="100" style="width:140px;text-align:center;padding:10px;border:2px solid rgba(212,168,67,0.2);border-radius:12px;font-size:18px;font-weight:700;color:#d4a843;outline:none;background:#0d1225;">
          <span style="font-size:16px;font-weight:600;color:#6b7280;">€ / mois</span>
        </div>
        <div style="font-size:10px;color:#6b7280;margin-top:4px;">Le revenu du conjoint sera cumulé au vôtre pour le budget 50/30/20</div>
      </div>'''

# Insert after the email field (around acctInfoEmail)
email_end = html.find('acctInfoEmail')
if email_end >= 0:
    # Find the end of the email div
    email_div_end = html.find('</div>', email_end)
    if email_div_end >= 0:
        email_div_end = html.find('</div>', email_div_end + 1)
        if email_div_end >= 0:
            html = html[:email_div_end+6] + spouse_salary_html + html[email_div_end+6:]

# 4. Add JS for spouse salary
spouse_js = '''
// Spouse salary
function saveSpouseSalary(){
  const val = parseFloat(document.getElementById('acctInfoSpouseSalary').value) || 0;
  try { window.__kkRealLocalStorage.setItem('kk_spouseSalary', String(val)); } catch(e){}
}'''

# Insert after saveAccountName function
save_func_end = html.find('function saveAccountName()')
if save_func_end >= 0:
    # Find the closing brace of saveAccountName
    func_end = html.find('\n}', save_func_end)
    if func_end >= 0:
        func_end = html.find('\n}', func_end + 1)
        if func_end >= 0:
            html = html[:func_end+1] + spouse_js + html[func_end+1:]

# 5. Load spouse salary on account info page load
load_code = '''
  document.getElementById('acctInfoSpouseSalary').value = (window.__kkRealLocalStorage && window.__kkRealLocalStorage.getItem('kk_spouseSalary')) || '0';'''

# Insert after the existing load code for account info
acct_load = html.find("document.getElementById('acctInfoFirstName').value")
if acct_load >= 0:
    first_line_end = html.find('\n', acct_load)
    if first_line_end >= 0:
        html = html[:first_line_end+1] + load_code + html[first_line_end+1:]

# 6. Add spouse salary to the 50/30/20 calculation
# Find the default data profile
profile_data = html.find("month_spending_budget:0")
if profile_data >= 0:
    # Add spouseSalary:0 right after
    html = html[:profile_data] + "spouseSalary:0, " + html[profile_data:]

# Save the modified file
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo-clone/index.html', 'w') as f:
    f.write(html)

print('Refactoring complete!')
print(f'New file size: {len(html)} chars')
