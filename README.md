# 🌱 MonJardin — Version 4.0

Système automatisé de gestion de jardin potager · Raspberry Pi 5 + Arduino Edge Control · Flask · SQLite

---

## Aperçu visuel

### Tableau de bord

![Tableau de bord](docs/screenshot_dashboard_v2.png)

*Dashboard Option A : hero "Aujourd'hui" + Pulse Score + bandeau météo 24h, puis 2 onglets "Vue d'ensemble" (alertes, prévisions 7 jours, tâches du mois, récoltes) et "Mes zones" (grille drag&drop des 4 cartes).*

### Page Conseils

![Conseils](docs/screenshot_conseils.png)

*9 catégories de bonnes pratiques avec carrousels indépendants (Arrosage · Sol · Planification · Plantation · Compagnonnage · **Sous serre** · Observation · Lutte naturelle · Saisonnalité). Filtre par saison + recherche texte global.*

### Page Plantation

![Plantation](docs/screenshot_planting.png)

*Gestion des plantations par zone, conseils du mois (55 espèces), progression et dates de récolte.*

### Vue détail d'une zone

![Zone détail](docs/screenshot_zone_detail.png)

*5 onglets : Temps réel · Graphiques (3 graphes séparés : humidité, températures, événements arrosage) · **Plants** (plan visuel case-par-case avec drag&drop, multi-cases pour semis) · Événements · Configuration.*

### Diagnostic Arduino Edge Control

![Arduino Edge Control](docs/screenshot_arduino.png)

*6 onglets : Système (CPU, température MCU, SRAM, Flash), Réseau (WiFi, IP, MAC), Capteurs, Actionneurs, I/O & Bus, API brute.*

### À propos

![À propos](docs/screenshot_about.png)

*Présentation du projet, fonctionnalités v4.0, matériel et stack technique.*

### Interface mobile iPhone (PWA)

<p align="center">
  <img src="docs/screenshot_iphone_bord.png" alt="Tableau de bord iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_zones.png" alt="Mes zones iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_encyclopedia.png" alt="Encyclopédie iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_plantation.png" alt="Plantation iPhone" width="220">
</p>

*Interface PWA installable sur iPhone — Tableau de bord, vue des zones, encyclopédie de 55 espèces et gestion des plantations.*


## Architecture matérielle

![Schéma de connexion](docs/schema_connexion.svg)

---

## Aperçu

MonJardin gère automatiquement l'arrosage et l'ouverture du toit de serre de 4 zones de culture, en tenant compte de l'humidité du sol, de la météo locale et des besoins spécifiques des légumes plantés.

| Zone | Nom | Particularité |
|------|-----|--------------|
| 1 | Serre | Toit motorisé, capteur température intérieure |
| 2 | Soleil | Exposition plein sud |
| 3 | Mi-ombre | Exposition partielle |
| 4 | Aromates | Seuils d'arrosage réduits |

---

## Nouveautés version 4.0

### Plan visuel case-par-case avec drag & drop libre

- **Grille fixe** N×M cases (30 cm × 30 cm) calculée d'après les dimensions réelles de la zone
- **Toutes les cases visibles** — chaque case vide est cliquable pour planter à cet endroit précis
- **1 plant = 1 case** : plus de badge `×3`, chaque plant peut être déplacé indépendamment
- **Drag & drop natif HTML5** : glisser un plant vers n'importe quelle case libre, contrôle de collision côté serveur (HTTP 409 si occupée)
- **Mode rangée pour les semis** (carottes, radis, oignons, …) : sélection de longueur (2 à 8 cases adjacentes), créées comme une seule plantation
- **Auto-placement** des plantings existants à la migration (row-major)
- **Récapitulatif** sous la grille : compte par espèce/variété
- **Persistance de l'onglet** : retour automatique sur l'onglet *Plants* après chaque action (drag, ajout, suppression, édition) via hash d'URL

### Drag & drop des cartes zones (Dashboard)

- Bouton **« Réorganiser »** dans l'onglet *Mes zones* → mode drag actif
- SortableJS pour glisser les cartes (souris ou tactile)
- Sauvegarde immédiate de l'ordre via `Zone.display_order`
- Ordre propagé partout (sidebar, dropdowns, plans, automation cycle)

### Dashboard Option A (page d'accueil épurée)

- 2 onglets seulement : **Vue d'ensemble** (par défaut) et **Mes zones**
- Hero "Aujourd'hui à Vullierens" + Pulse Score + bandeau météo 24h restent visibles au-dessus
- Vue d'ensemble réorganisée : alertes (gel + vigilance sanitaire) → **prévisions 7 jours** (vs 2 jours en v3) → tâches du mois → récoltes
- Carte "Vent" compactée en pied de la carte Prévisions (info secondaire)
- Carte de bienvenue **fermable** par bouton croix (réactivable depuis Administration)

### Page Conseils refondue (9 catégories + filtre saison)

| Catégorie | Conseils |
|-----------|----------|
| 💧 Arrosage | 6 conseils (matin, au pied, paillage…) |
| 🟫 Sol & fertilité | 7 conseils (paillage, compost, pH…) |
| 📅 Planification & rotation | 6 conseils |
| 🌱 Plantation & semis | 6 conseils |
| 🤝 Compagnonnage | 5 conseils |
| 🏠 **Sous serre / Tunnel** | **10 conseils** (à faire / à éviter) |
| 👁️ Observation & vigilance | 4 conseils |
| 🐛 Lutte naturelle & santé | 6 conseils |
| 🌿 Saisonnalité & climat | 7 conseils |

- **Carrousels indépendants** par catégorie (style identique à la page Glossaire)
- **Filtre par saison** : Toutes / 🌱 Printemps / ☀️ Été / 🍂 Automne / ❄️ Hiver
- **Recherche texte** combinée avec le filtre saison
- ~57 conseils au total (vs 12 en v3.0)

### Glossaire enrichi (57 termes)

- 8 catégories : Météo · Climat · Sol · Plantation · Entretien · Maladies · Traitements · Calendrier lunaire
- **Cards toujours déployées** (suppression du toggle « En savoir plus »)
- Images Wikimedia pour les termes principaux (Mildiou, Oïdium, Compost, Paillage, etc.)
- Tri éditorial des catégories (général → pointu)
- Recherche live + sections par catégorie avec carrousels

### Plans pré-faits (16 plans clé en main)

- Aromates de cuisine · Mini potager famille · Débutant salade-radis · Compagnonnage classique · Trois Sœurs · Serre d'été · Légumes racines hiver · Balcon en pots
- **Nouveaux plans v4.0** : Jardin à pizza 🍕 · Ratatouille provençale · Carré anti-pucerons 🐞 · Soupe d'automne 🥣 · Salade complète été · Paradis des pollinisateurs 🐝 · Potager d'altitude · Premier potager pour enfant 👶
- Modal de confirmation **uniformisé** (style global `showConfirm`)
- Compatibilité serre + surface minimale + niveau de difficulté affichés

### Page Graphiques refondue

- 3 graphiques distincts mais **base de temps commune** :
  - 💧 Humidité du sol (1 trace par zone)
  - 🌡️ Températures (extérieure + serre)
  - 💧 Événements d'arrosage (barres)
- Filtre par zone : 5 chips style Conseils (**Toutes** + 1 par zone, utilise le nom configuré)
- Filtre par période : 24h / 7 jours / 30 jours
- Mêmes graphiques disponibles dans l'onglet *Graphiques* d'une zone (filtrés sur la zone courante)

### Améliorations diverses

- **Modals uniformes** : suppression des `confirm()` natifs, helpers globaux `confirmDelete`, `confirmResetGarden`, `confirmApplyPlan`
- **Heures locales** : nouveaux filtres Jinja `localtime` / `localdate` / `localhour` qui convertissent UTC (DB) → Europe/Zurich pour l'affichage (fix bug heures journal)
- **Édition de variété** : le calcul du diff de quantité dans le modal Edit filtre désormais par variété (Tomate Cerise et Tomate Cœur de bœuf indépendantes)
- **Page d'administration** : tab dédié « Nouvelle année » pour reset annuel (archivage des plantations, dimensions zones par défaut)
- **Migration DB automatique** au démarrage : nouvelles colonnes `display_order`, `grid_row`, `grid_col`, `grid_w`, `grid_h` ajoutées sans perte de données

---

## Nouveautés version 3.0

### Dashboard transformé en vue contextuelle
- **Hero "Aujourd'hui"** : greeting personnalisé + phrases auto-générées (météo, récoltes prêtes, lucarne ouverte, sol sec)
- **Pulse Score 0-100** : cercle SVG animé, état global du jardin
- **Bandeau météo riche** : météo actuelle + forecast 24h scrollable
- **Bandeau d'actions concrètes** : 💧 zones à arroser, 🪟 lucarne ouverte, 🧺 récoltes prêtes
- **Onglet Tâches** : suggestions du mois (semis + récoltes ≤14j) avec validation

### Sécurité & automatisation
- **Arrêt automatique d'arrosage manuel** après la durée max configurée par zone
- **Plage horaire d'arrosage recommandée** par zone (selon saison + besoins)
- **Statut lucarne en temps réel** : "En cours d'ouverture/fermeture" pendant le mouvement (~30s)

---

## Nouveautés version 2.0

- **Dashboard** entièrement redessiné — navigation par onglets
- **Encyclopédie** étendue (55 espèces : légumes, herbes, fleurs ; les fruits ont été retirés en v3.0)
- **Profil météo dynamique** avec effet immédiat sur l'humidité simulée
- **Diagnostics système étendus** : Arduino (6 onglets) et Raspberry Pi (3 onglets)
- **Alertes email** paramétrables
- **Mise à jour simplifiée** : `update_pi.sh` compatible PEP 668 (Raspberry Pi OS Bookworm)

---

## Architecture

```
MonJardin/
└── garden_manager/
    ├── run.py                  # Point d'entrée unique
    ├── app/                    # Application Flask
    │   ├── api/                # Routes HTML + API JSON
    │   │   ├── routes_dashboard.py     # Pages HTML
    │   │   ├── routes_api.py           # API JSON (REST)
    │   │   └── routes_config.py        # CRUD plantations / zones
    │   ├── models/             # SQLAlchemy
    │   │   ├── zone.py                 # + display_order
    │   │   ├── planting.py             # + display_order, grid_row/col/w/h
    │   │   ├── sensor_data.py
    │   │   ├── irrigation_log.py       # + JournalEntry
    │   │   ├── alert_recipient.py
    │   │   └── admin_user.py
    │   ├── services/           # Moteurs décisionnels + clients matériel
    │   │   ├── arduino_client.py
    │   │   ├── weather_service.py      # + get_forecast_hourly(days=7)
    │   │   ├── irrigation_engine.py
    │   │   ├── roof_engine.py
    │   │   ├── planting_advisor.py
    │   │   ├── rotation_advisor.py
    │   │   ├── disease_advisor.py
    │   │   └── scheduler.py
    │   ├── templates/          # Interface Jinja2
    │   │   ├── dashboard.html          # Option A (2 onglets)
    │   │   ├── zone_detail.html        # Plan visuel case-par-case
    │   │   ├── conseils.html           # 9 catégories + filtre saison
    │   │   ├── glossary.html           # 57 termes
    │   │   ├── plans.html              # 16 plans pré-faits
    │   │   ├── history.html            # 3 graphes séparés + filtres zone
    │   │   ├── rotation.html
    │   │   ├── setup.html
    │   │   └── admin.html              # + tab Nouvelle année
    │   └── static/             # CSS, JS, PWA assets
    ├── simulator/              # Émulateur Arduino (simulation physique)
    └── arduino_edge_control/   # Firmware C++ / PlatformIO
```

---

## Fonctionnalités

### Automatisation
- **Moteur d'arrosage** — décisions par zone selon humidité, météo, gel, canicule, fenêtres horaires
- **Moteur de toit** — ouverture/fermeture automatique (température, pluie, vent, nuit)
- **Conseils plantation** — compagnonnage, calendrier suisse, alertes incompatibilité
- **Détection précoce maladies** — mildiou, oïdium, limaces, gel, canicule (selon météo + plantings actifs)
- **Rotation des cultures** — alertes par famille botanique, suggestion de meilleure zone
- **APScheduler** — cycles toutes les 60 secondes

### Interface web (PWA)
- Tableau de bord (Option A) · Graphiques (3 graphes filtrables) · Journal des événements
- Encyclopédie de **55 espèces** (légumes, herbes, fleurs — région suisse)
- **Plan visuel case-par-case** avec drag & drop libre + multi-cases pour semis
- Page Conseils — 9 catégories carrousel, filtre saison
- Page Glossaire — 57 termes horticoles avec images
- Page Plans pré-faits — 16 plans clé en main
- Page Plan rotation — historique par année et zone
- Diagnostic Arduino (6 onglets) et Raspberry Pi (3 onglets)
- Paramètres du jardin configurables · **Mode sombre/clair** · **Installable sur iPhone/iPad** (PWA)

### Météo
- **Open-Meteo** — prévisions horaires jusqu'à 7 jours (`GARDEN_LATITUDE / GARDEN_LONGITUDE`)
- **MétéoSuisse** — observations temps réel (station PAY par défaut)
- Cache DB 30 min · fallback simulateur

### Simulation
- Émulateur Arduino (`localhost:8081`) — physique réaliste par zone
- 6 profils météo (printemps, été chaud, orageux, automne, gel, canicule)
- Profil météo affiché dans le header avec effet immédiat
- Historique démo 30 jours généré automatiquement
- Accélération temps (`SIMULATION_SPEED`)

---

## Démarrage rapide

```bash
cd garden_manager
cp .env.example .env        # éditer si nécessaire
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Ouvrir **http://localhost:5001**
Login par défaut : `admin` / `admin123`

> En mode simulation (défaut), un émulateur Arduino démarre automatiquement sur `:8081`.

### Variables d'environnement clés

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SIMULATION_MODE` | `true` | `false` pour vrai Arduino |
| `ARDUINO_API_URL` | `http://192.168.1.100:80/api` | IP de l'Arduino réel |
| `SIMULATION_SPEED` | `1` | Accélérateur de temps (ex: `60`) |
| `WEATHER_PROFILE` | `printemps_normal` | Profil météo simulé |
| `FLASK_PORT` | `5001` | Port de l'application |
| `FLASK_SECRET_KEY` | (à définir) | Clé session Flask — **obligatoire** pour la stabilité |
| `GARDEN_NAME` | `MonJardin` | Nom affiché dans l'interface |
| `GARDEN_LOCATION` | `Vullierens · Vaud` | Lieu du jardin |
| `GARDEN_OWNER` | `Patrick Pinard` | Nom du propriétaire |
| `GARDEN_LATITUDE` | `46.778` | Coordonnées Open-Meteo |
| `GARDEN_LONGITUDE` | `6.641` | Coordonnées Open-Meteo |

---

## Schéma de base de données (v4.0)

| Table | Colonnes notables |
|-------|-------------------|
| `zones` | `zone_id`, `name`, `length_m`, `width_m`, `has_roof`, **`display_order`**, irrigation_mode, seuils |
| `plantings` | `id`, `zone_id`, `vegetable_name`, `variety`, `planted_date`, `expected_harvest_date`, `status`, **`display_order`**, **`grid_row`**, **`grid_col`**, **`grid_w`**, **`grid_h`** |
| `sensor_readings` | `timestamp`, `zone_id`, `soil_moisture_pct`, `temperature_c`, `temp_serre_c` |
| `irrigation_log` | `timestamp`, `zone_id`, `action`, `trigger_type`, `reason` |
| `roof_log` | `timestamp`, `action`, `trigger_type`, `reason` |
| `journal_entries` | `timestamp`, `level`, `message` (français, avec emojis) |
| `weather_cache` | `timestamp`, `forecast_json`, `source`, `valid_until` |
| `admin_users` | `id`, `username`, `pin_hash`, `enabled`, `last_login` |
| `alert_recipients` | `id`, `email`, `name`, `alert_types`, `enabled` |

> Les colonnes en **gras** sont nouvelles en v4.0. Une migration automatique `_migrate_db()` les ajoute au démarrage et auto-place les plantings existants sur la grille (row-major).

---

## API REST principale

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/data/current` | GET | Capteurs + actionneurs temps réel |
| `/api/data/history?zone_id&hours` | GET | Série temporelle pour Plotly |
| `/api/data/irrigation_events?hours` | GET | Marqueurs/barres d'arrosage |
| `/api/control/valve/<zone_id>` | POST | Commande manuelle vanne |
| `/api/control/roof` | POST | Commande manuelle lucarne |
| `/api/control/zone/<zone_id>/mode` | POST | Mode auto/manual/disabled |
| **`/api/zones/reorder`** | POST | **Drag&drop ordre des zones** |
| **`/api/zones/<id>/plants/reorder`** | POST | **Réordonner les groupes d'espèces** |
| **`/api/zones/<id>/plants/<id>/move`** | POST | **Déplacer un plant vers (row, col)** |
| `/api/weather/current` | GET | Météo actuelle |
| `/api/weather/forecast` | GET | Prévisions 7 jours |
| `/api/system/health` | GET | Statut système |
| `/api/system/force_cycle` | POST | Forcer cycle automation |
| `/setup/skip` | POST | Masquer la bannière de bienvenue |

---

## Mise à jour sur Raspberry Pi

```bash
# Depuis n'importe quel répertoire sur le Pi
bash ~/MonJardin/update_pi.sh --restart
```

Le script :
1. Détecte automatiquement le repo MonJardin
2. Sauvegarde la base de données (5 derniers backups conservés)
3. `git pull origin v3.0`
4. Met à jour les dépendances Python (compatible Bookworm / PEP 668)
5. Redémarre l'application (systemd ou manuel)

---

## Matériel

| Composant | Rôle |
|-----------|------|
| Raspberry Pi 5 | Serveur Flask, logique décisionnelle |
| Arduino Edge Control | Acquisition capteurs, pilotage actionneurs |
| Arduino MKR WiFi 1010 | Connectivité WiFi (enfichée sur le slot MKR du Edge Control) |
| SoilWatch 10 ×4 | Capteurs humidité sol |
| DS18B20 ×2 | Température extérieure + serre |
| Anémomètre QS-FS01 | Vitesse du vent (sortie analogique 0.4–2.0V) |
| Vannes GARDENA 24V ×4 | Irrigation par zone (solénoïde NC) |
| Vérin linéaire 12V | Ouverture toit serre |
| Edge Control Enclosure Kit | LCD 2×16 + bouton poussoir |

---

### Arduino Edge Control

[![Arduino Edge Control](https://store.arduino.cc/cdn/shop/products/ABX00048_01.front_e9fb5a5f-ae6c-4d63-b041-a48e15c5f819_1000x750.jpg)](https://store.arduino.cc/products/arduino-edge-control)

Contrôleur industriel Arduino dédié à l'agriculture et à l'automatisation outdoor. Il intègre nativement la gestion des vannes latching 24V, les entrées analogiques haute résolution pour capteurs de sol et les bus OneWire/I²C. **La connectivité WiFi est fournie par une carte MKR WiFi 1010 enfichée dans le slot MKR dédié** — le Edge Control seul n'a pas de WiFi.

| Caractéristique | Valeur |
|----------------|--------|
| MCU | STM32H747 (Cortex-M7 + M4) |
| Entrées analogiques | 16 canaux 16-bit |
| Vannes latching | 8 sorties 24V DC |
| Connectivité | Slot MKR — nécessite MKR WiFi 1010 pour WiFi |
| Alimentation | 7–30V DC (panneau solaire ou secteur) |
| Protection | IP67-ready (boîtier hermétique) |

🔗 [Documentation officielle Arduino Edge Control](https://docs.arduino.cc/hardware/edge-control/)

---

### Arduino MKR WiFi 1010

[![MKR WiFi 1010](https://store.arduino.cc/cdn/shop/products/ABX00023_03.front_a2f63975-6a58-43ea-ae5d-e7a5b1a07c95_643x483.jpg)](https://store.arduino.cc/products/arduino-mkr-wifi-1010)

Carte MKR enfichée dans le slot dédié du Edge Control. Elle fournit la connectivité WiFi 802.11 b/g/n et BLE 5.0 via le module NINA-W102. Le Edge Control l'utilise pour exposer son serveur REST HTTP et communiquer avec le Raspberry Pi.

| Caractéristique | Valeur |
|----------------|--------|
| Module WiFi/BLE | u-blox NINA-W102 |
| Connectivité | WiFi 802.11 b/g/n · BLE 5.0 |
| Interface | Slot MKR du Edge Control |
| Bibliothèque | `WiFiNINA` (incluse dans Arduino_EdgeControl) |

🔗 [Documentation officielle MKR WiFi 1010](https://docs.arduino.cc/hardware/mkr-wifi-1010/)

---

### Raspberry Pi 5

[![Raspberry Pi 5](https://www.raspberrypi.com/app/uploads/2023/10/2M2A3559-edit-1500x1000.jpg)](https://www.raspberrypi.com/products/raspberry-pi-5/)

Micro-ordinateur exécutant le serveur Flask, le moteur de décision et l'interface web. Il dialogue avec l'Arduino Edge Control via WiFi (API REST JSON) et se connecte à Open-Meteo pour les données météo.

| Caractéristique | Valeur |
|----------------|--------|
| CPU | Broadcom BCM2712 · Quad-core Arm Cortex-A76 @ 2.4 GHz |
| RAM | 4 GB LPDDR4X |
| Stockage | microSD (SQLite) |
| Connectivité | WiFi 802.11ac · Gigabit Ethernet |
| OS | Raspberry Pi OS Lite 64-bit (Bookworm) |
| Alimentation | 5V/5A USB-C |

🔗 [Documentation officielle Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/)

---

## Stack technique

- **Backend** : Python 3.10 · Flask · SQLAlchemy · APScheduler
- **Frontend** : Jinja2 · CSS custom (Apple design system) · Plotly.js · Bootstrap Icons · SortableJS
- **Base de données** : SQLite (WAL)
- **Firmware** : C++ · PlatformIO · ArduinoJson
- **PWA** : Service Worker · Web App Manifest · iOS safe-area
- **Météo** : Open-Meteo (prévisions 7j) + MétéoSuisse (observations)

---

## Localisation

Tout le texte de l'interface est en **français** : messages du journal, raisons d'arrosage, alertes, labels de formulaire, conseils, glossaire.

---

## Documentation associée

- [`AUDIT.md`](AUDIT.md) — audit sécurité firmware + backend (rev. 2026-04-21)
- [`CLAUDE.md`](CLAUDE.md) — guide de contribution & conventions du projet
- [`docs/MonJardin_Documentation_Technique.pdf`](docs/MonJardin_Documentation_Technique.pdf) — documentation technique complète
- [`docs/schema_connexion.svg`](docs/schema_connexion.svg) — schéma matériel
- [`CHANGELOG.md`](CHANGELOG.md) — historique des versions

---

*Version 4.0 · Avril 2026 · Patrick Pinard · Vullierens, Vaud · Suisse*
