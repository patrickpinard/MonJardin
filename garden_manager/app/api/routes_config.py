"""Routes de configuration : zones, plantations, conseils."""
from datetime import date

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from ..models import db, Zone, Planting

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

    try:
        low = float(form.get("moisture_threshold_low", zone.moisture_threshold_low))
        high = float(form.get("moisture_threshold_high", zone.moisture_threshold_high))
        duration = int(form.get("irrigation_duration_min", zone.irrigation_duration_min))
        if 0 < low < high <= 100:
            zone.moisture_threshold_low = low
            zone.moisture_threshold_high = high
        if duration > 0:
            zone.irrigation_duration_min = duration
    except (ValueError, TypeError):
        pass

    db.session.commit()
    return redirect(url_for("dashboard.settings"))


@config_bp.get("/planting")
def planting_page():
    advisor = current_app.extensions["planting_advisor"]
    zones = Zone.query.order_by(Zone.zone_id).all()
    current_month = date.today().month
    plantings_by_zone = {}
    advice_by_zone = {}
    warnings_by_zone = {}
    for zone in zones:
        plantings_by_zone[zone.zone_id] = (
            Planting.query.filter_by(zone_id=zone.zone_id)
            .order_by(Planting.planted_date.desc()).all()
        )
        advice_by_zone[zone.zone_id] = advisor.get_planting_advice(zone.zone_id, current_month)
        warnings_by_zone[zone.zone_id] = advisor.check_zone_compatibility(zone.zone_id)
    all_vegetables = advisor.get_all_vegetables()
    golden = advisor.get_golden_associations()
    return render_template(
        "planting.html",
        zones=zones,
        plantings_by_zone=plantings_by_zone,
        advice_by_zone=advice_by_zone,
        warnings_by_zone=warnings_by_zone,
        all_vegetables=all_vegetables,
        golden_associations=golden,
        current_month=current_month,
    )


@config_bp.post("/planting/add")
def add_planting():
    """Ajoute une plantation dans une zone."""
    form = request.form
    try:
        zone_id = int(form.get("zone_id", 0))
        vegetable_name = form.get("vegetable_name", "").strip()
        if not zone_id or not vegetable_name:
            return jsonify({"ok": False, "error": "zone_id et vegetable_name requis"}), 400

        advisor = current_app.extensions["planting_advisor"]
        veg = advisor.get_vegetable(vegetable_name)

        planted_str = form.get("planted_date", "")
        planted = date.fromisoformat(planted_str) if planted_str else date.today()
        harvest_str = form.get("expected_harvest_date", "")
        harvest = date.fromisoformat(harvest_str) if harvest_str else None

        planting = Planting(
            zone_id=zone_id,
            vegetable_name=vegetable_name,
            variety=form.get("variety", ""),
            planted_date=planted,
            expected_harvest_date=harvest,
            water_need=veg.get("water_need", "medium") if veg else form.get("water_need", "medium"),
            status="active",
            notes=form.get("notes", ""),
        )
        db.session.add(planting)
        db.session.commit()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

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

    db.session.commit()
    redirect_to = request.form.get("redirect_to", "planting")
    if redirect_to == "zone":
        zone_id = p.zone_id
        return redirect(url_for("dashboard.zone_detail", zone_id=zone_id))
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/<int:planting_id>/harvest")
def harvest_planting(planting_id: int):
    """Marque une plantation comme récoltée."""
    p = Planting.query.get_or_404(planting_id)
    p.status = "harvested"
    db.session.commit()
    return redirect(url_for("config.planting_page"))


@config_bp.post("/planting/<int:planting_id>/delete")
def delete_planting(planting_id: int):
    """Supprime une plantation."""
    p = Planting.query.get_or_404(planting_id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("config.planting_page"))


@config_bp.get("/api/planting/compatibility/<int:zone_id>")
def zone_compatibility(zone_id: int):
    """API JSON pour vérification compatibilité en temps réel."""
    advisor = current_app.extensions["planting_advisor"]
    warnings = advisor.check_zone_compatibility(zone_id)
    return jsonify({"zone_id": zone_id, "warnings": warnings})
