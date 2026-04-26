"""Routes de configuration : zones, plantations, conseils."""
from datetime import date

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from ..models import db, Zone, Planting, JournalEntry

config_bp = Blueprint("config", __name__)


@config_bp.post("/settings/zone/<int:zone_id>")
def update_zone(zone_id: int):
    """Met à jour la configuration d'une zone."""
    zone = Zone.query.get_or_404(zone_id)
    form = request.form

    name = form.get("zone_name", "").strip()
    if name:
        zone.name = name[:40]

    mode = form.get("irrigation_mode", zone.irrigation_mode)
    if mode in ("auto", "manual", "disabled"):
        zone.irrigation_mode = mode

    # Serre vitrée (checkbox HTML — absent du form quand non coché)
    zone.has_roof = "has_roof" in form

    try:
        low = float(form.get("moisture_threshold_low", zone.moisture_threshold_low))
        high = float(form.get("moisture_threshold_high", zone.moisture_threshold_high))
        duration = int(form.get("irrigation_duration_min", zone.irrigation_duration_min))
        if 0 < low < high <= 100:
            zone.moisture_threshold_low = low
            zone.moisture_threshold_high = high
        else:
            flash(
                f"Seuils invalides ({low:.0f}% / {high:.0f}%) — "
                "le seuil bas doit être inférieur au seuil haut (0–100%).",
                "warning",
            )
        if duration > 0:
            zone.irrigation_duration_min = duration
        else:
            flash("Durée d'irrigation invalide — valeur ignorée.", "warning")
    except Exception:
        flash("Valeurs de seuils ou durée non valides — modifications ignorées.", "danger")

    try:
        cur_length = getattr(zone, "length_m", None) or 2.0
        cur_width  = getattr(zone, "width_m",  None) or 1.0
        length = float(form.get("length_m", cur_length))
        width  = float(form.get("width_m",  cur_width))
        if 0.1 <= length <= 50:
            zone.length_m = round(length, 2)
        if 0.1 <= width <= 50:
            zone.width_m = round(width, 2)
    except Exception:
        pass

    # Log de la modification
    db.session.add(JournalEntry(
        level="info",
        message=(
            f"⚙️ Configuration modifiée : {zone.name} (Z{zone.zone_id}) — "
            f"mode {zone.irrigation_mode}, seuils {int(zone.moisture_threshold_low)}–{int(zone.moisture_threshold_high)}%, "
            f"durée {zone.irrigation_duration_min}min"
        ),
    ))
    db.session.commit()
    redirect_to = form.get("redirect_to", "settings")
    if redirect_to == "zone":
        # Modification de zone → retour sur l'onglet Configuration
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#config")
    return redirect(url_for("dashboard.settings"))


MONTH_NAMES_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def _planting_display_items(plantings, sowing_type_map, emoji_map, today):
    """Convertit une liste de Planting en items d'affichage :
    - semis actifs → un seul item groupé par espèce (type='seed_group')
    - plants individuels + semis non-actifs → un item chacun (type='plant')
    """
    from collections import OrderedDict

    def _progress(p):
        if p.planted_date and p.expected_harvest_date and p.status == "active":
            total = (p.expected_harvest_date - p.planted_date).days
            elapsed = (today - p.planted_date).days
            days_left = (p.expected_harvest_date - today).days
            pct = max(0, min(100, int(elapsed / total * 100))) if total > 0 else 100
        else:
            pct = 0
            days_left = None
        return pct, days_left

    seed_groups: dict = OrderedDict()
    items = []

    for p in plantings:
        is_seed = sowing_type_map.get(p.vegetable_name, "plant") == "seed" and p.status == "active"
        if is_seed:
            seed_groups.setdefault(p.vegetable_name, []).append(p)
        else:
            pct, days_left = _progress(p)
            items.append({
                "kind": "plant",
                "planting": p,
                "emoji": emoji_map.get(p.vegetable_name, "🌱"),
                "pct": pct,
                "days_left": days_left,
            })

    seed_items = []
    for vname, plist in seed_groups.items():
        rep = plist[0]
        pct, days_left = _progress(rep)
        seed_items.append({
            "kind": "seed_group",
            "vegetable_name": vname,
            "emoji": emoji_map.get(vname, "🌱"),
            "count": len(plist),
            "rep": rep,
            "pct": pct,
            "days_left": days_left,
        })

    return seed_items + items


@config_bp.get("/planting")
def planting_page():
    advisor = current_app.extensions["planting_advisor"]
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    current_month = date.today().month
    today = date.today()
    plantings_by_zone = {}
    warnings_by_zone = {}
    for zone in zones:
        plantings_by_zone[zone.zone_id] = (
            Planting.query.filter_by(zone_id=zone.zone_id)
            .order_by(Planting.planted_date.desc()).all()
        )
        warnings_by_zone[zone.zone_id] = advisor.check_zone_compatibility(zone.zone_id)
    all_vegetables = sorted(advisor.get_all_vegetables(), key=lambda v: v["name"])
    golden = advisor.get_golden_associations()
    seasonal_advice = advisor.get_seasonal_advice(current_month)
    emoji_map       = {v["name"]: v.get("emoji", "🌱")         for v in all_vegetables}
    sowing_type_map = {v["name"]: v.get("sowing_type", "plant") for v in all_vegetables}

    # Items d'affichage pré-calculés (groupage semis fait côté Python)
    display_by_zone = {
        zone.zone_id: _planting_display_items(
            plantings_by_zone.get(zone.zone_id, []),
            sowing_type_map, emoji_map, today
        )
        for zone in zones
    }

    # Capacités restantes par zone/légume pour le hint quantité.
    # Utilise space_row_cm pour les semis en ligne (carotte, radis, etc.) ;
    # retombe sur space_cm pour les plants individuels (grille carrée).
    zone_capacity: dict = {}
    for zone in zones:
        zone_capacity[zone.zone_id] = {}
        for v in all_vegetables:
            sp     = v.get("space_cm", 30)
            sp_row = v.get("space_row_cm", sp)
            cols = max(1, int((getattr(zone, "length_m", 2.0) or 2.0) * 100 / sp))
            rows = max(1, int((getattr(zone, "width_m",  1.0) or 1.0) * 100 / sp_row))
            active_count = sum(
                1 for p in plantings_by_zone.get(zone.zone_id, [])
                if p.status == "active" and p.vegetable_name == v["name"]
            )
            zone_capacity[zone.zone_id][v["name"]] = max(0, cols * rows - active_count)

    return render_template(
        "planting.html",
        zones=zones,
        plantings_by_zone=plantings_by_zone,
        display_by_zone=display_by_zone,
        warnings_by_zone=warnings_by_zone,
        all_vegetables=all_vegetables,
        golden_associations=golden,
        current_month=current_month,
        month_name=MONTH_NAMES_FR.get(current_month, ""),
        seasonal_advice=seasonal_advice,
        today_date=today,
        emoji_map=emoji_map,
        sowing_type_map=sowing_type_map,
        zone_capacity=zone_capacity,
    )


@config_bp.post("/planting/add")
def add_planting():
    """Ajoute une ou plusieurs plantations dans une zone."""
    form = request.form
    try:
        zone_id = int(form.get("zone_id", 0))
        vegetable_name = form.get("vegetable_name", "").strip()
        if not zone_id or not vegetable_name:
            flash("Zone et légume requis.", "danger")
            return redirect(url_for("config.planting_page"))

        advisor = current_app.extensions["planting_advisor"]
        veg = advisor.get_vegetable(vegetable_name)

        planted_str = form.get("planted_date", "")
        planted = date.fromisoformat(planted_str) if planted_str else date.today()
        harvest_str = form.get("expected_harvest_date", "")
        harvest = date.fromisoformat(harvest_str) if harvest_str else None
        water_need = veg.get("water_need", "medium") if veg else form.get("water_need", "medium")

        try:
            quantity = max(1, min(50, int(form.get("quantity", 1))))
        except (ValueError, TypeError):
            quantity = 1

        # ── Position cible dans la grille (depuis le modal Quick-Plant) ──
        try:
            grid_row = max(0, int(form.get("grid_row", 0)))
            grid_col = max(0, int(form.get("grid_col", 0)))
            grid_w   = max(1, int(form.get("grid_w",   1)))
            grid_h   = max(1, int(form.get("grid_h",   1)))
        except (ValueError, TypeError):
            grid_row = grid_col = 0
            grid_w = grid_h = 1

        zone_obj = Zone.query.get(zone_id)
        CELL_CM = 30
        cols = max(4, int((zone_obj.length_m or 2.0) * 100 / CELL_CM)) if zone_obj else 8
        rows = max(2, int((zone_obj.width_m  or 1.0) * 100 / CELL_CM)) if zone_obj else 4

        # Si grid_w > 1 → mode "rangée" : 1 seule plantation occupant N cases
        if grid_w > 1:
            # Clamp pour rester dans la grille
            if grid_col + grid_w > cols:
                grid_w = max(1, cols - grid_col)
            db.session.add(Planting(
                zone_id=zone_id,
                vegetable_name=vegetable_name,
                variety=form.get("variety", ""),
                planted_date=planted,
                expected_harvest_date=harvest,
                water_need=water_need,
                status="active",
                notes=form.get("notes", ""),
                grid_row=grid_row, grid_col=grid_col,
                grid_w=grid_w, grid_h=grid_h,
            ))
        else:
            # Mode normal : N plantations indépendantes, posées dans les cases libres
            occupied = set()
            for op in Planting.query.filter_by(zone_id=zone_id, status="active").all():
                ow, oh = max(1, op.grid_w or 1), max(1, op.grid_h or 1)
                for dr in range(oh):
                    for dc in range(ow):
                        occupied.add(((op.grid_row or 0) + dr, (op.grid_col or 0) + dc))
            # Première case = celle cliquée si libre
            placed = 0
            # Génère les cases dans l'ordre : (grid_row, grid_col) d'abord, puis row-major
            candidates = []
            if (grid_row, grid_col) not in occupied:
                candidates.append((grid_row, grid_col))
            for r in range(rows):
                for c in range(cols):
                    if (r, c) not in occupied and (r, c) != (grid_row, grid_col):
                        candidates.append((r, c))
            for r, c in candidates:
                if placed >= quantity:
                    break
                db.session.add(Planting(
                    zone_id=zone_id,
                    vegetable_name=vegetable_name,
                    variety=form.get("variety", ""),
                    planted_date=planted,
                    expected_harvest_date=harvest,
                    water_need=water_need,
                    status="active",
                    notes=form.get("notes", ""),
                    grid_row=r, grid_col=c,
                    grid_w=1, grid_h=1,
                ))
                occupied.add((r, c))
                placed += 1

        # Log dans le journal
        zname = zone_obj.name if zone_obj else f"Z{zone_id}"
        emoji_v = (veg.get("emoji", "🌱") if veg else "🌱")
        if grid_w > 1:
            msg = f"🌱 Rangée semée : {emoji_v} {vegetable_name} sur {grid_w} cases dans {zname}"
        else:
            qty_label = f"{quantity}× " if quantity > 1 else ""
            msg = f"🌱 Plantation : {qty_label}{emoji_v} {vegetable_name} ajouté(s) dans {zname}"
        db.session.add(JournalEntry(level="info", message=msg))
        db.session.commit()
        if quantity > 1 and grid_w == 1:
            flash(f"{quantity} plants de {vegetable_name} ajoutés.", "success")
    except Exception as e:
        flash(f"Erreur lors de l'ajout : {e}", "danger")

    # Redirige vers la zone si demandé (modal Quick-Plant), sinon Plantation
    redirect_to = form.get("redirect_to", "")
    if redirect_to == "zone" and zone_id:
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#plants")
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/<int:planting_id>/edit")
def edit_planting(planting_id: int):
    """Met à jour une plantation existante."""
    p = Planting.query.get_or_404(planting_id)
    form = request.form

    variety = form.get("variety", "").strip()
    p.variety = variety

    harvest_str = form.get("expected_harvest_date", "")
    if harvest_str:
        try:
            p.expected_harvest_date = date.fromisoformat(harvest_str)
        except ValueError:
            pass

    notes = form.get("notes", "").strip()
    p.notes = notes

    status = form.get("status", p.status)
    if status in ("planned", "active", "harvested", "removed"):
        p.status = status

    water_need = form.get("water_need", p.water_need)
    if water_need in ("low", "medium", "high"):
        p.water_need = water_need

    # Ajustement du nombre total de plants de cette espèce dans cette zone
    # (en s'assurant qu'au moins le plant édité reste)
    quantity_str = form.get("quantity", "").strip()
    if quantity_str:
        try:
            new_qty = int(quantity_str)
        except ValueError:
            new_qty = None
        if new_qty is not None and new_qty >= 1:
            # Filtrer par espèce ET variété : permet de différencier
            # 'Tomate Cœur de bœuf' vs 'Tomate Cerise' (chacune sa quantité)
            target_variety = (p.variety or "").strip()
            actives_all = (Planting.query
                           .filter_by(zone_id=p.zone_id,
                                      vegetable_name=p.vegetable_name,
                                      status="active")
                           .order_by(Planting.id.desc()).all())
            actives = [a for a in actives_all if (a.variety or "").strip() == target_variety]
            current_count = len(actives)
            diff = new_qty - current_count
            if diff > 0:
                # Créer N copies du planting édité (même variété)
                for _ in range(diff):
                    db.session.add(Planting(
                        zone_id=p.zone_id,
                        vegetable_name=p.vegetable_name,
                        variety=p.variety,
                        planted_date=p.planted_date,
                        expected_harvest_date=p.expected_harvest_date,
                        water_need=p.water_need,
                        status="active",
                        notes=p.notes,
                    ))
            elif diff < 0:
                # Supprimer les plus récents de la même variété (en épargnant l'édité)
                removed = 0
                for other in actives:
                    if other.id == p.id:
                        continue
                    db.session.delete(other)
                    removed += 1
                    if removed >= -diff:
                        break

    # Log dans le journal
    zone_obj = Zone.query.get(p.zone_id)
    zname = zone_obj.name if zone_obj else f"Z{p.zone_id}"
    db.session.add(JournalEntry(
        level="info",
        message=f"✏️ Plantation modifiée : {p.vegetable_name} dans {zname}",
    ))
    db.session.commit()
    redirect_to = request.form.get("redirect_to", "planting")
    if redirect_to == "zone":
        zone_id = p.zone_id
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#plants")
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/<int:planting_id>/harvest")
def harvest_planting(planting_id: int):
    """Marque une plantation comme récoltée."""
    p = Planting.query.get_or_404(planting_id)
    p.status = "harvested"
    zone_obj = Zone.query.get(p.zone_id)
    zname = zone_obj.name if zone_obj else f"Z{p.zone_id}"
    db.session.add(JournalEntry(
        level="success",
        message=f"🧺 Récolte : {p.vegetable_name} dans {zname}",
    ))
    db.session.commit()
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/<int:planting_id>/delete")
def delete_planting(planting_id: int):
    """Supprime une plantation."""
    p = Planting.query.get_or_404(planting_id)
    zone_id = p.zone_id
    veg_name = p.vegetable_name
    zone_obj = Zone.query.get(zone_id)
    zname = zone_obj.name if zone_obj else f"Z{zone_id}"
    db.session.delete(p)
    db.session.add(JournalEntry(
        level="warning",
        message=f"🗑 Plantation supprimée : {veg_name} de {zname}",
    ))
    db.session.commit()
    redirect_to = request.form.get("redirect_to", "planting")
    if redirect_to == "zone":
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#plants")
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/zone/<int:zone_id>/species/<vegetable_name>/delete")
def delete_species_from_zone(zone_id: int, vegetable_name: str):
    """Supprime TOUTES les plantations actives d'une espèce dans une zone."""
    plantings = Planting.query.filter_by(
        zone_id=zone_id,
        vegetable_name=vegetable_name,
        status="active",
    ).all()
    count = len(plantings)
    for p in plantings:
        db.session.delete(p)
    zone_obj = Zone.query.get(zone_id)
    zname = zone_obj.name if zone_obj else f"Z{zone_id}"
    db.session.add(JournalEntry(
        level="warning",
        message=f"🗑 Espèce supprimée : {count}× {vegetable_name} de {zname}",
    ))
    db.session.commit()
    flash(f"{count} plantation(s) de {vegetable_name} supprimée(s).", "success")
    redirect_to = request.form.get("redirect_to", "zone")
    if redirect_to == "zone":
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#plants")
    return redirect(url_for("config.planting_page"))


@config_bp.get("/api/planting/compatibility/<int:zone_id>")
def zone_compatibility(zone_id: int):
    """API JSON pour vérification compatibilité en temps réel."""
    advisor = current_app.extensions["planting_advisor"]
    warnings = advisor.check_zone_compatibility(zone_id)
    return jsonify({"zone_id": zone_id, "warnings": warnings})
