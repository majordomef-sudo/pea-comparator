/* quadrant.js - Rend l'etat macro (quadrant Gave) sur le site.
   Donnees : quadrant.json, regenere par macro_gave/export_site.py a chaque run.
   Aucun appel externe, aucune donnee personnelle, aucun ordre. */
(function () {
  "use strict";
  var cible = document.getElementById("quadrant-macro");
  if (!cible) return;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function classeAxe(d) {
    if (!d) return "";
    var c = d.classe || "";
    if (c === "haut") return "qm-haut";
    if (c === "bas") return "qm-bas";
    return "qm-neutre";
  }

  function lireAxe(nom, d) {
    if (!d) return "";
    var fl = { haut: "au-dessus", bas: "en dessous", neutre: "dans la bande" }[d.classe] || d.classe;
    return '<div class="qm-axe ' + classeAxe(d) + '">' +
      '<div class="qm-axe-tete"><strong>' + esc(nom) + '</strong>' +
      '<span class="qm-axe-tag">' + esc(fl) + '</span></div>' +
      '<div class="qm-axe-val">' + esc(d.valeur) + '<small> vs ' + esc(d.moyenne_7a) +
      ' de moyenne 7 ans</small></div>' +
      '<div class="qm-axe-meta">ecart ' + esc(d.ecart_pp) + ' pp - ' + esc(d.periode) + (d.age_jours != null ? ' - J+' + esc(d.age_jours) : '') + '</div>' +
      '</div>';
  }

  function carteQuadrant(code, d, courant) {
    if (!d) return "";
    var actif = (code === courant) ? " qm-actif" : "";
    var lvl = d.level ? ' qm-lvl-' + esc(d.level) : "";
    var fav = Array.isArray(d.favorise) ? d.favorise.join(", ") : "";
    return '<div class="qm-case' + actif + lvl + '">' +
      '<div class="qm-case-tete"><span class="qm-code">' + esc(code) + '</span>' +
      '<span class="qm-nom">' + esc(d.nom) + '</span></div>' +
      '<div class="qm-case-axes">croissance ' + esc(d.croissance) +
      ' - inflation ' + esc(d.inflation) + '</div>' +
      (fav ? '<div class="qm-case-fav">Favorise : ' + esc(fav) + '</div>' : '') +
      (actif ? '<div class="qm-case-badge">Regime actuel</div>' : '') +
      '</div>';
  }

  function nettoyer(msg) {
    return String(msg || "")
      .replace(/ANALYTIQUE uniquement[^.]*\./gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  fetch("quadrant.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
    .then(function (d) {
      var q = d.quadrant || "?";
      var cases = "";
      var ordre = ["Q1", "Q2", "Q3", "Q4"];
      for (var i = 0; i < ordre.length; i++) {
        cases += carteQuadrant(ordre[i], d.quadrants ? d.quadrants[ordre[i]] : null, q);
      }
      var alloc = d.allocation || {};
      var html =
        '<div class="qm-bandeau">' +
          '<div class="qm-pastille qm-lvl-' + esc(d.allocation && d.allocation.level) + '">' + esc(q) + '</div>' +
          '<div class="qm-bandeau-txt"><strong>' + esc(d.nom) + '</strong>' +
          '<span>Confiance ' + esc(d.confidence) + '/100' +
          (d.zone_indecise ? ' - zone neutre : quadrant precedent conserve' : '') + '</span></div>' +
          '<div class="qm-bandeau-scores"><span>Global <strong>' + esc(d.global) + '</strong>/100</span>' +
          '<span>Transition <strong>' + esc(d.transition) + '</strong>/100 (' + esc(d.transition_label) + ')</span></div>' +
        '</div>' +
        '<div class="qm-grille">' + cases + '</div>' +
        '<div class="qm-axes">' + lireAxe("Croissance", d.axes && d.axes.croissance) +
          lireAxe("Inflation", d.axes && d.axes.inflation) + '</div>' +
        (alloc.message ? '<div class="qm-alloc"><strong>Lecture du regime</strong><p>' +
          esc(nettoyer(alloc.message)) + '</p></div>' : '') +
        (d.fraicheur && d.fraicheur.perime ?
          '<div class="qm-alerte"><strong>Donnees anciennes.</strong> ' + esc(d.fraicheur.message) + '</div>' : '') +
        '<div class="qm-pied">Mis a jour le ' + esc(d.updated) + ' UTC - ' +
          (d.fraicheur && d.fraicheur.age_max_jours != null ? 'donnee la plus ancienne : J+' + esc(d.fraicheur.age_max_jours) + ' - ' : '') +
          esc(d.methode) + '</div>';
      cible.innerHTML = html;
    })
    .catch(function () {
      cible.innerHTML = '<p class="qm-loading">Etat macro momentanement indisponible.</p>';
    });
})();
