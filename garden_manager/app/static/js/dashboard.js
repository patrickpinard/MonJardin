/* Dashboard : graphique Plotly + refresh temps réel */

const ZONE_COLORS = {1: '#30d158', 2: '#8BC34A', 3: '#0a84ff', 4: '#bf5af2'};
const ZONE_NAMES  = {1: 'Serre', 2: 'Soleil', 3: 'Mi-ombre', 4: 'Aromates'};

function plotlyTheme(extra) {
  const dark = (document.documentElement.getAttribute('data-theme') || 'dark') !== 'light';
  const fontColor  = dark ? 'rgba(255,255,255,.55)' : 'rgba(17,19,21,.70)';
  const gridColor  = dark ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.08)';
  const lineColor  = dark ? 'rgba(255,255,255,.10)' : 'rgba(0,0,0,.14)';
  return {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: {color: fontColor, size: 11, family: '-apple-system,BlinkMacSystemFont,system-ui'},
    xaxis: {gridcolor: gridColor, linecolor: lineColor, tickcolor: lineColor, tickformat: '%H:%M\n%d.%m'},
    yaxis: {gridcolor: gridColor, linecolor: lineColor, tickcolor: lineColor},
    legend: {orientation: 'h', y: -0.22, bgcolor: 'transparent', font: {color: fontColor}},
    ...extra,
  };
}

let _chartHours = 24;
// M11 : référence à l'intervalle pour clearInterval au déchargement
let _refreshInterval = null;

function initDashboard() {
  loadCurrentData();
  loadMainChart(_chartHours);
  // Refresh général toutes les 10s (humidité + lucarne)
  _refreshInterval = setInterval(() => {
    loadCurrentData();
    loadMainChart(_chartHours);
    loadJournal();
  }, 10000);
  window.addEventListener('beforeunload', () => {
    if (_refreshInterval) clearInterval(_refreshInterval);
    if (_fastRefreshInterval) clearInterval(_fastRefreshInterval);
  });
}

// Poll rapide (3s) pendant un mouvement de lucarne, sinon désactivé.
let _fastRefreshInterval = null;
function _setFastRefresh(enable) {
  if (enable && !_fastRefreshInterval) {
    _fastRefreshInterval = setInterval(loadCurrentData, 3000);
  } else if (!enable && _fastRefreshInterval) {
    clearInterval(_fastRefreshInterval);
    _fastRefreshInterval = null;
  }
}

// M12 : affichage visuel si les données ne se chargent plus
function _setConnectionBanner(ok) {
  let banner = document.getElementById('_conn-banner');
  if (ok) {
    if (banner) banner.remove();
    return;
  }
  if (!banner) {
    banner = document.createElement('div');
    banner.id = '_conn-banner';
    banner.style.cssText = `position:fixed;top:0;left:0;right:0;z-index:9999;
      background:#ef4444;color:#fff;font-size:13px;font-weight:600;
      text-align:center;padding:6px 12px;letter-spacing:.02em;`;
    banner.textContent = '⚠️ Connexion perdue — données figées';
    document.body.prepend(banner);
  }
}

async function loadCurrentData() {
  try {
    const resp = await fetch('/api/data/current');
    if (!resp.ok) { _setConnectionBanner(false); return; }
    _setConnectionBanner(true);
    updateZoneCards(await resp.json());
  } catch (e) {
    _setConnectionBanner(false);
    console.warn('loadCurrentData erreur:', e);
  }
}

function updateZoneCards(data) {
  const CIRC = 175.9;
  (data.zones || []).forEach(z => {
    const pct = z.soil_moisture_pct;
    const mc  = pct < (z.moisture_threshold_low  || 30) ? 'low'
              : pct > (z.moisture_threshold_high || 65) ? 'high' : 'ok';

    // SVG fill circle
    const fill = document.querySelector(`[data-zone-fill="${z.zone_id}"]`);
    if (fill) {
      fill.setAttribute('stroke-dasharray', `${(pct / 100 * CIRC).toFixed(1)} ${CIRC}`);
      fill.className.baseVal = `g-fill ${mc}`;
    }

    // Gauge center text + moisture value
    document.querySelectorAll(`[data-zone-text="${z.zone_id}"]`).forEach(el => {
      el.textContent = Math.round(pct) + '%';
      if (el.classList.contains('gauge-center')) {
        el.className = `gauge-center ${mc}`;
      } else if (el.classList.contains('moisture-value')) {
        el.className = `moisture-value ${mc}`;
      }
    });

    // Actuateur vanne — valeurs entièrement contrôlées (booléen), pas de XSS
    const valveEl = document.querySelector(`[data-valve-badge="${z.zone_id}"]`);
    if (valveEl) {
      const open = z.valve_state === 'open';
      valveEl.className = `zc-actuator ${open ? 'zc-actuator-on' : 'zc-actuator-off'}`;
      const ico = valveEl.querySelector('.zc-actuator-icon');
      const state = valveEl.querySelector('.zc-actuator-state');
      if (ico)   ico.className   = `bi bi-droplet${open ? '-fill' : ''} zc-actuator-icon`;
      if (state) state.textContent = open ? 'Arrosage actif' : 'Fermée';
    }
    // Alerte sécheresse
    const alertEl = document.getElementById(`alert-${z.zone_id}`);
    if (alertEl) alertEl.style.display = z.is_alerting ? '' : 'none';
  });

  // ── Lucarne (zone serre uniquement) ──────────────────────
  const roofEl = document.querySelector('[data-roof-badge]');
  if (roofEl) {
    const state  = data.roof_state;        // 'open' | 'close' | 'moving'
    const ico    = roofEl.querySelector('.zc-actuator-icon');
    const lbl    = roofEl.querySelector('.zc-actuator-state');
    if (state === 'moving') {
      // Fallback : si serveur ne renvoie pas roof_target, utiliser la dernière commande
      const target = (typeof getRoofMovingTarget === 'function')
        ? getRoofMovingTarget(data.roof_target)
        : (data.roof_target || 'open');
      roofEl.className = 'zc-actuator zc-actuator-moving';
      if (ico) ico.className = 'bi bi-arrow-repeat zc-actuator-icon';
      if (lbl) lbl.textContent = target === 'close' ? 'En cours de fermeture…' : "En cours d'ouverture…";
      // Active le poll rapide (3s) pour bien suivre le mouvement
      _setFastRefresh(true);
    } else if (state === 'open') {
      roofEl.className = 'zc-actuator zc-actuator-roof-on';
      if (ico) ico.className = 'bi bi-wind zc-actuator-icon';
      if (lbl) lbl.textContent = 'Ouverte';
      _setFastRefresh(false);
      // Cleanup mémoire fallback (la commande est terminée côté serveur)
      window._lastRoofCommand = null;
    } else if (state === 'close') {
      roofEl.className = 'zc-actuator zc-actuator-off';
      if (ico) ico.className = 'bi bi-house-fill zc-actuator-icon';
      if (lbl) lbl.textContent = 'Fermée';
      _setFastRefresh(false);
      window._lastRoofCommand = null;
    }
    // Si state est null/undefined : on ne touche pas au badge (évite de figer)
  }

  // Vent mesuré par l'Arduino
  const windEl = document.getElementById('dash-wind-arduino');
  if (windEl && data.wind_speed_kmh != null) {
    windEl.textContent = data.wind_speed_kmh.toFixed(1) + ' km/h';
  }
}

function switchTab(btn, hours) {
  document.querySelectorAll('.time-tabs .time-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadMainChart(hours);
}

async function loadMainChart(hours) {
  _chartHours = hours;
  try {
    const [histResp, eventsResp] = await Promise.all([
      fetch(`/api/data/history?hours=${hours}`),
      fetch(`/api/data/irrigation_events?hours=${hours}`),
    ]);
    if (!histResp.ok) return;
    const hist   = await histResp.json();
    const events = eventsResp.ok ? await eventsResp.json() : {events: []};
    renderMainChart(hist, events);
  } catch (e) {
    console.warn('loadMainChart erreur:', e);
  }
}

function renderMainChart(hist, events) {
  const traces = [];

  for (const [zid, readings] of Object.entries(hist.zones)) {
    const id = +zid;
    traces.push({
      x: readings.map(r => r.timestamp),
      y: readings.map(r => r.soil_moisture_pct),
      type: 'scatter', mode: 'lines',
      name: ZONE_NAMES[id] || `Zone ${id}`,
      line: {color: ZONE_COLORS[id], width: 2},
      yaxis: 'y1',
    });
  }

  const allReadings = Object.values(hist.zones).flat().sort((a, b) =>
    a.timestamp.localeCompare(b.timestamp));
  if (allReadings.length) {
    traces.push({
      x: allReadings.map(r => r.timestamp),
      y: allReadings.map(r => r.temperature_c),
      type: 'scatter', mode: 'lines', name: 'Temp (°C)',
      line: {color: '#ff9f0a', width: 1.5, dash: 'dot'},
      yaxis: 'y2',
    });
  }

  const shapes = (events.events || [])
    .filter(e => e.action === 'open')
    .map(e => ({
      type: 'line', x0: e.timestamp, x1: e.timestamp,
      y0: 0, y1: 1, yref: 'paper',
      line: {color: ZONE_COLORS[e.zone_id] || '#30d158', width: 1, dash: 'dot'},
    }));

  Plotly.react('mainChart', traces, plotlyTheme({
    margin: {t: 6, b: 50, l: 44, r: 52},
    yaxis:  {title: 'Humidité (%)', range: [0, 100]},
    yaxis2: {title: 'Temp (°C)', overlaying: 'y', side: 'right', showgrid: false},
    shapes,
  }), {responsive: true, displayModeBar: false});
}

// C5 : journal reconstruit via DOM — e.message jamais injecté via innerHTML
async function loadJournal() {
  try {
    const resp = await fetch('/api/journal?limit=10');
    if (!resp.ok) return;
    const data = await resp.json();
    const list = document.getElementById('journalList');
    if (!list) return;
    const iconMap = {
      warning: 'exclamation-triangle-fill',
      danger:  'x-circle-fill',
      error:   'x-circle-fill',
      success: 'check-circle-fill',
      info:    'info-circle-fill',
    };
    if (!data.entries || !data.entries.length) {
      list.innerHTML = '<div class="empty-state" style="padding:20px;"><i class="bi bi-journal" style="font-size:28px;display:block;margin-bottom:6px;"></i><p>Aucune entrée.</p></div>';
      return;
    }
    // C5 : DOM API — textContent pour les champs issus de l'Arduino/BD
    const frag = document.createDocumentFragment();
    data.entries.forEach(e => {
      const lvl = e.level in iconMap ? e.level : 'info';
      const ts  = e.timestamp ? e.timestamp.substring(5, 16).replace('T', ' ') : '';

      const item = document.createElement('div');
      item.className = 'journal-item';

      const icon = document.createElement('div');
      icon.className = `j-icon ${lvl}`;
      icon.innerHTML = `<i class="bi bi-${iconMap[lvl]}"></i>`;

      const body = document.createElement('div');
      body.className = 'j-body';

      const msg = document.createElement('div');
      msg.className = 'j-msg';
      msg.textContent = e.message;   // C5 : textContent — jamais innerHTML

      const time = document.createElement('div');
      time.className = 'j-time';
      time.textContent = ts;         // C5 : textContent

      body.appendChild(msg);
      body.appendChild(time);
      item.appendChild(icon);
      item.appendChild(body);
      frag.appendChild(item);
    });
    list.replaceChildren(frag);
  } catch (e) {
    console.warn('loadJournal erreur:', e);
  }
}

// C5 : forecast reconstruit via DOM — h.temperature jamais injecté via innerHTML
async function loadForecast() {
  try {
    const resp = await fetch('/api/weather/forecast');
    if (!resp.ok) return;
    const data  = await resp.json();
    const strip = document.getElementById('forecastStrip');
    if (!strip) return;
    const frag = document.createDocumentFragment();
    (data.forecast || []).slice(0, 24).forEach(h => {
      const dt   = new Date(h.hour);
      const hh   = dt.getHours().toString().padStart(2, '0');
      const rain = h.precip_mm > 0 ? '🌧️' : (h.precip_prob_pct > 40 ? '🌦️' : '☀️');
      const frost= h.frost_risk ? '❄️' : '';
      const temp = parseFloat(h.temperature);   // C5 : forcer number, pas de HTML

      const item = document.createElement('div');
      item.className = 'forecast-item';
      // Valeurs contrôlées (hh = padded number, emojis littéraux, temp = parseFloat)
      item.innerHTML = `<div class="fc-hour">${hh}h</div>
        <div class="fc-icon">${rain}${frost}</div>
        <div class="fc-temp">${isNaN(temp) ? '--' : temp}°</div>
        <div class="fc-rain">${Math.round(h.precip_prob_pct || 0)}%</div>`;
      frag.appendChild(item);
    });
    strip.replaceChildren(frag);
  } catch (e) {
    console.warn('loadForecast erreur:', e);
  }
}
