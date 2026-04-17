/* Commandes manuelles : vannes et toit */

async function setValve(zoneId, state) {
  try {
    const resp = await fetch(`/api/control/valve/${zoneId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({state}),
    });
    const data = await resp.json();
    showToast(data.message, data.ok ? 'success' : 'danger');
    if (data.ok && typeof loadCurrentData === 'function') loadCurrentData();
  } catch (e) {
    showToast('Erreur de communication', 'danger');
  }
}

async function setRoof(state) {
  try {
    const resp = await fetch('/api/control/roof', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({state}),
    });
    const data = await resp.json();
    showToast(data.message, data.ok ? 'success' : 'danger');
    if (data.ok && typeof loadCurrentData === 'function') loadCurrentData();
  } catch (e) {
    showToast('Erreur de communication', 'danger');
  }
}

async function forceCycle() {
  try {
    const resp = await fetch('/api/system/force_cycle', {method: 'POST'});
    const data = await resp.json();
    showToast(data.message, 'info');
  } catch (e) {
    showToast('Erreur', 'danger');
  }
}
