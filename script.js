/* === script.js — Comparateur ETF PEA === */

(function () {
  'use strict';

  const PER_PAGE = 50;
  const ROWS = window.PEA_ETFS || [];

  // État
  const state = {
    filtered: [],
    page: 1,
    sortCol: null,
    sortAsc: true,
  };

  // Références DOM
  const tbody = document.getElementById('etfBody');
  const pagination = document.getElementById('pagination');
  const resultCount = document.getElementById('resultCount');
  const searchInput = document.getElementById('search');
  const feesMinInput = document.getElementById('feesMin');
  const feesMaxInput = document.getElementById('feesMax');
  const sriSelect = document.getElementById('sri');
  const emetteurSelect = document.getElementById('emetteur');
  const resetBtn = document.getElementById('resetFilters');
  const toast = document.getElementById('toast');

  // Remplir le select des émetteurs
  function populateEmetteurs() {
    const counts = {};
    ROWS.forEach(e => {
      if (e.emetteur) counts[e.emetteur] = (counts[e.emetteur] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    sorted.forEach(([name, count]) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = `${name} (${count})`;
      emetteurSelect.appendChild(opt);
    });
  }
  populateEmetteurs();

  // Helper : parse les nombres au format français (virgule → point)
  function parseNum(v) {
    if (v === "" || v === undefined || v === null) return NaN;
    return parseFloat(String(v).replace(",", "."));
  }

  // === FILTRES ===
  function applyFilters() {
    const search = searchInput.value.trim().toLowerCase();
    const feesMin = parseFloat(feesMinInput.value);
    const feesMax = feesMaxInput.value !== '' ? parseFloat(feesMaxInput.value) : null;
    const sri = sriSelect.value;
    const emetteur = emetteurSelect.value;

    let filtered = ROWS;

    // Recherche textuelle
    if (search) {
      filtered = filtered.filter(e =>
        e.isin.toLowerCase().includes(search) ||
        e.nom.toLowerCase().includes(search) ||
        (e.emetteur && e.emetteur.toLowerCase().includes(search))
      );
    }

    // Frais min
    if (!isNaN(feesMin)) {
      filtered = filtered.filter(e => {
        const f = parseNum(e.frais);
        return e.frais !== '' && !isNaN(f) && f >= feesMin;
      });
    }

    // Frais max
    if (feesMax !== null && !isNaN(feesMax)) {
      filtered = filtered.filter(e => {
        const f = parseNum(e.frais);
        return e.frais !== '' && !isNaN(f) && f <= feesMax;
      });
    }

    // SRI
    if (sri) {
      filtered = filtered.filter(e => e.sri === sri);
    }

    // Émetteur
    if (emetteur) {
      filtered = filtered.filter(e => e.emetteur === emetteur);
    }

    state.filtered = filtered;
    state.page = 1;

    // Tri si une colonne est active
    if (state.sortCol) {
      sortData(state.sortCol, state.sortAsc);
    } else {
      render();
    }
  }

  // Debounce
  let debounceTimer;
  function debouncedFilter(delay) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyFilters, delay || 200);
  }

  // === TRI ===
  function sortData(col, asc) {
    state.filtered.sort((a, b) => {
      let va = a[col];
      let vb = b[col];

      if (col === 'frais' || col === 'perf5') {
        const na = va !== '' ? parseNum(va) : (col === 'frais' ? 999 : -999);
        const nb = vb !== '' ? parseNum(vb) : (col === 'frais' ? 999 : -999);
        return asc ? na - nb : nb - na;
      }

      if (col === 'sri') {
        const na = va !== '' ? parseInt(va, 10) : 0;
        const nb = vb !== '' ? parseInt(vb, 10) : 0;
        return asc ? na - nb : nb - na;
      }

      // String
      va = (va || '').toString().toLowerCase();
      vb = (vb || '').toString().toLowerCase();
      if (va < vb) return asc ? -1 : 1;
      if (va > vb) return asc ? 1 : -1;
      return 0;
    });

    render();
  }

  function handleSort(col) {
    if (state.sortCol === col) {
      state.sortAsc = !state.sortAsc;
    } else {
      state.sortCol = col;
      state.sortAsc = true;
    }
    sortData(col, state.sortAsc);
    updateSortIndicators(col);
  }

  function updateSortIndicators(col) {
    document.querySelectorAll('#etfTable thead th.sortable').forEach(th => {
      const c = th.dataset.col;
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (c === col) {
        th.classList.add(state.sortAsc ? 'sorted-asc' : 'sorted-desc');
      }
    });
  }

  // === PAGINATION ===
  function render() {
    const total = state.filtered.length;
    const totalPages = Math.ceil(total / PER_PAGE) || 1;
    const page = Math.min(state.page, totalPages);

    const start = (page - 1) * PER_PAGE;
    const pageData = state.filtered.slice(start, start + PER_PAGE);

    // Résultats
    resultCount.textContent = total;

    // Corps du tableau
    if (pageData.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:#999;">Aucun ETF trouvé. Essayez de modifier vos filtres.</td></tr>';
    } else {
      tbody.innerHTML = pageData.map(e => {
        const frais = e.frais !== '' ? parseNum(e.frais).toFixed(2) + '%' : '—';
        const sri = e.sri || '—';
        const perf5 = e.perf5 !== '' ? parseNum(e.perf5).toFixed(1) + '%' : '—';
        let perfClass = 'perf-neutral';
        if (e.perf5 !== '') {
          const pv = parseNum(e.perf5);
          if (pv > 0) perfClass = 'perf-positive';
          else if (pv < 0) perfClass = 'perf-negative';
        }
        const fraisClass = e.frais !== '' ? 'frais-vert' : '';

        return `<tr data-isin="${e.isin}">
          <td>${e.isin}</td>
          <td>${e.nom}</td>
          <td class="${fraisClass}">${frais}</td>
          <td>${sri}</td>
          <td class="${perfClass}">${perf5}</td>
          <td>${e.emetteur || '—'}</td>
          <td>${e.pays || '—'}</td>
          <td><span class="badge-pea">PEA</span></td>
          <td><a href="https://www.justetf.com/fr/etf-profile.html?isin=${e.isin}" target="_blank" rel="noopener" class="dic-link" title="Voir le DIC sur justETF">📄</a></td>
        </tr>`;
      }).join('');
    }

    // Pagination
    renderPagination(page, totalPages);

    // Attacher le clic pour copier ISIN
    tbody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', function () {
        tbody.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));
        this.classList.add('selected');
        const isin = this.dataset.isin;
        if (isin) copyISIN(isin);
      });
    });
  }

  function renderPagination(page, totalPages) {
    if (totalPages <= 1) {
      pagination.innerHTML = '';
      return;
    }

    let html = '';

    // Prev
    html += `<button class="page-btn" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>←</button>`;

    // Pages
    const range = 3;
    const start = Math.max(1, page - range);
    const end = Math.min(totalPages, page + range);

    if (start > 1) {
      html += `<button class="page-btn" data-page="1">1</button>`;
      if (start > 2) html += `<span class="page-dots">…</span>`;
    }

    for (let i = start; i <= end; i++) {
      html += `<button class="page-btn${i === page ? ' active' : ''}" data-page="${i}">${i}</button>`;
    }

    if (end < totalPages) {
      if (end < totalPages - 1) html += `<span class="page-dots">…</span>`;
      html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
    }

    // Next
    html += `<button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>→</button>`;

    pagination.innerHTML = html;

    // Événements
    pagination.querySelectorAll('.page-btn:not(:disabled)').forEach(btn => {
      btn.addEventListener('click', () => {
        const p = parseInt(btn.dataset.page, 10);
        if (p >= 1 && p <= totalPages) {
          state.page = p;
          render();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    });
  }

  // === COPIER ISIN ===
  function copyISIN(isin) {
    if (!navigator.clipboard) {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = isin;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta);
      showToast();
      return;
    }
    navigator.clipboard.writeText(isin).then(showToast).catch(() => {});
  }

  let toastTimer;
  function showToast() {
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 2000);
  }

  // === ÉVÉNEMENTS ===
  searchInput.addEventListener('input', () => debouncedFilter(300));
  feesMinInput.addEventListener('input', () => debouncedFilter(300));
  feesMaxInput.addEventListener('input', () => debouncedFilter(300));
  sriSelect.addEventListener('change', applyFilters);
  emetteurSelect.addEventListener('change', applyFilters);

  resetBtn.addEventListener('click', () => {
    searchInput.value = '';
    feesMinInput.value = '';
    feesMaxInput.value = '';
    sriSelect.value = '';
    emetteurSelect.value = '';
    state.sortCol = null;
    state.sortAsc = true;
    updateSortIndicators(null);
    applyFilters();
  });

  // Tri clic sur entêtes
  document.querySelectorAll('#etfTable thead th.sortable').forEach(th => {
    th.addEventListener('click', () => handleSort(th.dataset.col));
  });

  // === CALCULATEURS ===
  function formatEuro(v) {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v);
  }

  // Tab switching
  document.querySelectorAll('.calc-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.calc-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.calc-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
  });

  // Compound interest
  document.getElementById('comp-calc').addEventListener('click', () => {
    const init = +document.getElementById('comp-init').value || 0;
    const monthly = +document.getElementById('comp-monthly').value || 0;
    const rate = +document.getElementById('comp-rate').value / 100 || 0;
    const years = +document.getElementById('comp-years').value || 0;
    const months = years * 12;
    const r = rate / 12;

    let capital = init;
    let invested = init;
    const halfTarget = (init + monthly * months) / 2;
    let foundHalf = false;
    let foundWorkYear = false;
    let workYear = 0;

    for (let m = 1; m <= months; m++) {
      capital = (capital + monthly) * (1 + r);
      invested += monthly;

      if (!foundHalf && capital >= halfTarget) {
        foundHalf = true;
        document.getElementById('comp-half').textContent = formatEuro(capital) + ' (mois ' + m + ', ~' + (m/12).toFixed(1) + ' ans)';
      }

      // Check when annual return > annual contributions
      if (!foundWorkYear && m % 12 === 0) {
        const yearlyReturn = capital * rate;
        const yearlyContrib = monthly * 12;
        if (yearlyReturn >= yearlyContrib) {
          foundWorkYear = true;
          workYear = m / 12;
          document.getElementById('comp-work-year').textContent = 'Année ' + workYear;
        }
      }
    }

    const gain = capital - invested;
    document.getElementById('comp-final').textContent = formatEuro(capital);
    document.getElementById('comp-invested').textContent = formatEuro(invested);
    document.getElementById('comp-gain').textContent = formatEuro(gain);

    if (!foundHalf) document.getElementById('comp-half').textContent = 'Atteint après la période';
    if (!foundWorkYear) document.getElementById('comp-work-year').textContent = 'Pas encore atteint';
  });

  // FIRE calculator
  document.getElementById('fire-calc').addEventListener('click', () => {
    const income = +document.getElementById('fire-income').value || 0;
    const rate = +document.getElementById('fire-rate').value / 100 || 0.04;
    const current = +document.getElementById('fire-current').value || 0;
    const save = +document.getElementById('fire-save').value || 0;
    const ret = +document.getElementById('fire-return').value / 100 || 0.07;

    const target = (income * 12) / rate;
    document.getElementById('fire-target').textContent = formatEuro(target);

    // Calculate years to reach target
    let years = 0;
    let cap = current;
    const r = ret;
    while (cap < target && years < 100) {
      cap = cap * (1 + r) + save * 12;
      years++;
    }

    const age = 26 + years;
    document.getElementById('fire-time').textContent = years < 100 ? years + ' ans' : '> 100 ans';
    document.getElementById('fire-age').textContent = years < 100 ? age + ' ans' : '—';
    document.getElementById('fire-estimate').textContent = formatEuro(cap);
  });

  // Fee impact calculator with chart
  function calculateFees() {
    const init = +document.getElementById('fees-init').value || 0;
    const monthly = +document.getElementById('fees-monthly').value || 0;
    const rate = +document.getElementById('fees-rate').value / 100 || 0;
    const years = +document.getElementById('fees-years').value || 0;
    const months = years * 12;

    function simulateWithHistory(fee) {
      const r = (rate - fee) / 12;
      let cap = init;
      const data = [{ year: 0, value: cap }];
      for (let m = 1; m <= months; m++) {
        cap = (cap + monthly) * (1 + r);
        if (m % 12 === 0) {
          data.push({ year: m / 12, value: cap });
        }
      }
      return data;
    }

    const d0 = simulateWithHistory(0);
    const dLow = simulateWithHistory(0.005);
    const dMid = simulateWithHistory(0.01);
    const dHigh = simulateWithHistory(0.015);

    const r0 = d0[d0.length - 1].value;
    const rLow = dLow[dLow.length - 1].value;
    const rMid = dMid[dMid.length - 1].value;
    const rHigh = dHigh[dHigh.length - 1].value;

    document.getElementById('fees-none').textContent = formatEuro(r0);
    document.getElementById('fees-low').textContent = formatEuro(rLow);
    document.getElementById('fees-mid').textContent = formatEuro(rMid);
    document.getElementById('fees-high').textContent = formatEuro(rHigh);

    // Draw chart
    drawFeeChart(d0, dLow, dMid, dHigh, years);
  }

  function drawFeeChart(d0, dLow, dMid, dHigh, years) {
    const canvas = document.getElementById('fees-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 700;
    const h = canvas.clientHeight || 350;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const pad = { top: 20, right: 20, bottom: 40, left: 70 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    let maxVal = 0;
    [d0, dLow, dMid, dHigh].forEach(s => s.forEach(d => { if (d.value > maxVal) maxVal = d.value; }));

    function toX(year) { return pad.left + (year / years) * plotW; }
    function toY(val) { return pad.top + plotH - (val / maxVal) * plotH; }

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#fafafa';
    ctx.fillRect(pad.left, pad.top, plotW, plotH);

    // Grid
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    for (let y = 0; y <= 4; y++) {
      const val = (maxVal / 4) * y;
      const yy = toY(val);
      ctx.beginPath();
      ctx.moveTo(pad.left, yy);
      ctx.lineTo(w - pad.right, yy);
      ctx.stroke();
      ctx.fillStyle = '#999';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText(formatEuro(val), pad.left - 8, yy + 4);
    }

    ctx.fillStyle = '#999';
    ctx.font = '11px system-ui';
    ctx.textAlign = 'center';
    for (let y = 0; y <= years; y += Math.max(1, Math.floor(years / 6))) {
      ctx.fillText(y + 'a', toX(y), h - pad.bottom + 16);
    }

    const series = [
      { data: d0, color: '#2ecc71', label: '0%' },
      { data: dLow, color: '#f39c12', label: '0,50%' },
      { data: dMid, color: '#e74c3c', label: '1,00%' },
      { data: dHigh, color: '#c0392b', label: '1,50%' },
    ];

    series.forEach(s => {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      s.data.forEach((d, i) => {
        const x = toX(d.year);
        const y = toY(d.value);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      const last = s.data[s.data.length - 1];
      ctx.fillStyle = s.color;
      ctx.font = 'bold 12px system-ui';
      ctx.textAlign = 'left';
      ctx.fillText(s.label, toX(last.year) + 6, toY(last.value) + 4);
    });

    ctx.fillStyle = '#333';
    ctx.font = 'bold 13px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Écart selon les frais de gestion', w / 2, 14);
  }

  document.getElementById('fees-calc').addEventListener('click', calculateFees);

  // Allocation recommandée
  const ALLOCATIONS = {
    offensif: {
      name: '⚔️ Offensif (10-30 ans)',
      etfs: [
        { label: 'MSCI World (42%)', isin: 'FR001400U5Q4', ticker: 'DCAM', pct: 42 },
        { label: 'MSCI EM IMI (7%)', isin: 'IE00BKM4GZ66', ticker: 'IS3N', pct: 7 },
        { label: 'MSCI World Small Cap (3%)', isin: 'IE00B4RFH31', ticker: 'IUSN', pct: 3 },
        { label: 'MSCI World Quality (5%)', isin: 'IE00BQN1K786', ticker: 'CEMR', pct: 5 },
        { label: 'Nasdaq-100 (4%)', isin: 'LU182922024', ticker: 'PUST', pct: 4 },
        { label: 'Or physique (10%)', isin: 'FR0013416716', ticker: 'GOLD', pct: 10 },
        { label: 'Obligations agg. (5%)', isin: 'IE00BDBRDM35', ticker: 'EUN4', pct: 5 },
        { label: 'Crypto Basket (5%)', isin: 'CH0445689208', ticker: 'HODL', pct: 5 },
        { label: 'SCPI (10%)', isin: '—', ticker: 'EN AV', pct: 10 },
        { label: 'Fonds daté (5%)', isin: 'FR001400MCQ6', ticker: '2030', pct: 5 },
        { label: 'Private Equity (4%)', isin: 'FR0013202108', ticker: 'NEXT', pct: 4 },
      ],
      perf: 10.78,
      ter: 0.28,
    },
    equilibre: {
      name: '⚖️ Équilibré (5-15 ans)',
      etfs: [
        { label: 'MSCI World (35%)', isin: 'FR001400U5Q4', ticker: 'DCAM', pct: 35 },
        { label: 'MSCI EM IMI (5%)', isin: 'IE00BKM4GZ66', ticker: 'IS3N', pct: 5 },
        { label: 'S&P 500 (10%)', isin: 'FR0010755611', ticker: 'ESE', pct: 10 },
        { label: 'Or physique (10%)', isin: 'FR0013416716', ticker: 'GOLD', pct: 10 },
        { label: 'Obligations agg. (10%)', isin: 'IE00BDBRDM35', ticker: 'EUN4', pct: 10 },
        { label: 'Monétaire (10%)', isin: 'FR0010754209', ticker: 'CSH', pct: 10 },
        { label: 'SCPI (10%)', isin: '—', ticker: 'EN AV', pct: 10 },
        { label: 'Crypto (3%)', isin: 'CH0445689208', ticker: 'HODL', pct: 3 },
        { label: 'Fonds daté (7%)', isin: 'FR001400MCQ6', ticker: '2030', pct: 7 },
      ],
      perf: 8.5,
      ter: 0.35,
    },
    defensif: {
      name: '🛡️ Défensif (0-5 ans)',
      etfs: [
        { label: 'MSCI World (15%)', isin: 'FR001400U5Q4', ticker: 'DCAM', pct: 15 },
        { label: 'Obligations agg. (25%)', isin: 'IE00BDBRDM35', ticker: 'EUN4', pct: 25 },
        { label: 'Monétaire (25%)', isin: 'FR0010754209', ticker: 'CSH', pct: 25 },
        { label: 'Or (10%)', isin: 'FR0013416716', ticker: 'GOLD', pct: 10 },
        { label: 'Fonds daté (15%)', isin: 'FR001400MCQ6', ticker: '2030', pct: 15 },
        { label: 'SCPI (5%)', isin: '—', ticker: 'EN AV', pct: 5 },
        { label: 'Fonds € (5%)', isin: '—', ticker: 'EN AV', pct: 5 },
      ],
      perf: 5.2,
      ter: 0.45,
    },
  };

  document.getElementById('alloc-calc').addEventListener('click', () => {
    const profile = document.getElementById('alloc-profile').value;
    const monthly = +document.getElementById('alloc-monthly').value || 0;
    const init = +document.getElementById('alloc-init').value || 0;
    const country = document.getElementById('alloc-country').value;

    const alloc = ALLOCATIONS[profile];
    document.getElementById('alloc-count').textContent = alloc.etfs.length + ' ETF / Fonds';

    // Build pie text
    const pieParts = alloc.etfs.map(e => e.label).join(' · ');
    document.getElementById('alloc-pie').textContent = pieParts;

    document.getElementById('alloc-ter').textContent = alloc.ter.toFixed(2) + '%';
    document.getElementById('alloc-perf').textContent = alloc.perf.toFixed(1) + '% / an';

    // ETF list with ISIN
    const etfLines = alloc.etfs.map(e => e.label + ' (' + e.pct + '%)' + (e.isin !== '—' ? ' → ' + e.isin : ' → via AV')).join('\n');
    document.getElementById('alloc-etfs').textContent = etfLines;
  });

  // PEA vs AV vs CTO comparator with chart
  function calculateEnveloppe() {
    const init = +document.getElementById('env-init').value || 0;
    const monthly = +document.getElementById('env-monthly').value || 0;
    const gross = +document.getElementById('env-rate').value / 100 || 0;
    const years = +document.getElementById('env-years').value || 0;
    const months = years * 12;

    // Simulate each enveloppe year by year
    function simulate(taxOnGain, yearlyFee, taxFreeAllowance) {
      let cap = init;
      let totalInvested = init;
      let yearlyData = [];
      yearlyData.push({ year: 0, value: cap, invested: totalInvested });

      for (let y = 1; y <= years; y++) {
        // Monthly contributions + growth
        for (let m = 0; m < 12; m++) {
          cap = (cap + monthly) * (1 + (gross - yearlyFee) / 12);
          totalInvested += monthly;
        }
        // Apply tax on gains at year end (after 5 years for PEA, 8 for AV)
        if (y >= 5) {
          // Only tax the gain portion
        }
        yearlyData.push({ year: y, value: cap, invested: totalInvested });
      }

      // Final tax calculation
      const gain = cap - totalInvested;
      let netGain = gain;

      if (taxOnGain > 0) {
        // PEA: 17.2% PS on gains (no IR) after 5 years
        // AV: 7.5% on gains after 8 years (with allowance)
        // CTO: 30% flat on gains
        let taxableGain = gain;
        if (taxFreeAllowance > 0) {
          taxableGain = Math.max(0, gain - taxFreeAllowance);
        }
        netGain = gain - taxableGain * taxOnGain;
      }

      return { net: totalInvested + netGain, gross: cap, invested: totalInvested, data: yearlyData };
    }

    // PEA: 17.2% PS on gains after 5 years
    const pea = simulate(0.172, 0.002, 0);
    // AV: 7.5% + ~0.75% fees/year, allowance 4600€/yr
    const av = simulate(0.075, 0.0075, 4600);
    // CTO: 30% PFU flat on gains
    const cto = simulate(0.30, 0.002, 0);

    document.getElementById('env-pea').textContent = formatEuro(pea.net);
    document.getElementById('env-av').textContent = formatEuro(av.net);
    document.getElementById('env-cto').textContent = formatEuro(cto.net);

    // Winner
    const vals = [
      { name: 'PEA', val: pea.net, emoji: '💼' },
      { name: 'AV', val: av.net, emoji: '📜' },
      { name: 'CTO', val: cto.net, emoji: '📈' },
    ];
    vals.sort((a, b) => b.val - a.val);
    document.getElementById('env-winner').innerHTML = vals[0].emoji + ' ' + vals[0].name + ' (' + formatEuro(vals[0].val) + ')';

    // Render chart
    drawEnveloppeChart(pea.data, av.data, cto.data, years);
  }

  function drawEnveloppeChart(peaData, avData, ctoData, years) {
    const canvas = document.getElementById('env-chart');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 700;
    const h = canvas.clientHeight || 350;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const pad = { top: 20, right: 20, bottom: 40, left: 70 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    // Find max value across all series
    let maxVal = 0;
    [peaData, avData, ctoData].forEach(s => s.forEach(d => { if (d.value > maxVal) maxVal = d.value; }));

    function toX(year) { return pad.left + (year / years) * plotW; }
    function toY(val) { return pad.top + plotH - (val / maxVal) * plotH; }

    // Clear
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#fafafa';
    ctx.fillRect(pad.left, pad.top, plotW, plotH);

    // Grid lines
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    for (let y = 0; y <= 4; y++) {
      const val = (maxVal / 4) * y;
      const yy = toY(val);
      ctx.beginPath();
      ctx.moveTo(pad.left, yy);
      ctx.lineTo(w - pad.right, yy);
      ctx.stroke();
      ctx.fillStyle = '#999';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText(formatEuro(val), pad.left - 8, yy + 4);
    }

    // X labels
    ctx.fillStyle = '#999';
    ctx.font = '11px system-ui';
    ctx.textAlign = 'center';
    for (let y = 0; y <= years; y += Math.max(1, Math.floor(years / 6))) {
      ctx.fillText(y + 'a', toX(y), h - pad.bottom + 16);
    }

    // Draw series
    const series = [
      { data: peaData, color: '#2ecc71', label: 'PEA' },
      { data: avData, color: '#3498db', label: 'AV' },
      { data: ctoData, color: '#e67e22', label: 'CTO' },
    ];

    series.forEach(s => {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      s.data.forEach((d, i) => {
        const x = toX(d.year);
        const y = toY(d.value);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Label at end
      const last = s.data[s.data.length - 1];
      ctx.fillStyle = s.color;
      ctx.font = 'bold 12px system-ui';
      ctx.textAlign = 'left';
      ctx.fillText(s.label, toX(last.year) + 6, toY(last.value) + 4);
    });

    // Title
    ctx.fillStyle = '#333';
    ctx.font = 'bold 13px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Évolution du capital selon l\'enveloppe fiscale', w / 2, 14);
  }

  document.getElementById('env-calc').addEventListener('click', calculateEnveloppe);

  // Auto-calc on enter
  document.querySelectorAll('.calc-inputs input').forEach(inp => {
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const panel = inp.closest('.calc-panel');
        if (panel) {
          const btn = panel.querySelector('.calc-btn');
          if (btn) btn.click();
        }
      }
    });
  });

  // === INIT ===
  state.filtered = [...ROWS];
  render();

  // Auto-run calculators on load
  setTimeout(() => {
    document.getElementById('comp-calc').click();
    // Also trigger enveloppe chart for immediate preview
    if (document.getElementById('env-chart')) {
      calculateEnveloppe();
    }
  }, 100);

  // === NEW FEATURES ===

  // 1. Dark mode toggle
  const darkToggle = document.getElementById('darkToggle');
  if (darkToggle) {
    // Check saved preference
    if (localStorage.getItem('pea-dark') === 'true') {
      document.body.classList.add('dark-mode');
      darkToggle.textContent = '☀️';
    }
    darkToggle.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      const isDark = document.body.classList.contains('dark-mode');
      darkToggle.textContent = isDark ? '☀️' : '🌙';
      localStorage.setItem('pea-dark', isDark);
    });
  }

  // 2. Top 10 ETF click → copy ISIN
  document.querySelectorAll('.top10-card').forEach(card => {
    card.addEventListener('click', function () {
      const isin = this.dataset.isin;
      if (isin) copyISIN(isin);
    });
  });

  // 3. Email capture (localStorage mock)
  const emailForm = document.getElementById('emailForm');
  if (emailForm) {
    emailForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('emailInput').value.trim();
      if (!email) return;

      // Store locally (in production: POST to API)
      const subscribers = JSON.parse(localStorage.getItem('pea-subscribers') || '[]');
      if (!subscribers.includes(email)) {
        subscribers.push(email);
        localStorage.setItem('pea-subscribers', JSON.stringify(subscribers));
      }

      document.getElementById('emailForm').style.display = 'none';
      document.getElementById('emailSuccess').style.display = 'block';
    });
  }

  // 4. FAQ accordion
  document.querySelectorAll('.faq-question').forEach(q => {
    q.addEventListener('click', function () {
      const item = this.parentElement;
      const wasOpen = item.classList.contains('open');
      // Close all
      document.querySelectorAll('.faq-item').forEach(f => f.classList.remove('open'));
      // Toggle current
      if (!wasOpen) item.classList.add('open');
    });
  });

  // 5. Comparateur 2 ETF
  let selectedETFs = [];

  // Click on ETF table row → toggle selection
  function setupCompareClicks() {
    document.querySelectorAll('#etfBody tr').forEach(tr => {
      tr.removeEventListener('click', handleCompareClick);
      tr.addEventListener('click', handleCompareClick);
    });
  }

  function handleCompareClick() {
    const isin = this.dataset.isin;
    if (!isin) return;

    // Find ETF data
    const etf = ROWS.find(e => e.isin === isin);
    if (!etf) return;

    const idx = selectedETFs.findIndex(s => s.isin === isin);
    if (idx >= 0) {
      // Deselect
      selectedETFs.splice(idx, 1);
      this.classList.remove('selected');
    } else {
      if (selectedETFs.length >= 2) {
        // Remove oldest
        const old = selectedETFs.shift();
        document.querySelector(`#etfBody tr[data-isin="${old.isin}"]`)?.classList.remove('selected');
      }
      selectedETFs.push(etf);
      this.classList.add('selected');
    }

    updateComparePanel();
  }

  function updateComparePanel() {
    const empty = document.getElementById('compare-empty');
    const wrap = document.getElementById('compare-table-wrap');
    const body = document.getElementById('cmp-body');

    if (selectedETFs.length < 2) {
      empty.style.display = 'block';
      wrap.style.display = 'none';
      return;
    }

    empty.style.display = 'none';
    wrap.style.display = 'block';

    const a = selectedETFs[0];
    const b = selectedETFs[1];

    document.getElementById('cmp-name-1').textContent = a.nom + ' (' + a.isin + ')';
    document.getElementById('cmp-name-2').textContent = b.nom + ' (' + b.isin + ')';

    const rows = [
      { label: 'ISIN', v1: a.isin, v2: b.isin },
      { label: 'Nom', v1: a.nom, v2: b.nom },
      { label: 'Frais (TER)', v1: a.frais ? a.frais + '%' : '—', v2: b.frais ? b.frais + '%' : '—' },
      { label: 'SRI (Risque)', v1: a.sri || '—', v2: b.sri || '—' },
      { label: 'Perf 5 ans', v1: a.perf5 ? a.perf5 + '%' : '—', v2: b.perf5 ? b.perf5 + '%' : '—' },
      { label: 'Émetteur', v1: a.emetteur || '—', v2: b.emetteur || '—' },
      { label: 'Pays', v1: a.pays || '—', v2: b.pays || '—' },
    ];

    body.innerHTML = rows.map(r => {
      // Highlight the lower fees, higher perf, lower risk
      let class1 = '';
      let class2 = '';
      if (r.label === 'Frais (TER)' && a.frais && b.frais) {
        const f1 = parseNum(a.frais);
        const f2 = parseNum(b.frais);
        if (!isNaN(f1) && !isNaN(f2)) {
          class1 = f1 < f2 ? 'frais-vert' : '';
          class2 = f2 < f1 ? 'frais-vert' : '';
        }
      }
      if (r.label === 'Perf 5 ans' && a.perf5 && b.perf5) {
        const p1 = parseNum(a.perf5);
        const p2 = parseNum(b.perf5);
        if (!isNaN(p1) && !isNaN(p2)) {
          class1 = p1 > p2 ? 'perf-positive' : '';
          class2 = p2 > p1 ? 'perf-positive' : '';
        }
      }
      return `<tr><td>${r.label}</td><td class="${class1}">${r.v1}</td><td class="${class2}">${r.v2}</td></tr>`;
    }).join('');

    // Show savings comparison
    const savings = document.getElementById('cmp-savings');
    if (a.frais && b.frais) {
      const f1 = parseNum(a.frais);
      const f2 = parseNum(b.frais);
      if (!isNaN(f1) && !isNaN(f2) && f1 !== f2) {
        const diff = Math.abs(f1 - f2).toFixed(2);
        const lower = f1 < f2 ? a.nom : b.nom;
        savings.textContent = '💡 ' + lower + ' est ' + diff + '% moins cher en frais';
      } else {
        savings.textContent = '';
      }
    }

    document.getElementById('cmp-affiliate').style.display = 'inline-block';
  }

  document.getElementById('cmp-clear')?.addEventListener('click', () => {
    selectedETFs = [];
    document.querySelectorAll('#etfBody tr.selected').forEach(r => r.classList.remove('selected'));
    updateComparePanel();
  });

  // Override render to attach compare clicks
  const originalRender = render;
  render = function () {
    originalRender();
    setupCompareClicks();
    // Re-highlight selected rows
    selectedETFs.forEach(s => {
      const tr = document.querySelector(`#etfBody tr[data-isin="${s.isin}"]`);
      if (tr) tr.classList.add('selected');
    });
  };

  // 6. Open first FAQ on load
  setTimeout(() => {
    const firstFaq = document.querySelector('.faq-item');
    if (firstFaq) firstFaq.classList.add('open');
  }, 500);

})();