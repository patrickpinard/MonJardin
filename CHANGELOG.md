# Changelog MonJardin

Toutes les modifications notables sont consignées ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

---

## [4.0] — 2026-04-26

### Plan visuel des plantations — refonte complète
- Grille **case-par-case** (30 cm × 30 cm) calculée d'après les dimensions réelles de la zone
- **Toutes les cases visibles** (vides cliquables pour planter à l'endroit voulu)
- **1 plant = 1 case** (plus de badge `×3`), drag & drop natif HTML5 vers n'importe quelle case libre
- **Multi-cases pour semis** : pour les cultures en ligne (carottes, radis, oignons), création d'une rangée occupant 2 à 8 cases adjacentes
- API `POST /api/zones/<id>/plants/<id>/move` avec contrôle de collision (HTTP 409)
- Migration auto-place les plantings existants à l'installation
- Récapitulatif détaillé sous la grille (compte par espèce/variété)
- Persistance de l'onglet *Plants* (hash URL) après chaque action

### Drag & drop des cartes zones (Dashboard)
- Bouton « Réorganiser » dans l'onglet *Mes zones* (SortableJS)
- API `POST /api/zones/reorder`
- Nouvelle colonne `Zone.display_order` (init = `zone_id`)
- Ordre propagé partout (sidebar, dropdowns, automation cycle)

### Dashboard Option A (page d'accueil épurée)
- Réduction de 4 onglets à **2 onglets** : *Vue d'ensemble* (par défaut) | *Mes zones*
- Hero "Aujourd'hui" + Pulse Score + bandeau météo 24h restent visibles au-dessus
- Vue d'ensemble réorganisée : alertes → prévisions 7j → tâches → récoltes
- Carte « Vent » compactée en pied de la carte Prévisions
- Carte de bienvenue **fermable** par bouton croix (`POST /setup/skip`)

### Page Conseils refondue (9 catégories)
- Nouvelles catégories avec carrousels indépendants : Arrosage · Sol & fertilité · Planification · Plantation · Compagnonnage · **Sous serre / Tunnel** (10 conseils à faire/éviter) · Observation · Lutte naturelle · Saisonnalité
- **Filtre par saison** : Toutes / 🌱 Printemps / ☀️ Été / 🍂 Automne / ❄️ Hiver
- Recherche texte combinée avec le filtre saison
- ~57 conseils au total (vs 12 en v3.0)

### Glossaire enrichi
- Passage de **28 à 57 termes** horticoles
- Cards **toujours déployées** (suppression du toggle « En savoir plus »)
- Images Wikimedia pour 9 termes principaux
- Tri éditorial des catégories (général → pointu)
- Catégorie « Calendrier lunaire » : icône 🔇 → 🌑 pour Nœud lunaire

### Plans pré-faits
- Passage de 8 à **16 plans clé en main** : Pizza 🍕 · Ratatouille · Anti-pucerons 🐞 · Soupe d'automne 🥣 · Salade complète été · Pollinisateurs 🐝 · Potager d'altitude · Premier potager pour enfant 👶
- Modal de confirmation uniformisé (`showConfirm` global)

### Page Graphiques refondue (`/history`)
- 3 graphiques **séparés** mais base de temps commune : Humidité du sol · Températures · Événements d'arrosage (barres)
- Filtre par zone : 5 chips (**Toutes** + 1 par zone) — utilise les noms configurés
- Filtre par période : 24h / 7 jours / 30 jours
- Ces 3 graphiques sont aussi disponibles dans l'onglet *Graphiques* d'une zone (filtrés sur la zone courante)
- Boutons de période en chips style Conseils sur ligne dédiée (fix UI)

### Prévisions météo étendues
- `WeatherService.get_forecast_hourly(days=7)` — paramétrable de 1 à 7 jours
- Open-Meteo `forecast_days=7` (max gratuit) → **bulletin 7 jours** sur le dashboard (vs 2 en v3.0)
- `get_forecast_48h()` conservé en compatibilité (détections gel/maladies)

### Modals uniformes
- Suppression de tous les `confirm()` natifs
- Helpers globaux `confirmDelete(target)`, `confirmResetGarden`, `confirmApplyPlan`
- Nouveaux variants CSS `confirm-primary` (vert), `modal-icon.success`, `modal-icon.info`

### Heures locales (fix bug journal)
- Nouveaux filtres Jinja `localtime` / `localdate` / `localhour` qui convertissent UTC (DB) → Europe/Zurich
- Appliqué sur journal, zone_detail (events + dernier arrosage), dashboard

### Édition variété (fix bug)
- Le calcul du diff de quantité dans le modal Edit filtre désormais par variété
- Tomate Cerise et Tomate Cœur de bœuf manipulables indépendamment

### Page d'administration
- Tab dédié « Nouvelle année » pour reset annuel (archivage des plantations actives, dimensions zones par défaut)
- Modal de confirmation `confirmResetGarden` (orange, action lourde mais réversible via archives)

### Migration DB automatique
- Ajout de `Zone.display_order` (init = `zone_id`)
- Ajout de `Planting.display_order`, `grid_row`, `grid_col`, `grid_w`, `grid_h`
- Auto-placement initial des plantings actifs sur la grille (row-major)

### Compost (drop zone pour suppression)
- Nouvelle drop zone visible sous la grille du plan visuel — glisser un plant dessus = suppression définitive (avec confirmation)
- Icône grand format 🗑️ + 🍂 avec typographie alignée sur le reste de l'UI
- État de survol distinct (rouge) au passage d'un plant

### Plans pré-faits — fixes de compatibilité
- Audit automatique des `bad_companions` sur tous les plans : **17/17 plans compatibles**
- "Aromates de cuisine" refondu en "Aromates frais" (Basilic + Persil + Ciboulette + Coriandre + Cerfeuil)
- Nouveau plan "Aromates méditerranéens" (Thym + Romarin + Sauge + Origan + Lavande + Sarriette)
- Corrections : Serre d'été (Concombre retiré), Légumes racines (Betterave + Panais retirés, Oignon + Navet ajoutés), Balcon (Thym retiré), Ratatouille (Thym → Origan), Soupe d'automne (Panais + Céleri + Persil + Potiron + Poireau + Courgette retirés, Pomme de terre ajoutée), Salade complète (Concombre retiré), Potager d'altitude (Épinard → Roquette)
- Auto-distribution sur la grille à l'application : chaque plant placé dans la première case libre (row-major)
- Avertissement flash si incompatibilités détectées avant application

### Aide & maintenance
- Bouton **« Aide »** sur le plan visuel ouvre un modal explicatif (au lieu d'un long bandeau qui débordait sur petit écran)
- Bouton **« Effacer l'historique »** dans l'onglet Configuration d'une zone : supprime les plantations harvested/removed/archived/planned ; les actives sont préservées
- Bouton **« Effacer la grille »** sur la page Plan rotation : supprime l'historique de TOUTES les zones
- Bouton **« Rafraîchir »** sur la page Plan rotation pour recharger l'état courant

### Endpoints API ajoutés
- `POST /api/zones/reorder`
- `POST /api/zones/<id>/plants/reorder`
- `POST /api/zones/<id>/plants/<id>/move`
- `POST /setup/skip`
- `POST /planting/zone/<id>/history/clear`
- `POST /planting/rotation/clear`

---

## [3.0] — 2026-04 (rappel)

### Dashboard contextuel
- Hero "Aujourd'hui" + Pulse Score 0-100 + bandeau météo 24h
- Bandeau d'actions concrètes (zones à arroser, lucarne ouverte, récoltes)
- Onglet Tâches du mois avec validation

### Plan visuel partagé
- Grille soil-brown style App Store (proportionnelle aux dimensions de la zone)
- Modal Quick-Plant avec recherche live, filtres catégorie, compagnonnage temps réel

### Conseils refondu en 4 onglets
- Bonnes pratiques · Associations · Calendrier saisonnier · Plantations du mois

### Sécurité & automatisation
- Arrêt automatique d'arrosage manuel après durée max
- Plage horaire d'arrosage recommandée par zone
- Statut lucarne en temps réel pendant le mouvement (~30s)

### Données plantes
- Espacement réaliste pour 22 espèces semées en ligne (`space_row_cm`)
- Suppression de la catégorie « Fruits » → 55 espèces

---

## [2.0] — 2026-04 (rappel)

- Dashboard redessiné — navigation par onglets
- Encyclopédie 65 espèces, filtres catégorie/saison
- Profil météo dynamique avec effet immédiat sur l'humidité
- Diagnostics étendus : Arduino (6 onglets), Raspberry Pi (3 onglets)
- Alertes email paramétrables
- Script `update_pi.sh` compatible Bookworm / PEP 668

---

## [1.0] — 2026-03

- Première release : 4 zones, automation arrosage + lucarne, dashboard, journal, simulation
