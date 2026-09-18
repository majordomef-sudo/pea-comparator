// Banner to confirm script loaded
(function() {
  var banner = document.createElement('div');
  banner.id = 'alfred-banner';
  banner.textContent = '✅ Script chargé';
  banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#16a34a;color:white;text-align:center;padding:6px;z-index:99999;font-size:13px;font-family:monospace';
  document.body.insertBefore(banner, document.body.firstChild);
  
  // Compound interest calculator
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('#comp-calc');
    if (!btn) return;
    e.preventDefault();
    
    var init = document.getElementById('comp-init');
    var monthly = document.getElementById('comp-monthly');
    var rate = document.getElementById('comp-rate');
    var years = document.getElementById('comp-years');
    var final = document.getElementById('comp-final');
    var invested = document.getElementById('comp-invested');
    var gain = document.getElementById('comp-gain');
    
    if (!init || !final) return;
    
    var iv = parseFloat(init.value) || 0;
    var mo = parseFloat(monthly.value) || 0;
    var rt = parseFloat(rate.value) / 100 || 0;
    var yr = parseInt(years.value) || 0;
    var ms = yr * 12, r = rt / 12, cap = iv, inv = iv;
    for (var m = 0; m < ms; m++) { cap = (cap + mo) * (1 + r); inv += mo; }
    
    final.textContent = Math.round(cap).toLocaleString('fr-FR') + ' €';
    if (invested) invested.textContent = Math.round(inv).toLocaleString('fr-FR') + ' €';
    if (gain) gain.textContent = Math.round(cap - inv).toLocaleString('fr-FR') + ' €';
    
    banner.textContent = '✅ Calcul: ' + Math.round(cap).toLocaleString('fr-FR') + ' €';
    banner.style.background = '#0d9488';
    setTimeout(function() { banner.style.background = '#16a34a'; banner.textContent = '✅ Script chargé'; }, 3000);
  });
  
  // Tool card toggle
  document.addEventListener('click', function(e) {
    var hdr = e.target.closest('.tool-card-header');
    if (hdr) {
      var card = hdr.closest('.tool-card');
      if (card) card.classList.toggle('open');
    }
  });
})();
