# MonJardin — Guide projet pour Claude

> Version courante : **5.0** (avril 2026). Voir `CHANGELOG.md` pour l'historique.

## Vue d'ensemble

Système complet de gestion automatisée d'un jardin potager à **Vullierens, Vaud, Suisse** (zone USDA 7b, ~430m).

Deux sous-systèmes couplés :
1. **Firmware Arduino Edge Control** (C++/PlatformIO) — acquisition capteurs, pilotage actionneurs
2. **Application Raspberry Pi 5** (Python/Flask) — dashboard web, logique décisionnelle, météo, conseils

---

## Structure des répertoires

```
MonJardin/
└── garden_manager/            # Application Flask principale
    ├── run.py                 # Point d'entrée — démarre émulateur + Flask
    ├── .env                   # Config locale (non commitée)
    ├── requirements.txt
    ├── app/
    │   ├── __init__.py        # Factory Flask + APScheduler + blueprints
    │   ├── config.py          # Config depuis .env
    │   ├── seed.py            # Données initiales + historique démo 720h
    │   ├── models/            # SQLAlchemy — Zone, SensorReading, IrrigationLog, etc.
    │   ├── services/          # ArduinoClient, WeatherService, irrigation_engine, roof_engine
    │   ├── api/               # Blueprints Flask : routes_dashboard, routes_api, routes_config
    │   ├── templates/         # Jinja2 — base.html, dashboard.html, zone_detail.html, etc.
    │   └── static/            # CSS (style.css) + JS (dashboard.js, controls.js)
    ├── simulator/             # Émulateur Arduino (Flask :8081) + simulateurs physiques
    └── arduino_edge_control/  # Firmware C++/PlatformIO
        └── src/               # main.cpp, RestServer, ValveController, LinearActuator, etc.
```

---

## Démarrage

```bash
cd garden_manager
source venv/bin/activate
python run.py
```

- App Flask : http://localhost:5001 (port défini dans `.env`)
- Émulateur Arduino : http://localhost:8081
- Login par défaut : `admin` / `admin123`

---

## Configuration (.env)

| Variable | Valeur dev | Description |
|---|---|---|
| `SIMULATION_MODE` | `true` | Utilise l'émulateur Arduino local |
| `SIMULATION_SPEED` | `1` | Accélérateur simulation (1=temps réel) |
| `FLASK_PORT` | `5001` | Port de l'app Flask |
| `EMULATOR_PORT` | `8081` | Port de l'émulateur |
| `ARDUINO_API_URL` | `http://192.168.1.100:80/api` | URL Arduino réel (prod) |
| `DATABASE_PATH` | chemin absolu | SQLite dans ~/Library/Application Support/MonJardin/ |
| `FLASK_SECRET_KEY` | chaîne longue | Clé session Flask (obligatoire pour stabilité des sessions) |
| `WEATHER_PROFILE` | `printemps_normal` | Profil météo simulé |
| `GARDEN_LATITUDE/LONGITUDE` | `46.778 / 6.641` | Coordonnées Vullierens |

Pour basculer en production : `SIMULATION_MODE=false` + `ARDUINO_API_URL` → adresse réelle.

---

## Architecture technique

### Backend Flask
- **Factory pattern** avec `create_app()` dans `app/__init__.py`
- **3 blueprints** : `dashboard_bp` (HTML), `api_bp` (JSON REST), `config_bp` (config/plantation)
- **APScheduler** : cycle automation toutes les 60s, météo toutes les 30min
- **SQLite WAL** avec `check_same_thread=False`
- **Authentification** : Flask-Login simple (AdminUser en base)
- **Pas de Flask-WTF** — validation manuelle dans les routes

### Base de données (SQLite)
| Table | Colonnes notables |
|---|---|
| `zones` | `zone_id`, `name`, `has_roof`, `length_m`, `width_m`, `irrigation_mode`, seuils, **`display_order` (v4.0)** |
| `sensor_readings` | `timestamp`, `zone_id`, `soil_moisture_pct`, `temperature_c`, `temp_serre_c` |
| `irrigation_log` | Événements arrosage (`open`/`close`, `trigger_type`, `reason`) |
| `roof_log` | Événements toit serre |
| `plantings` | `vegetable_name`, `variety`, `status`, **`display_order`, `grid_row`, `grid_col`, `grid_w`, `grid_h` (v4.0)** |
| `journal_entries` | `timestamp` UTC, `level`, `message` (français + emojis) |
| `admin_users` | Comptes admin (PIN haché) |
| `alert_recipients` | Emails pour alertes arrosage |
| `weather_cache` | `forecast_json`, `source`, `valid_until` (TTL 30 min) |
| **`zone_photos` (v4.5)** | `id`, `zone_id`, `filename` (UUID), `captured_at`, `caption`, `file_size_kb` |

> Migration automatique au démarrage : `_migrate_db()` dans `app/__init__.py` ajoute les nouvelles colonnes avec `ALTER TABLE` sans perte de données. Les plantings existants sont auto-placés sur la grille (row-major) au premier démarrage v4.0.

### Moteur de décision irrigation (`irrigation_engine.py`)
Règles de priorité (ordre strict) :
1. Zone `disabled` → skip
2. Zone `manual` → skip
3. Gel (`temp < 3°C` ou `frost_risk`) → fermer
4. Pluie prévue (`precip_mm_6h > 5mm`) → reporter
5. Canicule (`temp > 32°C`) hors fenêtre 19h-21h → reporter
6. Humidité < seuil bas → ouvrir
7. Humidité ≥ seuil haut (vanne ouverte) → fermer
8. Défaut → skip

### Moteur toit (`roof_engine.py`)
- Fermer si : pluie, temp < 8°C, vent > 40km/h, nuit oct-mars, gel
- Ouvrir si : temp > 25°C sans pluie, ou humidité zone 1 > 75%
- Défaut sécurité : FERMÉ

### Zones physiques
| Zone | Nom | Particularité |
|---|---|---|
| 1 | Serre | `has_roof=True` — vérin pilote la lucarne |
| 2 | Soleil | Plein terre, exposition sud |
| 3 | Mi-ombre | Partiellement ombragée |
| 4 | Aromates | Seuil bas 25% (moins gourmand) |

---

## Interface web (v4.5)

### Dashboard principal (`/dashboard`) — 4 onglets en haut
- **Tab bar en tête de page** (au-dessus du hero) : Accueil · Météo · Tâches · Mes zones
- **Accueil** (défaut) : hero "Aujourd'hui" + Pulse Score + actions concrètes + alertes + récoltes prévues
- **Météo** : bandeau riche 24 h + prévisions 7 jours + risque gel + carte dédiée Anémomètre
- **Tâches** : vigilance sanitaire + tâches du mois avec intro pédagogique + liens vers Conseils/Plans/Rotation/Glossaire
- **Mes zones** : grille drag&drop (SortableJS) des cartes de zones
- Onglet actif en **fond vert** (style cohérent avec Conseils)
- Bouton « Réorganiser » sur Mes zones → mode SortableJS
- Carte de bienvenue fermable (`POST /setup/skip` → flag `.setup_skipped`)
- Refresh capteurs/actuators toutes les 30 s

### Page Zone détail (`/zones/<id>`)
- 6 onglets : Temps réel · Graphiques · **Plants** · **Photos** (v4.5) · Événements · Configuration
- Plan visuel **case-par-case** (30 cm/case) avec drag & drop natif HTML5
- Toutes les cases visibles (cliquables pour planter à l'endroit voulu)
- Multi-cases pour semis (toggle "Rangée" 2-8 cases dans modal Quick-Plant)
- Compost (drop zone) en bas pour suppression définitive
- Récapitulatif compact des plants par espèce/variété
- 3 graphiques séparés dans l'onglet Graphiques (mêmes que /history)
- Persistance d'onglet via hash URL (`#plants`, `#config`, …)

### Pages secondaires
- `/planting` — gestion globale des plantations (toutes zones)
- `/conseils` — 9 catégories carrousel + filtre saison + recherche
- `/glossaire` — 57 termes horticoles avec images Wikimedia
- `/plans` — 16 plans pré-faits (compatibilité de compagnonnage vérifiée), application avec auto-distribution sur la grille
- `/rotation` — historique par zone et année
- `/setup` — wizard d'onboarding (réutilisable depuis Administration)
- `/history` — 3 graphiques séparés (humidité · températures · arrosages) avec filtre par zone/période
- `/settings` — configuration seuils, mode irrigation, dimensions zones
- `/admin/*` — utilisateurs, alertes email, logs, reset annuel

---

## API REST (`/api/*`)

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/data/current` | GET | Capteurs + actionneurs temps réel |
| `/api/data/history` | GET | Série temporelle `?zone_id=&hours=` |
| `/api/data/irrigation_events` | GET | Marqueurs arrosages pour Plotly |
| `/api/control/valve/<zone_id>` | POST | Commande manuelle vanne `{"action":"open"}` |
| `/api/control/roof` | POST | Commande manuelle lucarne |
| `/api/control/zone/<zone_id>/mode` | POST | Changer mode auto/manual/disabled |
| **`/api/zones/reorder` (v4.0)** | POST | Drag & drop ordre des zones `{"order":[2,1,4,3]}` |
| **`/api/zones/<id>/plants/reorder` (v4.0)** | POST | Réordonner les groupes d'espèces |
| **`/api/zones/<id>/plants/<id>/move` (v4.0)** | POST | Déplacer un plant vers `{"row":r,"col":c}` |
| **`/zones/<id>/photos/upload` (v4.5)** | POST | Upload multi-fichiers (multipart/form-data) |
| **`/zones/<id>/photos/<id>/delete` (v4.5)** | POST | Suppression idempotente |
| **`/zones/<id>/photos/<id>/edit` (v4.5)** | POST | Édition date + légende |
| **`/zones/<id>/photos/<filename>` (v4.5)** | GET | Sert le fichier image (auth requise) |
| **`/planting/zone/<id>/history/clear` (v4.5)** | POST | Efface l'historique non-actif d'une zone |
| **`/planting/rotation/clear` (v4.5)** | POST | Efface la grille de rotation (toutes zones) |
| `/api/weather/current` | GET | Météo actuelle |
| `/api/weather/forecast` | GET | Prévisions (7 jours v4.0) |
| `/api/system/force_cycle` | POST | Forcer cycle automation immédiatement |
| `/api/system/health` | GET | Statut système |
| `/setup/skip` | POST | Masquer la bannière de bienvenue (v4.0) |

---

## Émulateur Arduino (`simulator/`)

Serveur Flask sur `:8081` qui simule exactement l'API de l'Arduino réel :
- `GET /api/sensors` — 4 zones avec physique simulée (évaporation, arrosage)
- `GET /api/actuators/status` — état vannes + toit
- `POST /api/actuators/valve/<zone_id>` — commande vanne
- `POST /api/actuators/roof` — commande lucarne
- `POST /admin/inject_failure` — injection de pannes pour tests
- `POST /admin/reset` — réinitialisation état

---

## Firmware Arduino (`arduino_edge_control/`)

- **Plateforme** : Arduino Edge Control (SAMD, 32KB SRAM, NINA-W102 WiFi)
- **Capteurs** : SoilWatch 10 (ADC) × 4, DS18B20 (OneWire) température
- **Actionneurs** : Vannes 24V latching (relais pulse 50ms) × 4, Vérin H-bridge (lucarne)
- **Serveur HTTP embarqué** : parsing manuel ligne par ligne (pas de bibliothèque HTTP)
- **Watchdog** : Adafruit SleepyDog, timeout 8s, `Watchdog.reset()` dans chaque loop
- **Failsafe** : fermeture vannes si perte WiFi > 5min

---

## Conventions de code

### Python
- `datetime.now(timezone.utc).replace(tzinfo=None)` — jamais `datetime.utcnow()` (déprécié Python 3.12+)
- Affichage des heures : utiliser les filtres Jinja **`localtime` / `localdate` / `localhour`** (conversion UTC → Europe/Zurich) — jamais `strftime` direct sur un timestamp DB
- Flash messages Flask pour feedback utilisateur (pas de redirect silencieux)
- Validation email : regex `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`
- Pas de `innerHTML` avec données issues de la DB → `textContent` ou `createElement`
- Lock threading sur `force_cycle` pour éviter exécutions parallèles

### JavaScript
- Stocker les `setInterval` dans une variable et `clearInterval` sur `beforeunload`
- Bannière d'erreur rouge fixe si fetch échoue (pas silencieux)
- `querySelectorAll` pour les attributs `data-zone-text` (plusieurs éléments par zone)
- **Modals uniformes** : utiliser `showConfirm({title, body, okLabel, okClass, icon, iconClass}, callback)` ; helpers `confirmDelete(target)`, `confirmResetGarden`, `confirmApplyPlan` — jamais `confirm()` natif
- **Persistance d'onglet** : `location.hash = '#tabname'` via `history.replaceState` ; au chargement, `_restoreTabFromHash` réactive l'onglet
- **Drag & drop natif HTML5** pour les plants (zone_detail) ; **SortableJS** (CDN) pour la grille des cartes du dashboard

### CSS
- Thème dark Apple-inspired : `--bg-app: #000`, `--bg-primary: #1c1c1e`
- Toujours ajouter `-webkit-` prefix pour `backdrop-filter` et propriétés flex critiques
- Classes `zc-*` pour les cartes du dashboard ; `plant-cell-filled` / `plant-cell-slot` pour la grille zone ; `plant-compost` pour le drop de suppression
- Cache-buster global : variable `static_v` injectée par le context_processor — bumper à chaque modif CSS/JS (actuellement v76)

---

## Problèmes connus / Notes

- **Safari** : nécessite `SESSION_COOKIE_SAMESITE = 'Lax'` dans config (déjà configuré) — rafraîchir avec Cmd+Shift+R si la session est perdue
- **SECRET_KEY** : doit être défini dans `.env` sinon sessions invalidées au redémarrage
- **MétéoSuisse** : URL VQHA80.json change périodiquement → fallback automatique vers Open-Meteo (qui fournit aussi les prévisions 7 jours utilisées par le dashboard v4.0)
- **db.create_all()** : doit être appelé APRÈS l'import explicite de tous les modèles dans `__init__.py`
- **Migrations DB** : `_migrate_db()` gère l'ajout des colonnes manquantes via `ALTER TABLE` au démarrage. Pour ajouter une colonne, ajouter un test `if "colname" not in cols` puis `_autoplace_plantings_initial()` ou similaire si peuplement requis
- **Port** : l'app tourne sur 5001 (défini dans `.env`), pas 5000
- **Plants drag & drop** : 1 plant = 1 case de 30 cm × 30 cm. Le contrôle de collision est côté serveur (`/api/zones/<id>/plants/<id>/move` retourne 409 si la case est occupée)
- **Plans pré-faits** : la compatibilité de compagnonnage est vérifiée à l'application (`bad_companions` dans `plants_database.json`). Auto-distribution sur la grille en row-major

---

## Localisation

Tout le texte de l'interface est en **français**. Les messages du journal système, les raisons d'arrosage, les alertes, les labels de formulaire — tout est en français.

---

## Propriétaire

Patrick Pinard — ppinard@bluewin.ch — Vullierens, Vaud, Suisse
