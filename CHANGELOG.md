# Changelog MonJardin

Toutes les modifications notables sont consignées ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

---

## [5.0] — 2026-04-26

Release de **consolidation UI** : tous les apports v4.x sont validés en production
et l'uniformisation visuelle est finalisée à travers toute l'application.

### UI uniforme — onglets et filtres
- **Onglets actifs** : règle CSS unique → fond vert plein, texte et icônes blancs
  (Dashboard, Zone détail, Conseils, Administration, etc.)
- **Filtres** : structure unifiée (modèle Encyclopédie) sur toutes les pages :
  `filter-bar > filter-section > filter-section-label + filter-row > filter-chip`
- Pages alignées : `/plants`, `/plans`, `/conseils`, `/history`, `/zones/<id>#graphiques`
- Promotion en CSS global de `.filter-bar`, `.filter-section`, `.filter-row`, `.filter-chip`
- `.filter-chip.active` passe en **fond vert plein** (au lieu du tint translucide)

### Alignement parfait des filtres sur la même ligne
- `.filter-bar` : `display: flex; flex-wrap: wrap; align-items: flex-start`
- `.filter-section-label` : `height: 16px` fixe → labels toujours au même y
- `.filter-row` : `min-height: 30px` (= chip height) → chips toujours au même y
- `.filter-chip` : `height: 30px` + `box-sizing: border-box` → button et anchor identiques
- Icônes : `line-height: 1; font-size: 12px` fixe

### Header simplifié
- Pastille **« S »** orange compacte (24×24 carré arrondi) remplace l'ancien
  badge « SIM ×50 🌸 Printemps » qui prenait trop de place
- Clic → `/admin?tab=simulation` (active directement le bon onglet)

### Centralisation de la version
- Variable Jinja `app_version` (= "5.0") + `app_release_date` (= "Avril 2026")
  injectée par le context_processor — un seul endroit à modifier
- Sidebar `v{{ app_version }}`, login footer, page About : tous synchronisés

### Documentation
- README.md : section v5.0 + version footer
- CHANGELOG.md : nouvelle entrée structurée
- CLAUDE.md : version courante 5.0

---

## [4.5] — 2026-04-26

### Photos par zone (PWA mobile)
- Nouveau modèle `ZonePhoto` (id, zone_id, filename UUID, captured_at, caption, file_size_kb)
- Onglet « Photos » sur chaque zone, vue calendrier groupée par mois en accordéon (mois récent ouvert)
- Capture iPhone via `capture="environment"` (caméra arrière) + sélection multiple depuis la galerie
- Lightbox plein écran avec navigation prev/next + clavier (Esc / ← / →)
- Édition de la date (`datetime-local`) et de la légende (200 caractères)
- Suppression et édition **idempotentes** : gèrent les syncs multi-appareils sans erreur 404
- Stockage : `data/uploads/zones/<id>/<uuid>.<ext>` (HEIC/JPG/PNG/WEBP, max 12 Mo)

### Dashboard refondu — 4 onglets en haut
- Onglets **placés en tête** de page (au-dessus du hero) pour visibilité maximale
- 4 onglets : Accueil · Météo · Tâches · Mes zones (au lieu de 2 en v4.0)
- Onglet actif en **fond vert** (style cohérent avec Conseils)
- Mapping JS `DASH_SECTIONS` qui agrège plusieurs sections par onglet logique

### Tab Météo enrichi
- Carte dédiée **Anémomètre** : comparaison vent prévu (Open-Meteo) vs mesuré (capteur QS-FS01)
- Bandeau météo riche 24 h déplacé dans le tab Météo
- Prévisions par jour étendues à 7 jours

### Tab Tâches enrichi
- Intro pédagogique (différence vigilance sanitaire vs tâches du mois)
- Section « Pour aller plus loin » avec liens vers Conseils, Plans, Rotation, Glossaire

### Glossaire — nouvelle catégorie « Familles botaniques »
- 17 nouveaux termes : Solanacées, Cucurbitacées, Brassicacées, Apiacées, Alliacées, Légumineuses, Astéracées, Chénopodiacées, Lamiacées, Poacées, Valérianacées, Rosacées, Boraginacées, Tropaeolacées, Hydrophyllacées, Asparagacées, Polygonacées
- Chaque entrée : définition + tip + détails (nom scientifique, exemples cultivés)
- Total Glossaire : **74 termes** (vs 57 en v4.0)

### Plans pré-faits — 20 plans
- 3 nouveaux plans niveau **★★★ Difficile** :
  - 🌾 Asperges & Rhubarbe (vivaces, engagement 2-3 ans)
  - 🥵 Serre tropicale d'été (aubergine, poivron, piment, basilic à ≥18°C)
  - 🌿 Jardin médicinal & tisanes (hysope, sauge, mélisse, origan, lavande...)
- **4 groupes de filtres** en chips : Niveau · Type (Serre / Plein air) · Saison · Surface

### UI raffinée
- **Pastille « S »** orange compacte dans le header (badge simulation) → clic vers `/admin?tab=simulation`
- **Compost** : drop zone visible sous le plan visuel pour suppression par drag & drop (icône 🗑️ + 🍂 grand format)
- **Bouton « Aide »** sur le plan visuel ouvre un modal explicatif
- Boutons « Effacer l'historique » par zone et « Effacer la grille de rotation »
- Bouton « Rafraîchir » sur la page Plan rotation
- Carte de bienvenue masquable (réactivable depuis Administration)
- Tab « Nouvelle année » dans Administration pour reset annuel

### Page Login enrichie
- Footer affiche désormais **Version + Auteur** (`Version 4.5 · Avril 2026 · Patrick Pinard`)
- Sidebar version centralisée : variable `app_version` du context_processor

### Photos accordéon
- Chaque mois est un `<details>`/`<summary>` repliable (HTML5 natif, pas de JS)
- Mois le plus récent ouvert par défaut, autres pliés → page beaucoup plus compacte

### Bug fixes notables
- **Édition + zoom photos** : refactor avec data-attributes (le `tojson` dans `onclick=""` cassait le quoting HTML)
- **UI mobile header zone** : titre + sous-titre + badges ne se chevauchent plus
- **Plans pré-faits** : audit + corrections de toutes les incompatibilités (17/17 OK avant v4.0, restées validées)

### Endpoints API ajoutés
- `POST /zones/<id>/photos/upload` — multi-fichiers
- `POST /zones/<id>/photos/<id>/delete` (idempotent)
- `POST /zones/<id>/photos/<id>/edit` (idempotent)
- `GET  /zones/<id>/photos/<filename>` — sert le fichier
- `POST /planting/zone/<id>/history/clear` — efface l'historique non-actif d'une zone
- `POST /planting/rotation/clear` — efface la grille de rotation (toutes zones)

### Schéma de base de données (v4.5)
- Nouvelle table `zone_photos` (id, zone_id, filename, captured_at, caption, file_size_kb, width, height)

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
