# MonJardin — Guide projet pour Claude

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
| Table | Rôle |
|---|---|
| `zone` | Configuration des 4 zones (seuils, mode, has_roof) |
| `sensor_reading` | Historique capteurs (humidité, température) indexé sur timestamp+zone_id |
| `irrigation_log` | Événements arrosage (open/close, trigger_type, raison) |
| `roof_log` | Événements toit serre |
| `planting` | Plants actifs/planifiés par zone |
| `journal_entry` | Journal système (décisions moteur, alertes) |
| `admin_user` | Comptes admin (1 seul en pratique) |
| `alert_recipient` | Emails pour alertes arrosage |

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

## Interface web

### Dashboard principal (`/dashboard`)
- 4 cartes de zone : humidité (jauge), état vanne/lucarne, plants actifs
- Graphiques Plotly (historique humidité + température)
- Refresh automatique toutes les 30s
- Onglets : Zones | Météo | Récoltes | Journal

### Pages secondaires
- `/zones/<id>` — détail zone : graphique + historique + gestion plants + contrôles manuels
- `/planting` — gestion plantations + compagnonnage
- `/history` — historique global
- `/settings` — configuration seuils, mode irrigation, dimension zones
- `/admin/*` — alertes email, logs système

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
| `/api/weather/current` | GET | Météo actuelle |
| `/api/weather/forecast` | GET | Prévisions 48h |
| `/api/system/force_cycle` | POST | Forcer cycle automation immédiatement |
| `/api/system/health` | GET | Statut système |

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
- Flash messages Flask pour feedback utilisateur (pas de redirect silencieux)
- Validation email : regex `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`
- Pas de `innerHTML` avec données issues de la DB → `textContent` ou `createElement`
- Lock threading sur `force_cycle` pour éviter exécutions parallèles

### JavaScript
- Stocker les `setInterval` dans une variable et `clearInterval` sur `beforeunload`
- Bannière d'erreur rouge fixe si fetch échoue (pas silencieux)
- `querySelectorAll` pour les attributs `data-zone-text` (plusieurs éléments par zone)

### CSS
- Thème dark Apple-inspired : `--bg-app: #000`, `--bg-primary: #1c1c1e`
- Toujours ajouter `-webkit-` prefix pour `backdrop-filter` et propriétés flex critiques
- Classes `zc-*` pour les nouvelles cartes du dashboard (remplace l'ancienne `zone-card`)

---

## Problèmes connus / Notes

- **Safari** : nécessite `SESSION_COOKIE_SAMESITE = 'Lax'` dans config (déjà configuré) — rafraîchir avec Cmd+Shift+R si la session est perdue
- **SECRET_KEY** : doit être défini dans `.env` sinon sessions invalidées au redémarrage
- **MétéoSuisse** : URL VQHA80.json change périodiquement → fallback automatique vers Open-Meteo
- **db.create_all()** : doit être appelé APRÈS l'import explicite de tous les modèles dans `__init__.py`
- **Port** : l'app tourne sur 5001 (défini dans `.env`), pas 5000

---

## Localisation

Tout le texte de l'interface est en **français**. Les messages du journal système, les raisons d'arrosage, les alertes, les labels de formulaire — tout est en français.

---

## Propriétaire

Patrick Pinard — ppinard@bluewin.ch — Vullierens, Vaud, Suisse
