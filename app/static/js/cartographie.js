/* Carte des habitants — agrégation par quartier (Leaflet auto-hébergé).
 * Aucun domicile individuel n'est affiché : une bulle par quartier, dont la
 * taille reflète le nombre d'habitants localisés. Les données viennent de
 * l'endpoint JSON /quartiers/carte/data (filtrable secteur/public/année).
 */
(function () {
  "use strict";

  var el = document.getElementById("carte-habitants");
  if (!el || typeof L === "undefined") return;

  var cfg = {
    dataUrl: el.getAttribute("data-data-url"),
    tileUrl: el.getAttribute("data-tile-url"),
    tileAttr: el.getAttribute("data-tile-attr"),
    lat: parseFloat(el.getAttribute("data-centre-lat")) || 49.2583,
    lon: parseFloat(el.getAttribute("data-centre-lon")) || 2.475,
  };

  var map = L.map(el, { scrollWheelZoom: true }).setView([cfg.lat, cfg.lon], 13);
  L.tileLayer(cfg.tileUrl, { maxZoom: 19, attribution: cfg.tileAttr }).addTo(map);

  var layer = L.layerGroup().addTo(map);
  var infoEl = document.getElementById("carte-info");

  function rayon(total, max) {
    // Surface ~ effectif : rayon proportionnel à la racine carrée.
    var r = 8 + Math.sqrt(total) * 4;
    return Math.max(10, Math.min(46, r));
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function ventilation(titre, obj) {
    var keys = Object.keys(obj || {});
    if (!keys.length) return "";
    var lignes = keys
      .slice(0, 6)
      .map(function (k) {
        return "<li>" + escapeHtml(k) + " : <strong>" + obj[k] + "</strong></li>";
      })
      .join("");
    return "<div class='carte-pop-sec'><div class='muted'>" + titre + "</div><ul>" + lignes + "</ul></div>";
  }

  function dessiner(data) {
    layer.clearLayers();
    var quartiers = (data && data.quartiers) || [];
    var maxTotal = quartiers.reduce(function (m, q) {
      return Math.max(m, q.total);
    }, 1);

    var bounds = [];
    quartiers.forEach(function (q) {
      if (q.lat == null || q.lon == null) return;
      var couleur = q.is_qpv ? "#d9534f" : "#2a6fb0";
      var marker = L.circleMarker([q.lat, q.lon], {
        radius: rayon(q.total, maxTotal),
        color: couleur,
        weight: 2,
        fillColor: couleur,
        fillOpacity: 0.45,
      });
      var titre = escapeHtml(q.nom) + (q.ville ? " <span class='muted'>(" + escapeHtml(q.ville) + ")</span>" : "");
      if (q.is_qpv) titre += " <span class='carte-qpv'>QPV</span>";
      var html =
        "<div class='carte-pop'><div class='carte-pop-titre'>" + titre + "</div>" +
        "<div class='carte-pop-total'>" + q.total + " habitant(s) localisé(s)</div>" +
        ventilation("Par secteur", q.par_secteur) +
        ventilation("Par public", q.par_type_public) +
        "</div>";
      marker.bindPopup(html);
      marker.bindTooltip(String(q.total), {
        permanent: true,
        direction: "center",
        className: "carte-count",
      });
      marker.addTo(layer);
      bounds.push([q.lat, q.lon]);
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }

    if (infoEl) {
      var loc = data.localises || 0;
      var non = data.non_localises || 0;
      var tot = data.total || 0;
      infoEl.innerHTML =
        "<strong>" + loc + "</strong> localisé(s) sur " + tot + " · " +
        "<strong>" + non + "</strong> non localisé(s) (adresse manquante ou non géocodée)";
    }
  }

  function params() {
    var p = new URLSearchParams();
    ["secteur", "type_public", "annee"].forEach(function (name) {
      var sel = document.getElementById("carte-" + name);
      if (sel && sel.value) p.set(name, sel.value);
    });
    return p.toString();
  }

  function charger() {
    var url = cfg.dataUrl + (params() ? "?" + params() : "");
    if (infoEl) infoEl.textContent = "Chargement…";
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(dessiner)
      .catch(function (e) {
        if (infoEl) infoEl.textContent = "Erreur de chargement des données (" + e.message + ").";
      });
  }

  ["secteur", "type_public", "annee"].forEach(function (name) {
    var sel = document.getElementById("carte-" + name);
    if (sel) sel.addEventListener("change", charger);
  });

  charger();
})();
