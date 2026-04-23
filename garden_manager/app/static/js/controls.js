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
    // Mémorise la dernière commande pour fallback si l'API ne renvoie pas roof_target
    window._lastRoofCommand = state;
    window._lastRoofCommandAt = Date.now();
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

// Récupère la cible "vraie" de la lucarne en mouvement.
// Priorité : roof_target serveur, sinon dernière commande utilisateur (≤60s),
// sinon "open" par défaut (mieux que de toujours afficher "fermeture" à tort).
function getRoofMovingTarget(serverTarget) {
  if (serverTarget === 'open' || serverTarget === 'close') return serverTarget;
  const recent = window._lastRoofCommand
    && (Date.now() - (window._lastRoofCommandAt || 0)) < 60000;
  if (recent) return window._lastRoofCommand;
  return 'open';
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
