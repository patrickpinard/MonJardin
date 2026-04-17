/* Dashboard : graphique Plotly + refresh temps réel */

const ZONE_COLORS = {1: '#30d158', 2: '#8BC34A', 3: '#0a84ff', 4: '#bf5af2'};
const ZONE_NAMES  = {1: 'Serre', 2: 'Soleil', 3: 'Mi-ombre', 4: 'Aromates'};

let _chartHours = 24;

function initDashboard() {
  loadCurrentData();
  loadMainChart(_chartHours);
  setInterval(() => {
    loadCurrentData();
    loadMainChart(_chartHours);
    loadJournal();
  }, 30000);
}

async function loadCurrentData() {
  try {
    const resp = await fetch('/api/data/current');
    if (!resp.ok) return;
    updateZoneCards(await resp.json());
  } catch (e) {
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

    // Gauge center text
    const txt = document.querySelector(`[data-zone-text="${z.zone_id}"]`);
    if (txt) {
      txt.textContent = Math.round(pct) + '%';
      txt.className = `gauge-center ${mc}`;
    }

    // Valve badge
    const badge = document.querySelector(`[data-valve-badge="${z.zone_id}"]`);
    if (badge) {
      const open = z.valve_state === 'open';
      badge.className = `badge ${open ? 'badge-valve-open' : 'badge-valve-close'}`;
      badge.innerHTML = `<i class="bi bi-droplet${open ? '-fill' : ''}"></i> ${open ? 'Arrosage' : 'Fermé'}`;
    }
  });

  // Vent mesuré par l'Arduino
  const windEl = document.getElementById('dash-wind-arduino');
  if (windEl && data.wind_speed_kmh != null) {
    windEl.textContent = data.wind_speed_kmh.toFixed(1) + 'km/h';
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
    traces.push({
      x: readings.map(r => r.timestamp),
      y: readings.map(r => r.soil_moisture_pct),
      type: 'scatter', mode: 'lines',
      name: ZONE_NAMES[zid] || `Zone ${zid}`,
      line: {color: ZONE_COLORS[zid], width: 2},
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

  Plotly.react('mainChart', traces, {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: {color: 'rgba(255,255,255,.55)', size: 11, family: '-apple-system,BlinkMacSystemFont,system-ui'},
    margin: {t: 6, b: 50, l: 44, r: 52},
    xaxis: {gridcolor: 'rgba(255,255,255,.06)', tickformat: '%H:%M\n%d.%m', linecolor: 'rgba(255,255,255,.08)'},
    yaxis: {title: 'Humidité (%)', range: [0, 100], gridcolor: 'rgba(255,255,255,.06)', linecolor: 'rgba(255,255,255,.08)'},
    yaxis2: {title: 'Temp (°C)', overlaying: 'y', side: 'right', showgrid: false, linecolor: 'rgba(255,255,255,.08)'},
    legend: {orientation: 'h', y: -0.22, bgcolor: 'transparent'},
    shapes,
  }, {responsive: true, displayModeBar: false});
}

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
    list.innerHTML = data.entries.map(e => {
      const lvl = e.level in iconMap ? e.level : 'info';
      const ts  = e.timestamp ? e.timestamp.substring(5, 16).replace('T', ' ') : '';
      return `<div class="journal-item">
        <div class="j-icon ${lvl}"><i class="bi bi-${iconMap[lvl]}"></i></div>
        <div class="j-body">
          <div class="j-msg">${e.message}</div>
          <div class="j-time">${ts}</div>
        </div>
      </div>`;
    }).join('') || '<div class="empty-state" style="padding:20px;"><i class="bi bi-journal" style="font-size:28px;display:block;margin-bottom:6px;"></i><p>Aucune entrée.</p></div>';
  } catch (e) {
    console.warn('loadJournal erreur:', e);
  }
}

async function loadForecast() {
  try {
    const resp = await fetch('/api/weather/forecast');
    if (!resp.ok) return;
    const data  = await resp.json();
    const strip = document.getElementById('forecastStrip');
    if (!strip) return;
    strip.innerHTML = (data.forecast || []).slice(0, 24).map(h => {
      const dt   = new Date(h.hour);
      const hh   = dt.getHours().toString().padStart(2, '0');
      const rain = h.precip_mm > 0 ? '🌧️' : (h.precip_prob_pct > 40 ? '🌦️' : '☀️');
      const frost= h.frost_risk ? '❄️' : '';
      return `<div class="forecast-item">
        <div class="fc-hour">${hh}h</div>
        <div class="fc-icon">${rain}${frost}</div>
        <div class="fc-temp">${h.temperature}°</div>
        <div class="fc-rain">${Math.round(h.precip_prob_pct || 0)}%</div>
      </div>`;
    }).join('');
  } catch (e) {
    console.warn('loadForecast erreur:', e);
  }
}
