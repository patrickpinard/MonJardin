# 🌱 MonJardin — Version 1.0

Système automatisé de gestion de jardin potager · Raspberry Pi 5 + Arduino Edge Control · Flask · SQLite

---

## Aperçu visuel

### Tableau de bord

![Tableau de bord](docs/screenshot_dashboard_v2.png)

*4 cartes de zones avec humidité en temps réel, températures serre/extérieur, statut des vannes, plantations actives et prévisions météo horaires.*

### Page Conseils

![Conseils](docs/screenshot_conseils.png)

*Carrousel de 12 conseils de jardinage, guide complet du compagnonnage (associations bénéfiques et à éviter), calendrier saisonnier.*

### Page Plantation

![Plantation](docs/screenshot_planting.png)

*Gestion des plantations par zone, conseils du mois (39 légumes en avril), progression et dates de récolte.*

### Vue détail d'une zone

![Zone détail](docs/screenshot_zone_detail.png)

*Plantations actives, barre d'humidité avec seuils, historique Plotly, configuration des seuils et journal des événements.*

### Diagnostic Arduino Edge Control

![Arduino Edge Control](docs/screenshot_arduino.png)

*Entrées analogiques SoilWatch 10, températures DS18B20, anémomètre, statut des vannes, vérin linéaire et I/O.*

### À propos

![À propos](docs/screenshot_about.png)

*Présentation du projet, fonctionnalités, matériel et stack technique.*

### Interface mobile iPhone (PWA) — 4 écrans

<p align="center">
  <img src="docs/screenshot_iphone_bord.png" alt="Tableau de bord iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_zones.png" alt="Mes zones iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_encyclopedia.png" alt="Encyclopédie iPhone" width="220">
  &nbsp;
  <img src="docs/screenshot_iphone_plantation.png" alt="Plantation iPhone" width="220">
</p>

*Interface PWA installable sur iPhone — Tableau de bord, vue des zones, encyclopédie de 50 légumes et gestion des plantations.*


## Architecture matérielle

![Schéma de connexion](docs/schema_connexion.svg)

---

## Aperçu

MonJardin gère automatiquement l'arrosage et l'ouverture du toit de serre de 4 zones de culture, en tenant compte de l'humidité du sol, de la météo locale et des besoins spécifiques des légumes plantés.

| Zone | Nom | Particularité |
|------|-----|--------------|
| 1 | Serre | Toit motorisé, capteur température intérieure |
| 2 | Potager | Exposition plein sud |
| 3 | Potager | Exposition partielle |
| 4 | Fleurs | Seuils d'arrosage réduits |

---

## Architecture

```
MonJardin/
└── garden_manager/
    ├── run.py                  # Point d'entrée unique
    ├── app/                    # Application Flask
    │   ├── api/                # Routes HTML + API JSON
    │   ├── models/             # SQLAlchemy (Zone, SensorReading, Planting…)
    │   ├── services/           # Moteurs décisionnels + clients matériel
    │   ├── templates/          # Interface Jinja2
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
- **APScheduler** — cycles toutes les 60 secondes

### Interface web (PWA)
- Tableau de bord · Graphiques 30 jours · Journal des événements
- Encyclopédie de 50 légumes et fleurs (région suisse)
- Gestion des plantations par zone avec progression et récolte
- Page Conseils — carrousel, compagnonnage, calendrier saisonnier
- Diagnostic Arduino et Raspberry Pi en temps réel
- Paramètres du jardin configurables (nom, lieu, propriétaire)
- **Mode sombre/clair** · **Installable sur iPhone/iPad** (PWA)
- Sidebar rétractable · Menu hamburger mobile

### Météo
- Open-Meteo (`GARDEN_LATITUDE / GARDEN_LONGITUDE`)
- Cache DB 30 min · fallback simulateur

### Simulation
- Émulateur Arduino (`localhost:8081`) — physique réaliste par zone
- 6 profils météo (printemps, été chaud, orageux, automne, gel, canicule)
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

Ouvrir **http://localhost:5000**

> En mode simulation (défaut), un émulateur Arduino démarre automatiquement sur `:8081`.

### Variables d'environnement clés

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SIMULATION_MODE` | `true` | `false` pour vrai Arduino |
| `ARDUINO_API_URL` | `http://192.168.1.100:80/api` | IP de l'Arduino réel |
| `SIMULATION_SPEED` | `1` | Accélérateur de temps (ex: `60`) |
| `WEATHER_PROFILE` | `printemps_normal` | Profil météo simulé |
| `FLASK_PORT` | `5000` | Port de l'application |
| `GARDEN_NAME` | `MonJardin` | Nom affiché dans l'interface |
| `GARDEN_LOCATION` | `Vullierens · Vaud` | Lieu du jardin |
| `GARDEN_OWNER` | `Patrick Pinard` | Nom du propriétaire |

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
| OS | Raspberry Pi OS Lite (64-bit) |
| Alimentation | 5V/5A USB-C |

🔗 [Documentation officielle Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/)

---

## Stack technique

- **Backend** : Python 3.10 · Flask · SQLAlchemy · APScheduler
- **Frontend** : Jinja2 · CSS custom (Apple design system) · Plotly.js · Bootstrap Icons
- **Base de données** : SQLite
- **Firmware** : C++ · PlatformIO · ArduinoJson
- **PWA** : Service Worker · Web App Manifest · iOS safe-area

---

*Version 1.0 · Avril 2026 · Patrick Pinard*
