/* === Calculator Functions for Alfred Invest === */
/* Note: script.min.js handles: comp-calc, fire-calc, fees-calc, alloc-calc, env-calc */
/* This file handles: catchup-calc, infl-calc, mil-calc, cons-calc, cmp-calc + top ETFs */

(function() {
  'use strict';

  function pf(id) { return parseFloat(document.getElementById(id).value) || 0; }
  function fmt(v) { return v.toLocaleString('fr-FR', {maximumFractionDigits: 2, minimumFractionDigits: 2}) + ' \u20ac'; }
  function fmtPct(v) { return v.toFixed(1) + '%'; }

  function calcCatchup() {
    var target = pf('catchup-target');
    var current = pf('catchup-current');
    var age = pf('catchup-age');
    var retire = pf('catchup-retire');
    var rate = pf('catchup-rate') / 100;
    if (rate <= 0) { document.getElementById('catchup-result').innerHTML = '<span style="color:#dc2626">Rendement doit \u00eatre > 0</span>'; return; }
    var years = retire - age;
    if (years <= 0) { document.getElementById('catchup-result').innerHTML = '<span style="color:#dc2626">\u00c2ge retraite doit \u00eatre > \u00e2ge actuel</span>'; return; }
    var fvFactor = Math.pow(1 + rate, years);
    var needed = target - current * fvFactor;
    if (needed <= 0) {
      document.getElementById('catchup-monthly').textContent = '0,00 \u20ac';
      document.getElementById('catchup-final').textContent = fmt(current * fvFactor);
      return;
    }
    var rMonthly = Math.pow(1 + rate, 1/12) - 1;
    var nMonths = years * 12;
    var monthly = needed * rMonthly / (Math.pow(1 + rMonthly, nMonths) - 1);
    document.getElementById('catchup-monthly').textContent = fmt(monthly);
    document.getElementById('catchup-final').textContent = fmt(target);
  }

  function calcInfl() {
    var amount = pf('infl-amount');
    var rate = pf('infl-rate') / 100;
    var years = pf('infl-years');
    var future = amount * Math.pow(1 + rate, years);
    var loss = future - amount;
    document.getElementById('infl-future').textContent = fmt(future);
    document.getElementById('infl-loss').textContent = fmt(loss);
  }

  function calcMil() {
    var current = pf('mil-current');
    var monthly = pf('mil-monthly');
    var rate = pf('mil-rate') / 100;
    if (rate <= 0) { document.getElementById('mil-result').innerHTML = '<span style="color:#dc2626">Rendement doit \u00eatre > 0</span>'; return; }
    var target = 1000000;
    var years = 0;
    var val = current;
    while (val < target && years < 100) {
      val = val * (1 + rate) + monthly * 12;
      years++;
    }
    document.getElementById('mil-years').textContent = years + ' ans';
    document.getElementById('mil-final').textContent = fmt(val);
  }

  function calcCons() {
    var capital = pf('cons-capital');
    var rate = pf('cons-rate') / 100;
    var years = pf('cons-years');
    if (rate <= 0 || years <= 0) { document.getElementById('cons-result').innerHTML = '<span style="color:#dc2626">Param\u00e8tres invalides</span>'; return; }
    var monthlyRate = rate / 12;
    var n = years * 12;
    var monthly = capital * monthlyRate / (1 - Math.pow(1 + monthlyRate, -n));
    document.getElementById('cons-monthly').textContent = fmt(monthly);
    document.getElementById('cons-yearly').textContent = fmt(monthly * 12);
  }

  function calcCmp() {
    var isin1 = document.getElementById('cmp-isin1').value.trim().toUpperCase();
    var isin2 = document.getElementById('cmp-isin2').value.trim().toUpperCase();
    var etfs = window.PEA_ETFS || [];
    var e1 = etfs.find(function(e) { return e.isin === isin1; });
    var e2 = etfs.find(function(e) { return e.isin === isin2; });
    var html = '';
    if (!e1) html += '<p style="color:#dc2626">ETF ' + isin1 + ' non trouv\u00e9</p>';
    if (!e2) html += '<p style="color:#dc2626">ETF ' + isin2 + ' non trouv\u00e9</p>';
    if (e1 && e2) {
      html = '<table style="width:100%;border-collapse:collapse;font-size:0.85rem">';
      html += '<tr><th style="text-align:left">Crit\u00e8re</th><th style="text-align:center">' + e1.nom + '</th><th style="text-align:center">' + e2.nom + '</th></tr>';
      html += '<tr><td>ISIN</td><td style="text-align:center">' + e1.isin + '</td><td style="text-align:center">' + e2.isin + '</td></tr>';
      html += '<tr><td>Frais</td><td style="text-align:center">' + (e1.frais || '-') + '%</td><td style="text-align:center">' + (e2.frais || '-') + '%</td></tr>';
      html += '<tr><td>SRI</td><td style="text-align:center">' + (e1.sri || '-') + '</td><td style="text-align:center">' + (e2.sri || '-') + '</td></tr>';
      html += '<tr><td>Perf 5A</td><td style="text-align:center">' + (e1.perf5 || '-') + '%</td><td style="text-align:center">' + (e2.perf5 || '-') + '%</td></tr>';
      html += '<tr><td>\u00c9metteur</td><td style="text-align:center">' + (e1.emetteur || '-') + '</td><td style="text-align:center">' + (e2.emetteur || '-') + '</td></tr>';
      html += '</table>';
    }
    document.getElementById('cmp-result').innerHTML = html;
  }

  /* === Top ETF PEA === */
  function getTopETFs() {
    var etfs = window.PEA_ETFS || [];
    if (etfs.length === 0) return;

    var withPerf = etfs.filter(function(e) {
      return e.perf5 !== '' && e.perf5 !== undefined && e.perf5 !== null && e.perf5 !== 'N/A';
    });

    var top6 = withPerf.sort(function(a, b) {
      var pa = parseFloat(String(a.perf5).replace(',', '.'));
      var pb = parseFloat(String(b.perf5).replace(',', '.'));
      return pb - pa;
    }).slice(0, 6);

    var grid = document.getElementById('topEtfsGrid');
    if (!grid) return;

    grid.innerHTML = top6.map(function(e, i) {
      var perf5 = parseFloat(String(e.perf5 || '0').replace(',', '.'));
      var perfStr = (perf5 >= 0 ? '+' : '') + perf5.toFixed(1) + '%';
      var perfUp = perf5 >= 0;
      var frais = e.frais ? parseFloat(String(e.frais).replace(',', '.')).toFixed(2) + '%' : '—';
      var name = e.nom || '';
      var shortName = name.length > 40 ? name.slice(0, 38) + '...' : name;

      return '<div class="top-etf">' +
        '<div class="top-etf-rank">' + (i + 1) + '</div>' +
        '<div style="flex:1">' +
          '<h4>' + shortName + '</h4>' +
          '<p>' + (e.isin || '') + ' \u00b7 Frais: ' + frais + ' \u00b7 Perf: <span style="color:' + (perfUp ? '#059669' : '#dc2626') + ';font-weight:700">' + perfStr + '</span></p>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  /* === Init — only non-conflicting handlers === */
  function initCalcs() {
    document.getElementById('catchup-calc').addEventListener('click', calcCatchup);
    document.getElementById('infl-calc').addEventListener('click', calcInfl);
    document.getElementById('mil-calc').addEventListener('click', calcMil);
    document.getElementById('cons-calc').addEventListener('click', calcCons);
    document.getElementById('cmp-calc').addEventListener('click', calcCmp);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCalcs);
    document.addEventListener('DOMContentLoaded', getTopETFs);
  } else {
    initCalcs();
    getTopETFs();
  }
})();
