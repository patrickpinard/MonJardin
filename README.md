# 🌱 MonJardin — Version 3.0

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

*Gestion des plantations par zone, conseils du mois (65 espèces), progression et dates de récolte.*

### Vue détail d'une zone

![Zone détail](docs/screenshot_zone_detail.png)

*5 onglets : Plantations actives, barre d'humidité avec seuils, historique Plotly, configuration des seuils et journal des événements.*

### Diagnostic Arduino Edge Control

![Arduino Edge Control](docs/screenshot_arduino.png)

*6 onglets : Système (CPU, température MCU, SRAM, Flash), Réseau (WiFi, IP, MAC), Capteurs, Actionneurs, I/O & Bus, API brute.*

### Diagnostic Raspberry Pi

![Raspberry Pi](docs/screenshot_rpi.png)

*3 onglets : Système (CPU, RAM, température), Stockage, Réseau (IP, débit).*

### À propos

![À propos](docs/screenshot_about.png)

*Présentation du projet, fonctionnalités v3.0, matériel et stack technique.*

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

*Interface PWA installable sur iPhone — Tableau de bord, vue des zones, encyclopédie de 65 espèces et gestion des plantations.*


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

## Nouveautés version 3.0

### Dashboard transformé en vue contextuelle
- **Hero "Aujourd'hui"** : greeting personnalisé + phrases auto-générées (météo, récoltes prêtes, lucarne ouverte, sol sec) — toute l'info en 1 coup d'œil sans cliquer
- **Pulse Score 0-100** : cercle SVG animé, état global du jardin (humidité 40 + alertes 30 + plants 20 + météo 10)
- **Bandeau météo riche** : météo actuelle + forecast 24h scrollable horizontal en pleine largeur
- **Bandeau d'actions concrètes** : 💧 zones à arroser, 🪟 lucarne ouverte, 🧺 récoltes prêtes — avec boutons d'action directs
- **Onglet Tâches** : suggestions du mois (semis + récoltes ≤14j) avec boutons valider ✓ / annuler ✕

### Plan visuel partagé (zones + dashboard)
- Grille soil-brown style App Store, **proportionnelle aux dimensions réelles** de la zone
- 1 cellule = 1 espèce avec emoji + quantité + délai de récolte
- **Modal Quick-Plant** : ajout en 3 clics depuis cellule vide, recherche live, filtres catégorie
- **Compagnonnage en temps réel** : ⚠️ incompatibilités, ✅ bonnes associations, 💡 suggestions
- Recommandations affichées (espacement, profondeur, eau, soleil, conseil)
- Suppression d'une espèce entière depuis le modal Edit

### Conseils refondu en 4 onglets
- 💡 **Bonnes pratiques** (carrousel 12 conseils)
- ❤️ **Associations** (compagnonnages bons/mauvais)
- 📅 **Calendrier saisonnier** (4 cartes saisons)
- 🌸 **Plantations du mois** (page Plantation supprimée et fusionnée ici)

### Sécurité & automatisation
- **Arrêt automatique d'arrosage manuel** après la durée max configurée par zone (anti-inondation)
- **Plage horaire d'arrosage recommandée** par zone (calculée selon saison + besoins en eau)
- **Graphique unifié zone** : un seul graph multi-axes (humidité + températures + bandes vannes ouvertes)
- **Statut lucarne en temps réel** : "En cours d'ouverture/fermeture" pendant le mouvement (~30s)

### Données plantes
- **Espacement réaliste** pour 22 espèces semées en ligne (`space_row_cm` : Carotte 5×25cm, Maïs 30×70cm, etc.) — capacité de zone 4× plus précise
- Suppression de la catégorie "Fruits" (arbres et arbustes pas en potager) → 55 espèces (légumes, herbes, fleurs)

### UX & navigation
- Cartes zones du dashboard sur **2 colonnes** (au lieu de 4) pour plus d'espace
- Sous-menus mobile **fermés par défaut** (Zones, Système & Admin) — menu plus compact
- Cache-buster global pour CSS + JS (plus de problème de cache navigateur)
- Tab Météo refondu : pas de doublon avec le bandeau du haut, comparaison vent prévu vs mesuré

### Bug fixes notables
- Tabs zone cassés (variables Jinja inter-blocks)
- Statut lucarne figé sur "En cours…" (refresh dashboard non déclenché)
- Légumes invisibles sur le plan visuel (zone "pleine")
- Sens lucarne inversé dans certains cas (fallback `getRoofMovingTarget`)
- Modal Quick-Plant non scrollable (boutons inaccessibles)

---

## Nouveautés version 2.0

### Interface redessinée
- **Dashboard** entièrement redessiné — navigation par onglets (Zones · Météo · Récoltes · Journal)
- **Zone détail** restructurée en 5 onglets (Plantations · Graphique · Historique · Seuils · Journal)
- **Onglets pill** sur toutes les pages secondaires pour navigation fluide
- Logo MonJardin harmonisé (couleur unique cohérente)

### Encyclopédie étendue
- **65 espèces** au total : légumes, herbes aromatiques, fruits, fleurs (vs 50 en v1)
- Ajout de 9 nouveaux fruits : Fraise, Framboise, Myrtille, Groseille, Cassis, Rhubarbe, Melon, Pastèque, Figue
- Ajout de 6 herbes aromatiques : Coriandre, Aneth, Estragon, Mélisse, Sarriette, Marjolaine
- Filtres par **catégorie** (légumes, herbes, fruits, fleurs) et par **saison**

### Gestion des plantations
- Formulaire plantation compatible iPad/PC/iPhone (grille 6 colonnes responsive)
- Sélecteur de légumes natif iOS (UIPickerView) restauré via `@supports (-webkit-touch-callout)`
- Affichage corrigé des légumes plantés dans la vue Plantation

### Profil météo dynamique
- **Profil météo actif** visible dans le header en mode simulation (chip coloré)
- Changement de profil météo avec **effet immédiat** sur l'humidité des zones (`PROFILE_MOISTURE_DELTA`)
- Températures simulées par profil (`PROFILE_TEMP`) — plus de température fixe à 18°C

### Diagnostics système étendus
- **Page Arduino** : 6 onglets avec CPU, température MCU, SRAM/Flash, IP, MAC, WiFi RSSI
- **Page Raspberry Pi** : 3 onglets Système · Stockage · Réseau
- Tailles d'affichage uniformisées sur toutes les pages de diagnostic

### Alertes email
- Notifications email paramétrables pour les événements d'arrosage et alertes
- Gestion des destinataires dans l'interface admin

### Mise à jour simplifiée
- Script `update_pi.sh` amélioré : détection automatique du repo, backup DB, compatible PEP 668 (Raspberry Pi OS Bookworm)

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
- Encyclopédie de **65 espèces** (légumes, herbes, fruits, fleurs — région suisse)
- Gestion des plantations par zone avec progression et récolte
- Page Conseils — carrousel, compagnonnage, calendrier saisonnier
- Diagnostic Arduino (6 onglets) et Raspberry Pi (3 onglets) en temps réel
- Paramètres du jardin configurables (nom, lieu, propriétaire)
- **Mode sombre/clair** · **Installable sur iPhone/iPad** (PWA)
- Sidebar rétractable · Menu hamburger mobile · Navigation onglets pill

### Météo
- Open-Meteo (`GARDEN_LATITUDE / GARDEN_LONGITUDE`)
- Cache DB 30 min · fallback simulateur

### Simulation
- Émulateur Arduino (`localhost:8081`) — physique réaliste par zone
- 6 profils météo (printemps, été chaud, orageux, automne, gel, canicule)
- **Profil météo affiché dans le header** avec effet immédiat sur humidité et température
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
| `GARDEN_NAME` | `MonJardin` | Nom affiché dans l'interface |
| `GARDEN_LOCATION` | `Vullierens · Vaud` | Lieu du jardin |
| `GARDEN_OWNER` | `Patrick Pinard` | Nom du propriétaire |

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
- **Frontend** : Jinja2 · CSS custom (Apple design system) · Plotly.js · Bootstrap Icons
- **Base de données** : SQLite (WAL)
- **Firmware** : C++ · PlatformIO · ArduinoJson
- **PWA** : Service Worker · Web App Manifest · iOS safe-area

---

*Version 3.0 · Avril 2026 · Patrick Pinard*
