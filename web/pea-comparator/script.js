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

  // Fee impact calculator
  document.getElementById('fees-calc').addEventListener('click', () => {
    const init = +document.getElementById('fees-init').value || 0;
    const monthly = +document.getElementById('fees-monthly').value || 0;
    const rate = +document.getElementById('fees-rate').value / 100 || 0;
    const years = +document.getElementById('fees-years').value || 0;
    const months = years * 12;

    function simulate(fee) {
      const r = (rate - fee) / 12;
      let cap = init;
      for (let m = 0; m < months; m++) {
        cap = (cap + monthly) * (1 + r);
      }
      return cap;
    }

    const r0 = simulate(0);
    const rLow = simulate(0.005);
    const rMid = simulate(0.01);
    const rHigh = simulate(0.015);

    document.getElementById('fees-none').textContent = formatEuro(r0);
    document.getElementById('fees-low').textContent = formatEuro(rLow);
    document.getElementById('fees-mid').textContent = formatEuro(rMid);
    document.getElementById('fees-high').textContent = formatEuro(rHigh);
  });

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
  }, 100);

})();