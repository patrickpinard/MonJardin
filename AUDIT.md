# AUDIT — MonJardin
**Date** : 2026-04-21  
**Auditeur** : Claude Sonnet 4.6 (rôle auditeur senior embarqué + web)  
**Périmètre** : Firmware Arduino Edge Control + Application Raspberry Pi (Flask)  
**Méthodologie** : Lecture seule, analyse statique, croisement des deux composants

---

## 1. Résumé exécutif

MonJardin est un système de gestion automatisée de jardin composé d'un firmware Arduino Edge Control (C++/ArduinoJson, REST embarqué) et d'une application Raspberry Pi (Python/Flask, SQLite, APScheduler). Les deux communiquent via HTTP/WiFi sur réseau local.

L'architecture est globalement saine : le mode simulation est bien isolé, la logique de décision (irrigation, toit) est correctement séparée des couches d'accès, et le mode WAL de SQLite est activé. Cependant, **5 vulnérabilités critiques** requièrent une attention immédiate avant tout déploiement en production :

- Côté Arduino : le serveur REST embarqué accepte des requêtes HTTP sans limite de taille (épuisement SRAM possible), le watchdog matériel est configuré mais jamais alimenté, et une boucle busy-wait gèle le firmware 2 secondes par requête.
- Côté Raspberry : la `SECRET_KEY` Flask a une valeur par défaut triviale contrefaisable, et le frontend injecte des données non sanitisées via `innerHTML` (XSS).

---

## 2. Tableau des findings — trié par sévérité

### 🔴 Critique (5)

| # | Composant | Catégorie | Fichier:ligne | Problème | Impact |
|---|-----------|-----------|---------------|----------|--------|
| C1 | Arduino | Buffers / Mémoire | `RestServer.cpp:31` | `client.readStringUntil('\n')` sans limite de longueur. Un attaquant ou une trame corrompue peut envoyer une ligne infiniment longue, épuisant la SRAM (32 KB) jusqu'au crash ou comportement indéfini. | Crash Arduino → vannes et lucarne sans contrôle ; redémarrage forcé par watchdog sans log |
| C2 | Arduino | Blocage | `RestServer.cpp:19` | Busy-wait `while (!client.available() && millis()-t < 2000)` sans `delay(1)`. Le firmware est gelé à 100% CPU pendant jusqu'à 2 s par requête HTTP. Pendant ce temps : pas de lecture capteurs, pas de mise à jour du watchdog, pas de commande d'urgence possible. | Perte de réactivité totale 2 s/requête ; watchdog non alimenté → reset si plusieurs requêtes consécutives |
| C3 | Arduino | Watchdog | `main.cpp` / `utils/Watchdog.h` | `WATCHDOG_TIMEOUT_MS = 8000` défini (`config.h:77`) mais `watchdog.feed()` absent de la boucle principale `loop()`. Le watchdog est configuré mais jamais "nourri" → en cas de blocage (ex: WiFi lent), il ne peut pas déclencher de reset protecteur ; en cas de fonctionnement normal, le firmware se reset toutes les 8 s. | Comportement non déterministe : soit reset périodique intempestif, soit absence de protection en cas de blocage réel |
| C4 | Raspberry | Sécurité | `config.py:9` | `SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "monjardin-dev-secret")`. Valeur par défaut publiquement connue (visible dans le repo). Si `FLASK_SECRET_KEY` n'est pas défini en production, les cookies de session Flask sont signés avec cette clé triviale → contrefaçon de session possible. | Usurpation d'identité admin, accès au panel `/admin`, commande des vannes et de la lucarne |
| C5 | Frontend | Sécurité / XSS | `dashboard.js:162`, `dashboard.js:185` | `innerHTML` alimenté par `e.message` (journal système, origin Arduino via `/api/arduino/log`) et `h.temperature` (données météo externes). Si l'Arduino est compromis ou si l'API météo retourne une valeur malformée, du HTML/JS arbitraire est exécuté dans le navigateur de l'utilisateur. | XSS persistant : vol de session, commande des actionneurs depuis le navigateur de l'admin |

---

### 🟠 Majeur (14)

| # | Composant | Catégorie | Fichier:ligne | Problème | Impact |
|---|-----------|-----------|---------------|----------|--------|
| M1 | Arduino | Mémoire | `RestServer.cpp:125` | Concaténation `String(msg) + "..."` répétée sur Arduino. Chaque `+` alloue/libère de la mémoire dynamique ; après des heures de fonctionnement la heap se fragmente et les allocations échouent silencieusement. | Crashs aléatoires après plusieurs heures de fonctionnement ; difficile à diagnostiquer |
| M2 | Arduino | Buffers | `RestServer.cpp:138–146` | Timeout de lecture du body HTTP (`2000 ms`) non réinitialisé à chaque byte reçu. Une connexion lente ou un payload envoyé en plusieurs paquets TCP laisse le body tronqué sans erreur visible. | Commande vanne/toit reçue partiellement → action non exécutée ou JSON malformé ignoré |
| M3 | Arduino | Blocage | `RestServer.cpp:35` | Lecture des headers HTTP (`while(client.available())`) sans timeout explicite par ligne. Si le client envoie des headers sans `\r\n` final, la boucle ne se termine jamais. | Hang permanent du firmware sur une requête malformée |
| M4 | Raspberry | Sécurité | Aucun fichier | Aucune protection CSRF sur les routes POST (formulaires admin, `/api/control/*`). Flask n'utilise pas Flask-WTF ni de token CSRF manuel. Un site tiers peut forcer le navigateur de l'admin à ouvrir une vanne. | Commande non autorisée des actionneurs depuis un site externe |
| M5 | Raspberry | Validation | `routes_api.py:84` | `hours = min(int(...), 720)` — une valeur négative (ex: `?hours=-5`) passe la validation. `datetime.utcnow() - timedelta(hours=-5)` produit une date **future** ; la requête retourne silencieusement zéro résultats. | Confusion utilisateur ; requête API invalide indétectable |
| M6 | Raspberry | Validation | `routes_api.py:81` | `zone_id` passé en query string pour `/api/data/history` n'est pas validé dans `[1..4]`. `zone_id=999` retourne une réponse vide sans erreur 400. | API peu robuste ; difficile à déboguer côté client |
| M7 | Raspberry | Erreur | `routes_api.py:146–148` | L'exception lors de la persistance d'une commande vanne est catchée et loguée, mais `success` reste `True` dans la réponse JSON. L'utilisateur reçoit `{"ok": true}` alors que le log en base a échoué. | Divergence entre état affiché et état réel ; données d'historique incomplètes |
| M8 | Raspberry | Threads | `routes_api.py:336–343` | `force_cycle()` crée un `threading.Thread` à chaque appel sans lock. 10 clics en 1 s → 10 cycles parallèles écrivent simultanément dans `sensor_readings`. | Doublons en base, décisions d'arrosage redondantes, commandes valve multiples |
| M9 | Raspberry | Code | `scheduler.py:37` et ~20 occurrences | `datetime.utcnow()` est deprecated depuis Python 3.12 et sera supprimé dans une future version. | Rupture de compatibilité lors d'une montée de version Python |
| M10 | Cohérence | Timestamps | `main.cpp:90` vs `scheduler.py:37` | Arduino envoie `uptime_s` = secondes depuis le boot (relatif, remis à 0 à chaque reboot). RPi stocke `datetime.utcnow()` (absolu UTC). Les deux ne sont jamais réconciliés. Si Arduino redémarre, les graphiques Plotly montrent un saut temporel inexpliqué. | Perte de traçabilité ; corrélation impossible entre logs Arduino et données DB |
| M11 | Frontend | Mémoire | `dashboard.js:26` | `setInterval(callback, 30000)` sans `clearInterval`. En navigation SPA ou rechargement partiel, des intervalles orphelins continuent d'émettre des requêtes HTTP en arrière-plan. | Requêtes inutiles, données obsolètes dans des intervalles "zombies" |
| M12 | Frontend | UX / Erreur | `dashboard.js:33–40` | Erreur réseau `fetch('/api/data/current')` catchée uniquement en `console.warn`. L'utilisateur voit des données figées sans aucun indicateur visuel de panne. | Décision d'arrosage manuelle sur données périmées ; perte de confiance dans l'interface |
| M13 | Arduino | WiFi | `WiFiManager.cpp:41` | Reconnexion WiFi bloquante jusqu'à 10 s (`while(status != WL_CONNECTED && millis()-t < 10000)`). Acceptable en `setup()`, mais si ce code est invoqué en contexte de loop (via `reconnectIfNeeded`), le firmware est gelé 10 s. | Perte de réactivité prolongée ; watchdog non alimenté pendant ce temps |
| M14 | Raspberry | Validation | `alert_recipient.py:21` + `routes_dashboard.py:595` | Validation email = présence du caractère `@` uniquement. `abc@`, `@domaine`, `a@b` sont acceptés et stockés en base. | Adresses invalides stockées ; envois SMTP en erreur sans diagnostic clair |

---

### 🟡 Mineur (6)

| # | Composant | Catégorie | Fichier:ligne | Problème | Impact |
|---|-----------|-----------|---------------|----------|--------|
| m1 | Arduino | Mémoire | `Logger.cpp:7` | Buffer circulaire statique `char _buffer[20][160]` = 3.2 KB. Si plus de 20 logs sont générés avant flush HTTP, les plus anciens sont silencieusement écrasés. | Perte de logs de diagnostic en cas de pic d'activité |
| m2 | Raspberry | Code | `routes_config.py:38` | Rejet silencieux des seuils d'humidité hors plage `(0, 100]` — aucun message d'erreur retourné à l'utilisateur (formulaire re-rendu sans feedback). | Confusion UX ; l'utilisateur ne sait pas pourquoi sa modification n'est pas prise en compte |
| m3 | Raspberry | Sécurité | `alert_recipient.py:21` | Longueur email limitée à 120 chars par DB mais non vérifiée côté application avant insertion. | Risque de troncature silencieuse si email > 120 chars (rare mais possible) |
| m4 | Frontend | Accessibilité | `base.html:145` | Bouton notifications (`<button class="notif-btn">`) contient uniquement `<i class="bi bi-bell-fill">`, sans `aria-label`. | Inaccessible aux lecteurs d'écran |
| m5 | Frontend | Accessibilité | `base.html` (nav-sub) | Éléments `<div class="zone-dot">` décoratifs sans `aria-hidden="true"` — les lecteurs d'écran les annoncent comme des éléments de contenu vides. | Expérience dégradée pour utilisateurs de technologies d'assistance |
| m6 | CSS | Qualité | `style.css:54` | Variable `--card-header-bg: rgba(48,209,88,0.08)` définie mais peu utilisée dans les templates (usage limité à un contexte commenté). | Dette technique mineure ; variable potentiellement obsolète |

---

## 3. Top 5 des actions prioritaires

### 🥇 P1 — Limiter la taille de lecture HTTP Arduino (`RestServer.cpp:31`)
```cpp
// Avant (dangereux) :
String line = client.readStringUntil('\n');

// Après (sûr) :
String line = "";
int maxLen = 512;
while (client.available() && line.length() < maxLen) {
    char c = client.read();
    if (c == '\n') break;
    line += c;
}
```
**Risque sans fix** : crash Arduino par épuisement SRAM sur une seule requête malformée → toutes les vannes hors contrôle.

---

### 🥈 P2 — Alimenter le watchdog + supprimer le busy-wait (`main.cpp`, `RestServer.cpp:19`)
```cpp
// Dans loop() — ajouter en fin de boucle :
watchdog.feed();

// RestServer.cpp:19 — remplacer le busy-wait par :
while (!client.available() && millis() - t < 2000) delay(1);
```
**Risque sans fix** : firmware en état indéterminé (resets intempestifs ou absence de protection en cas de blocage réel).

---

### 🥉 P3 — Durcir la `SECRET_KEY` Flask (`config.py:9`)
```python
# Avant :
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "monjardin-dev-secret")

# Après :
_key = os.environ.get("FLASK_SECRET_KEY")
if not _key:
    import secrets
    _key = secrets.token_hex(32)
    import logging
    logging.getLogger(__name__).warning(
        "FLASK_SECRET_KEY non définie — clé éphémère générée. "
        "Les sessions seront invalidées à chaque redémarrage."
    )
SECRET_KEY = _key
```
**Risque sans fix** : usurpation de session admin, commande des actionneurs par un attaquant réseau local.

---

### 🏅 P4 — Sanitiser les `innerHTML` côté frontend (`dashboard.js:162, 185`)
```javascript
// Avant (XSS) :
list.innerHTML = data.entries.map(e => `<div>${e.message}</div>`).join('');

// Après (sûr) — créer les éléments via DOM :
list.replaceChildren(...data.entries.map(e => {
    const d = document.createElement('div');
    d.textContent = e.message;  // textContent échappe automatiquement
    return d;
}));
```
Appliquer le même pattern partout où des données API sont injectées via `innerHTML`.

---

### 🏅 P5 — Protéger `force_cycle()` contre les exécutions parallèles (`routes_api.py:336`)
```python
import threading
_cycle_lock = threading.Lock()

def force_cycle():
    if not _cycle_lock.acquire(blocking=False):
        return jsonify({"ok": False, "message": "Un cycle est déjà en cours"}), 429
    def _run():
        try:
            automation_cycle(current_app._get_current_object())
        finally:
            _cycle_lock.release()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Cycle déclenché"})
```

---

## 4. Questions ouvertes

| # | Question | Contexte |
|---|----------|---------|
| Q1 | **Comportement des vannes latching lors d'un reset Arduino** : les relais latching conservent leur état mécaniquement. Si l'Arduino reboot (watchdog), une vanne ouverte reste ouverte indéfiniment jusqu'à la prochaine commande RPi (60 s). Est-ce le comportement souhaité, ou faut-il un failsafe électronique (relais de coupure générale) ? | `ValveController.cpp`, `config.h:17` |
| Q2 | **Authentification des routes `/api/*`** : les endpoints de contrôle (`/api/control/valve`, `/api/control/roof`) ne demandent aucune authentification. N'importe quel client sur le réseau local peut commander les actionneurs. Est-ce intentionnel (réseau domestique isolé) ou faut-il un token API ? | `routes_api.py:118–182`, `app/__init__.py:_setup_auth()` |
| Q3 | **`datetime.utcnow()` vs `datetime.now(timezone.utc)`** : le code utilise systématiquement `utcnow()` (deprecated). La migration vers `datetime.now(timezone.utc)` change le type retourné (naive → aware). Y a-t-il des comparaisons `datetime naive / aware` qui casseraient après migration ? | ~20 occurrences dans `scheduler.py`, `routes_api.py`, `models/` |
| Q4 | **Taille maximale de `IrrigationLog` et `JournalEntry`** : à 1 cycle/min, 4 zones, on génère ~5760 `SensorReading`/jour. Les tables `journal_entries` et `irrigation_log` n'ont pas de politique de rétention. Sur Raspberry Pi (carte SD), quelle est la durée avant saturation disque ? Route `/api/journal/purge` existe mais n'est pas appelée automatiquement. | `models/irrigation_log.py`, `routes_api.py:674` |
| Q5 | **`AnemometerSensor` : données collectées mais non utilisées dans les décisions** : la vitesse du vent est lue et incluse dans `/api/sensors`, stockée dans `SensorReading` (`temp_serre_c` column présente mais pas `wind_speed_kmh`). Le `roof_engine.py` utilise `weather["wind_kmh"]` (météo externe) mais pas la mesure locale de l'anémomètre. Divergence intentionnelle ? | `AnemometerSensor.cpp`, `roof_engine.py`, `models/sensor_data.py` |
| Q6 | **Mode production : `SIMULATION_MODE=false` + Arduino physique absent** : si l'Arduino est déconnecté, `ArduinoClient` retourne `None` sur chaque appel. Le dashboard affiche des données "vides" mais ne signale pas clairement "Arduino hors ligne" à l'utilisateur. Un badge ou alerte globale est-il prévu ? | `arduino_client.py:19–29`, `routes_api.py:225` |

---

*Audit généré le 2026-04-21 — MonJardin v1.0 — Lecture seule, aucun fichier modifié.*
