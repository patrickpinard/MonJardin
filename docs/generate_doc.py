"""Génère la documentation technique MonJardin au format PDF."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import Flowable
import datetime

# ── Couleurs ──────────────────────────────────────────────────────────────
C_GREEN      = HexColor("#2D5F2D")
C_GREEN_LIGHT= HexColor("#4CAF50")
C_ORANGE     = HexColor("#FF9F0A")
C_BLUE       = HexColor("#0A84FF")
C_RED        = HexColor("#FF453A")
C_GRAY_BG    = HexColor("#F5F5F7")
C_GRAY_DARK  = HexColor("#3A3A3C")
C_BORDER     = HexColor("#D1D1D6")
C_HEADER_BG  = HexColor("#1C1C1E")
C_CODE_BG    = HexColor("#EFEFEF")

OUT_PATH = "/Users/patrick/Github/MonJardin/docs/MonJardin_Documentation_Technique.pdf"

# ── Styles ────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def s(name, **kw):
    return ParagraphStyle(name, **kw)

TITLE = s("TITLE", fontSize=28, fontName="Helvetica-Bold", textColor=C_GREEN,
          spaceAfter=6, alignment=TA_LEFT)
SUBTITLE = s("SUBTITLE", fontSize=13, fontName="Helvetica", textColor=C_GRAY_DARK,
             spaceAfter=20, alignment=TA_LEFT)
H1 = s("H1", fontSize=16, fontName="Helvetica-Bold", textColor=C_GREEN,
        spaceBefore=18, spaceAfter=8, borderPadding=(0,0,4,0))
H2 = s("H2", fontSize=13, fontName="Helvetica-Bold", textColor=C_GRAY_DARK,
        spaceBefore=12, spaceAfter=6)
H3 = s("H3", fontSize=11, fontName="Helvetica-Bold", textColor=C_GREEN,
        spaceBefore=8, spaceAfter=4)
BODY = s("BODY", fontSize=10, fontName="Helvetica", textColor=C_GRAY_DARK,
         spaceAfter=5, leading=15, alignment=TA_JUSTIFY)
BODY_SMALL = s("BODY_SMALL", fontSize=9, fontName="Helvetica", textColor=C_GRAY_DARK,
               spaceAfter=3, leading=13)
CODE = s("CODE", fontSize=8.5, fontName="Courier", textColor=HexColor("#1A1A1A"),
         backColor=C_CODE_BG, borderPadding=4, spaceAfter=6, leading=12)
NOTE = s("NOTE", fontSize=9, fontName="Helvetica-Oblique", textColor=HexColor("#636366"),
         spaceAfter=4, leftIndent=12)
WARN = s("WARN", fontSize=9.5, fontName="Helvetica-Bold", textColor=C_RED,
         spaceAfter=4, leftIndent=12)
CAPTION = s("CAPTION", fontSize=8, fontName="Helvetica-Oblique", textColor=HexColor("#8E8E93"),
            alignment=TA_CENTER, spaceAfter=8)

def p(text, style=BODY): return Paragraph(text, style)
def sp(h=6): return Spacer(1, h)
def hr(): return HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=8, spaceBefore=4)

# ── Table helper ──────────────────────────────────────────────────────────
def make_table(data, col_widths, header=True):
    style = [
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, C_GRAY_BG]),
        ("GRID",        (0,0), (-1,-1), 0.4, C_BORDER),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING",(0,0), (-1,-1), 7),
    ]
    if header:
        style += [
            ("BACKGROUND",  (0,0), (-1,0), C_GREEN),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("TEXTCOLOR",   (0,0), (-1,0), white),
            ("FONTSIZE",    (0,0), (-1,0), 9.5),
        ]
    rows = [[Paragraph(str(c), ParagraphStyle("tc", fontSize=9,
             fontName="Helvetica-Bold" if (header and i==0) else "Helvetica",
             textColor=white if (header and i==0) else C_GRAY_DARK,
             leading=12)) for c in row]
            for i, row in enumerate(data)]
    rows = [[Paragraph(str(c), ParagraphStyle("tc", fontSize=9,
             fontName="Helvetica",
             textColor=white if (header and ri==0) else C_GRAY_DARK,
             leading=12)) for c in row]
            for ri, row in enumerate(data)]
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style))
    return t

def api_table(rows):
    """Table spéciale pour les endpoints API."""
    header = ["Endpoint", "Méthode", "Description", "Réponse / Corps"]
    full = [header] + rows
    return make_table(full, [5.5*cm, 1.8*cm, 6*cm, 4.2*cm])

# ── DOCUMENT ─────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2.2*cm, bottomMargin=2.2*cm,
        title="MonJardin — Documentation Technique v1.0",
        author="Patrick Pinard",
    )

    story = []

    # ── PAGE DE GARDE ─────────────────────────────────────────────────────
    story += [
        sp(30),
        p("🌱 MonJardin", TITLE),
        p("Documentation Technique — Version 1.0", SUBTITLE),
        hr(),
        sp(4),
        p("Système automatisé de gestion de jardin potager", s("sub2", fontSize=12, fontName="Helvetica", textColor=C_GRAY_DARK, spaceAfter=3)),
        p("Raspberry Pi 5 · Arduino Edge Control · Flask · SQLite", s("sub3", fontSize=10, fontName="Helvetica-Oblique", textColor=HexColor("#8E8E93"), spaceAfter=20)),
        sp(8),
        make_table([
            ["Auteur",    "Patrick Pinard"],
            ["Version",   "1.0"],
            ["Date",      datetime.date.today().strftime("%d %B %Y")],
            ["Localisation", "Vullierens, Vaud, Suisse"],
            ["Firmware",  "1.0.0 (PlatformIO / Arduino Edge Control + MKR WiFi 1010)"],
            ["Backend",   "Python 3.10 · Flask 3.x · APScheduler"],
        ], [5*cm, 11.5*cm], header=False),
        PageBreak(),
    ]

    # ── SOMMAIRE ──────────────────────────────────────────────────────────
    story += [
        p("Table des matières", H1),
        hr(),
        make_table([
            ["1", "Architecture du système",           "3"],
            ["2", "Matériel requis",                   "3"],
            ["3", "Montage — Capteurs sol (SoilWatch 10)","4"],
            ["4", "Montage — Capteurs température DS18B20","5"],
            ["5", "Montage — Anémomètre",                      "6"],
            ["6", "Montage — Vannes 24V (GARDENA)",           "6"],
            ["7", "Montage — Vérin linéaire (lucarne)",       "7"],
            ["8", "Enclosure Kit — LCD 2×16 + Bouton",        "8"],
            ["9", "Alimentation",                             "9"],
            ["10","Firmware Arduino — Configuration",          "9"],
            ["11","API REST Arduino ↔ Raspberry Pi",          "10"],
            ["12","Bascule Simulation → Production",          "13"],
            ["12","Checklist de mise en service",      "13"],
        ], [1*cm, 12*cm, 3.5*cm], header=False),
        PageBreak(),
    ]

    # ── 1. ARCHITECTURE ────────────────────────────────────────────────────
    story += [
        p("1. Architecture du système", H1), hr(),
        p("""MonJardin est un système en deux couches communicantes via WiFi.
        Le <b>Raspberry Pi 5</b> exécute le serveur Flask, le moteur de décision
        (arrosage, toit, météo) et l'interface web PWA.
        L'<b>Arduino Edge Control</b> gère exclusivement le hardware :
        acquisition des capteurs et pilotage des actionneurs.
        La communication est unidirectionnelle : le Raspberry interroge l'Arduino
        via API REST JSON toutes les 60 secondes."""),
        sp(6),
        make_table([
            ["Couche",        "Matériel",              "Rôle"],
            ["Décision",      "Raspberry Pi 5",        "Flask · APScheduler · SQLite · Météo Open-Meteo · Interface PWA"],
            ["Terrain",       "Arduino Edge Control",  "Lecture capteurs · Pilotage vannes · Contrôle vérin · Serveur HTTP"],
            ["WiFi",          "MKR WiFi 1010",         "Connectivité WiFi 802.11 b/g/n (slot MKR du Edge Control)"],
            ["Capteurs sol",  "SoilWatch 10 ×4",       "Humidité volumétrique par zone (Input 0-5V CH01–04)"],
            ["Température",   "DS18B20 ×2",            "Température extérieure + intérieure serre (OneWire)"],
            ["Vent",          "Anémomètre QS-FS01",    "Vitesse vent km/h — tension analogique 0.4–2.0 V (Input CH05)"],
            ["Irrigation",    "Vannes GARDENA 24V ×4", "Solénoïde NC — relais latching (Latching OUT 1–4)"],
            ["Lucarne",       "Vérin linéaire 12V",    "Ouverture toit serre (H-bridge + fins de course)"],
            ["Affichage",     "Enclosure Kit",         "LCD 2×16 NDS1602A + bouton POWER_ON"],
        ], [3.5*cm, 4.5*cm, 8.5*cm]),
        PageBreak(),
    ]

    # ── 2. MATÉRIEL ────────────────────────────────────────────────────────
    story += [
        p("2. Matériel requis", H1), hr(),
        make_table([
            ["Référence",                "Qté", "Rôle",                              "Interface Arduino"],
            ["Arduino Edge Control",     "1",   "Contrôleur principal terrain",       "—"],
            ["Arduino MKR WiFi 1010",    "1",   "WiFi 802.11 b/g/n (slot MKR)",      "Slot MKR Edge Control"],
            ["Raspberry Pi 5 (4 GB)",    "1",   "Serveur Flask / décision",           "WiFi 802.11ac"],
            ["SoilWatch 10",             "4",   "Capteur humidité sol 0–100%",        "Input 0-5V CH01–CH04"],
            ["DS18B20 (sonde étanche)",  "2",   "Température ext. + serre",           "OneWire D5"],
            ["Anémomètre QS-FS01",       "1",   "Vitesse vent (tension 0.4–2.0 V)",  "Input 0-5V CH05"],
            ["GARDENA 24V (réf. 900904101)","4","Irrigation — solénoïde NC",          "Latching OUT 1–4"],
            ["Vérin linéaire 12V",       "1",   "Ouverture lucarne serre",            "GPIO D7/D8 + D9/D10"],
            ["Edge Control Enclosure Kit","1",  "LCD 2×16 NDS1602A + bouton",        "TCA6424A Expander + POWER_ON"],
            ["Alimentation 24V / 5A",    "1",   "Vannes GARDENA solénoïde",           "—"],
            ["Alimentation 12V / 2A",    "1",   "Vérin linéaire",                     "—"],
            ["Alimentation 5V / 5A USB-C","1",  "Raspberry Pi 5",                     "—"],
            ["Boîtier IP67",             "1",   "Protection intempéries",             "—"],
        ], [5.2*cm, 1.2*cm, 5.2*cm, 5*cm]),
        PageBreak(),
    ]

    # ── 3. CAPTEURS SOL ────────────────────────────────────────────────────
    story += [
        p("3. Montage — Capteurs sol SoilWatch 10", H1), hr(),
        p("Les capteurs SoilWatch 10 mesurent l'humidité volumétrique du sol par résistivité électrique "
          "et fournissent une tension analogique de <b>0 V (sec) à 3 V (saturé)</b>. "
          "L'Arduino Edge Control les lit via son <b>InputExpander</b> avec ADC 16-bit."),
        sp(4),
        p("Connexion physique", H2),
        make_table([
            ["Zone", "Canal InputExpander", "Fil Signal",     "Fil GND",    "Alimentation"],
            ["Zone 1 — Serre",    "Canal 0  (AI0)", "Jaune/Blanc", "Noir", "3.3V (rouge)"],
            ["Zone 2 — Potager",  "Canal 1  (AI1)", "Jaune/Blanc", "Noir", "3.3V (rouge)"],
            ["Zone 3 — Mi-ombre", "Canal 2  (AI2)", "Jaune/Blanc", "Noir", "3.3V (rouge)"],
            ["Zone 4 — Aromates", "Canal 3  (AI3)", "Jaune/Blanc", "Noir", "3.3V (rouge)"],
        ], [3.5*cm, 4*cm, 3.5*cm, 2.5*cm, 3*cm]),
        sp(6),
        p("Méthode de lecture (firmware)", H2),
        p("""L'InputExpander de l'Edge Control remplace les broches ADC classiques.
        Il est initialisé avec <b>Expander.begin()</b>.
        Chaque lecture est la moyenne de <b>8 échantillons</b> (ADC_SAMPLES)
        espacés de 5 ms pour filtrer le bruit.
        La conversion ADC→% utilise une interpolation linéaire entre deux valeurs de calibration :"""),
        p("<b>humidité (%) = 100 × (ADC_DRY − ADC_mesuré) / (ADC_DRY − ADC_WET)</b>", CODE),
        sp(4),
        p("Calibration", H2),
        make_table([
            ["Paramètre",  "Valeur par défaut", "Signification"],
            ["ADC_DRY",    "3100",              "Valeur ADC lorsque le capteur est dans l'air sec"],
            ["ADC_WET",    "1200",              "Valeur ADC lorsque le capteur est dans l'eau"],
        ], [4*cm, 4*cm, 8.5*cm]),
        sp(4),
        p("⚠️  Ces valeurs sont globales (même calibration pour les 4 zones). "
          "Pour une précision maximale, calibrer chaque capteur individuellement "
          "avec setCalibration(zone_id, dry, wet) dans main.cpp.", WARN),
        sp(4),
        p("Notes d'installation", H2),
        p("• Insérer le capteur verticalement dans le sol à <b>10–15 cm</b> de profondeur, "
          "au niveau des racines actives.", BODY_SMALL),
        p("• Ne pas plier le câble à moins de <b>5 cm</b> du boîtier.", BODY_SMALL),
        p("• Protéger les connecteurs avec du ruban auto-amalgamant ou une gaine thermo.", BODY_SMALL),
        p("• Le capteur fonctionne dans des sols de conductivité EC < 2 mS/cm "
          "(sols standard non-fertilisés intensivement).", BODY_SMALL),
        PageBreak(),
    ]

    # ── 4. TEMPÉRATURE DS18B20 ─────────────────────────────────────────────
    story += [
        p("4. Montage — Capteurs température DS18B20", H1), hr(),
        p("Les DS18B20 communiquent via le protocole <b>1-Wire (OneWire)</b> sur une seule broche "
          "de données. Les deux capteurs partagent le <b>même bus</b> (broche D5). "
          "Chaque capteur possède un identifiant 64-bit unique gravé en usine."),
        sp(4),
        p("Connexion physique — bus partagé", H2),
        make_table([
            ["Capteur",                  "Pin D5 (Data)", "GND",  "VCC",  "Résistance pull-up"],
            ["DS18B20 #0 — Extérieur",   "Fil jaune",     "Noir", "Rouge (3.3V)", "4.7 kΩ entre Data et VCC"],
            ["DS18B20 #1 — Serre intérieure","Fil jaune", "Noir", "Rouge (3.3V)", "(une seule résistance sur le bus)"],
        ], [4.5*cm, 3*cm, 2*cm, 3*cm, 4*cm]),
        sp(4),
        p("⚠️  <b>Important :</b> La résistance pull-up 4.7 kΩ est obligatoire entre la broche Data "
          "et VCC. Sans elle, les lectures retournent −127°C.", WARN),
        sp(4),
        p("Méthode de lecture (firmware)", H2),
        p("La bibliothèque <b>DallasTemperature</b> gère l'adressage OneWire automatiquement. "
          "L'ordre des capteurs dépend de leur ordre de découverte sur le bus "
          "(setWaitForConversion(false) pour mode asynchrone) :"),
        p("• Index 0 → getExterior() → température extérieure", BODY_SMALL),
        p("• Index 1 → getGreenhouse() → température intérieure serre", BODY_SMALL),
        sp(4),
        p("⚠️  Si les deux capteurs sont inversés (serre affiche température extérieure), "
          "inverser physiquement les capteurs ou changer les index dans TempSensor.cpp.", WARN),
        p("Lecture toutes les <b>30 secondes</b> (TEMP_READ_INTERVAL = 30 000 ms). "
          "En cas de lecture invalide (−127°C ou 85°C), la dernière valeur connue est conservée.", BODY),
        PageBreak(),
    ]

    # ── 5. ANÉMOMÈTRE ──────────────────────────────────────────────────────
    story += [
        p("5. Montage — Anémomètre QS-FS01", H1), hr(),
        p("Le QS-FS01 est un anémomètre à <b>sortie tension analogique</b> (0.4 V–2.0 V). "
          "La tension est convertie en vitesse de vent selon la formule du fabricant. "
          "Il n'utilise <b>pas</b> de sortie impulsions — il est connecté sur le canal ADC 4 "
          "de l'InputExpander de l'Arduino Edge Control."),
        sp(4),
        p("Caractéristiques électriques", H2),
        make_table([
            ["Paramètre",           "Valeur",          "Description"],
            ["Alimentation",        "7–24 V DC",       "Ne pas alimenter en 3.3 V — tension minimale 7 V"],
            ["Sortie signal",       "0.4 V à 2.0 V",   "Analogique — 0.4 V = vent nul, 2.0 V = 32.4 m/s"],
            ["Plage de mesure",     "0–32.4 m/s",      "Soit 0–116.6 km/h"],
            ["Formule de conversion","(V − 0.4) / 1.6 × 32.4","Résultat en m/s · multiplier par 3.6 pour km/h"],
            ["Canal ADC",           "Input 0-5V CH05", "INPUT_05V_CH05 (=4) — CH01–04 réservés SoilWatch"],
            ["Lectures moyennées",  "8",               "WIND_ADC_SAMPLES — réduction du bruit"],
            ["Période de lecture",  "5 s",             "lastWindReadMs — géré dans loop()"],
        ], [4.5*cm, 3.5*cm, 8.5*cm]),
        sp(6),
        p("Câblage", H2),
        make_table([
            ["Fil QS-FS01",   "Couleur typique",  "Connexion Arduino Edge Control"],
            ["Alimentation",  "Rouge / Marron",   "Bornier 12V ou 24V DC (7 V min)"],
            ["Masse",         "Bleu / Noir",       "GND commun Arduino"],
            ["Signal",        "Jaune / Bleu clair","InputExpander ADC canal 4"],
        ], [4*cm, 4*cm, 8.5*cm]),
        sp(4),
        p("⚠️  L'alimentation doit être ≥ 7 V DC. Ne jamais alimenter le QS-FS01 depuis la "
          "pin 3.3 V de l'Arduino — la tension est insuffisante et le signal restera à 0.4 V "
          "(vent nul) en permanence.", WARN),
        sp(4),
        p("Formule complète (implémentée dans AnemometerSensor.cpp)", H2),
        p("int avgAdc = moyenne(8 × InputExpander.analogRead(4));\n"
          "float V    = avgAdc × (3.3 / 65535.0);          // ADC 16-bit → tension\n"
          "float ms   = (V - 0.4) / 1.6 × 32.4;           // formule datasheet\n"
          "float kmh  = ms × 3.6;                          // m/s → km/h", CODE),
        PageBreak(),
    ]

    # ── 6. VANNES ──────────────────────────────────────────────────────────
    story += [
        p("6. Montage — Vannes d'irrigation GARDENA 24V (réf. 900904101)", H1), hr(),
        p("Les vannes utilisées sont des <b>solénoïdes GARDENA 24V normalement fermés</b>. "
          "Contrairement aux vannes latching bistables, elles requièrent un <b>24V continu</b> "
          "pour rester ouvertes et se referment automatiquement par ressort dès que "
          "la tension est coupée."),
        sp(4),
        p("Principe de fonctionnement avec les relais Edge Control", H2),
        p("Les relais <b>latching</b> de l'Arduino Edge Control assurent la compatibilité : "
          "une impulsion SET ferme les contacts du relais, qui restent fermés sans "
          "alimentation continue. Le 24V est ainsi appliqué en permanence sur la bobine "
          "GARDENA tant que la vanne doit rester ouverte. Une impulsion RESET ouvre "
          "les contacts, coupant le 24V — le ressort referme la vanne."),
        sp(4),
        make_table([
            ["Action",          "Commande firmware",  "Relais Edge Control",      "Vanne GARDENA"],
            ["Ouvrir",          "Relay.on(index)",    "Impulsion SET → contacts fermés", "24V continu → ouverte"],
            ["Fermer",          "Relay.off(index)",   "Impulsion RESET → contacts ouverts", "Hors tension → fermée"],
            ["Durée impulsion",  "RELAY_PULSE_MS = 50 ms", "—",                  "—"],
        ], [3*cm, 4*cm, 5.5*cm, 4*cm]),
        sp(6),
        p("Connexion aux relais Edge Control", H2),
        make_table([
            ["Zone", "Relais Edge Control", "Fil solénoïde 1",  "Fil solénoïde 2", "Alimentation"],
            ["Zone 1 — Serre",    "Relay 0", "Fil A (rouge)",  "Fil B (noir)", "24V DC / ~300 mA en continu"],
            ["Zone 2 — Potager",  "Relay 1", "Fil A (rouge)",  "Fil B (noir)", "24V DC / ~300 mA en continu"],
            ["Zone 3 — Mi-ombre", "Relay 2", "Fil A (rouge)",  "Fil B (noir)", "24V DC / ~300 mA en continu"],
            ["Zone 4 — Aromates", "Relay 3", "Fil A (rouge)",  "Fil B (noir)", "24V DC / ~300 mA en continu"],
        ], [3.5*cm, 3.5*cm, 2.8*cm, 2.8*cm, 4*cm]),
        sp(4),
        p("La polarité des fils solénoïde n'est pas critique pour les solénoïdes AC/DC. "
          "Vérifier la tension d'alimentation : la vanne GARDENA 900904101 est prévue "
          "pour 24V DC ou AC.", NOTE),
        sp(6),
        p("Séquence d'initialisation", H2),
        p("Au démarrage du firmware (begin()), toutes les vannes reçoivent une impulsion "
          "de fermeture (sécurité). Même si l'état interne indique 'fermé', "
          "l'impulsion est envoyée pour garantir la position physique après une coupure de courant.", BODY),
        sp(4),
        p("Protection contre l'arrosage excessif (firmware)", H2),
        make_table([
            ["Paramètre",                    "Valeur",   "Description"],
            ["IRRIGATION_MAX_PER_HOUR",       "4",        "Max 4 déclenchements par zone par heure"],
            ["IRRIGATION_MIN_INTERVAL_MS",    "300 000 ms (5 min)", "Délai minimum entre deux arrosages"],
            ["IRRIGATION_ALERT_COOLDOWN",     "3 600 000 ms (1h)",  "Délai entre deux alertes email"],
        ], [5.5*cm, 4.5*cm, 6.5*cm]),
        PageBreak(),
    ]

    # ── 7. VÉRIN ───────────────────────────────────────────────────────────
    story += [
        p("7. Montage — Vérin linéaire (lucarne serre)", H1), hr(),
        p("Le vérin linéaire 12V est commandé par un <b>pont en H (H-bridge)</b> via deux "
          "sorties GPIO de l'Arduino (D7 et D8). Deux <b>fins de course</b> (D9 et D10) "
          "signalent les positions extrêmes et coupent le moteur automatiquement."),
        sp(4),
        make_table([
            ["Signal",            "Broche",  "Type",          "Rôle"],
            ["IN1 (direction A)",  "D7",     "OUTPUT",        "Sens extension (ouverture)"],
            ["IN2 (direction B)",  "D8",     "OUTPUT",        "Sens rétraction (fermeture)"],
            ["ENDSTOP_OPEN",       "D9",     "INPUT_PULLUP",  "Fin de course position ouverte"],
            ["ENDSTOP_CLOSE",      "D10",    "INPUT_PULLUP",  "Fin de course position fermée"],
        ], [4.5*cm, 2*cm, 3*cm, 7*cm]),
        sp(4),
        p("Logique de commande", H2),
        make_table([
            ["Action",       "IN1", "IN2", "Résultat"],
            ["Ouverture",    "HIGH","LOW", "Vérin s'étend — lucarne s'ouvre"],
            ["Fermeture",    "LOW", "HIGH","Vérin se rétracte — lucarne se ferme"],
            ["Arrêt",        "LOW", "LOW", "Moteur coupé (frein)"],
        ], [4*cm, 2*cm, 2*cm, 8.5*cm]),
        sp(4),
        p("Sécurités", H2),
        p("• <b>Timeout 60 s</b> (ACTUATOR_TIMEOUT_MS) : si la fin de course n'est pas "
          "atteinte en 60 secondes, le moteur est coupé et l'état passe en ERROR.", BODY_SMALL),
        p("• Les fins de course sont câblés en <b>Normalement Fermé (NC)</b> avec pull-up interne "
          "→ l'ouverture du contact (HIGH) signale l'atteinte de la position.", BODY_SMALL),
        p("• La méthode update() doit être appelée dans chaque itération du loop() pour "
          "surveiller les fins de course en temps réel.", BODY_SMALL),
        PageBreak(),
    ]

    # ── 8. ENCLOSURE KIT ───────────────────────────────────────────────────
    story += [
        p("8. Enclosure Kit — LCD 2×16 + Bouton", H1), hr(),
        p("L'<b>Arduino Edge Control Enclosure Kit</b> ajoute un boîtier IP40 din-rail "
          "avec un breakout board intégrant un <b>afficheur LCD NDS1602A 2×16</b> "
          "et un <b>bouton poussoir</b>. L'afficheur est piloté via le TCA6424A "
          "(I/O Expander déjà présent sur l'Edge Control) — aucun câblage supplémentaire."),
        sp(4),

        p("LCD NDS1602A — Caractéristiques", H2),
        make_table([
            ["Paramètre",       "Valeur",              "Description"],
            ["Modèle",          "NDS1602A",            "LCD alphanumérique 2 lignes × 16 caractères"],
            ["Interface",       "TCA6424A (I/O Expander)", "Connecté sur Port 2 — EXP_LCD_D4..D7, RS, EN, RW"],
            ["Rétroéclairage",  "EXP_LCD_BACKLIGHT",   "Contrôlé via TCA6424A_P20"],
            ["Objet Arduino",   "LCD (global)",        "Fourni par <Arduino_EdgeControl.h>"],
            ["Initialisation",  "LCD.begin(16, 2)",    "16 colonnes, 2 lignes"],
        ], [3.5*cm, 5*cm, 8*cm]),
        sp(6),

        p("5 Écrans en rotation automatique (5 s / écran)", H2),
        make_table([
            ["Écran",  "Ligne 1",                        "Ligne 2"],
            ["1 — Zones 1+2", "Z1: XX%   Z2: XX%",      "V1: ON/OFF  V2: ON/OFF"],
            ["2 — Zones 3+4", "Z3: XX%   Z4: XX%",      "V3: ON/OFF  V4: ON/OFF"],
            ["3 — Climat",    "Ext XX.X° Ser XX.X°",    "Vent: XX.X km/h"],
            ["4 — Vannes",    "Vannes:",                 "V1 V2 V3 V4 (-- = fermé)"],
            ["5 — Système",   "WiFi: OK/OFF  RPi: OK/OFF","Uptime: XXXXh XXm"],
        ], [3*cm, 6*cm, 7.5*cm]),
        sp(4),
        p("Le rétroéclairage s'éteint automatiquement après 30 s sans activité "
          "(LCD_BACKLIGHT_MS). Tout appui bouton le rallume.", NOTE),
        sp(4),
        p("Alertes prioritaires", H2),
        make_table([
            ["Événement",                      "Ligne 1",           "Ligne 2",        "Durée"],
            ["RPi injoignable (watchdog)",     "! RPi injoignable", "Vannes fermees", "5 s"],
            ["RPi reconnecté",                 "RPi reconnecte",    "Mode normal",    "3 s"],
            ["Arrêt d'urgence (bouton long)",  "! ARRET URGENCE",  "Vannes fermees", "4 s"],
        ], [5*cm, 4*cm, 3.5*cm, 2*cm]),
        sp(6),

        p("Bouton poussoir — Actions", H2),
        make_table([
            ["Type d'appui",   "Durée",     "Action"],
            ["Court",          "< 2 s",     "Avance à l'écran suivant + rallume le rétroéclairage"],
            ["Long",           "≥ 2 s",     "Arrêt d'urgence : ferme toutes les vannes immédiatement"],
        ], [4*cm, 3*cm, 9.5*cm]),
        sp(4),
        make_table([
            ["Paramètre",          "Valeur",       "Description"],
            ["POWER_ON",           "(lib)",        "Constante définie par Arduino_EdgeControl — pin bouton Enclosure Kit"],
            ["BUTTON_DEBOUNCE_MS", "50 ms",        "Anti-rebond logiciel"],
            ["BUTTON_LONG_PRESS_MS","2 000 ms",    "Durée détection appui long"],
        ], [5*cm, 3*cm, 8.5*cm]),
        sp(4),
        p("Le pin bouton est la constante POWER_ON définie par la librairie Arduino_EdgeControl "
          "(user manual §PowerOnButton). Aucune configuration manuelle requise.", NOTE),
        PageBreak(),
    ]

    # ── 9. ALIMENTATION ────────────────────────────────────────────────────
    story += [
        p("9. Alimentation", H1), hr(),
        make_table([
            ["Composant",            "Tension", "Courant max", "Notes"],
            ["Vannes GARDENA 900904101","24V DC/AC","~300 mA × 4 = 1.2A (simultané)", "Solénoïde NC — 24V continu requis quand ouverte"],
            ["Vérin linéaire",       "12V DC",  "2A",          "Alimentation dédiée"],
            ["Arduino Edge Control", "7–30V",   "500 mA",      "Peut être alimenté depuis le 24V"],
            ["Raspberry Pi 5",       "5V DC",   "5A",          "USB-C, alimentation officielle RPi"],
            ["Capteurs SoilWatch 10","3.3V",    "50 mA total", "Fourni par Arduino via pin 3.3V"],
            ["DS18B20",              "3.3V",    "1.5 mA chacun","Fourni par Arduino via pin 3.3V"],
            ["Anémomètre QS-FS01",   "7–24V DC","< 20 mA",    "Alimentation dédiée ≥ 7 V requise"],
        ], [4.5*cm, 2*cm, 4*cm, 6*cm]),
        sp(8),
        p("⚠️  Ne jamais connecter la masse 24V directement à la masse 3.3V de l'Arduino "
          "sans isolateur optique. Les relais de l'Edge Control assurent déjà l'isolation galvanique.", WARN),
        PageBreak(),
    ]

    # ── 10. FIRMWARE ───────────────────────────────────────────────────────
    story += [
        p("10. Firmware Arduino — Configuration", H1), hr(),
        p("Tous les paramètres modifiables sont centralisés dans "
          "<b>arduino_edge_control/src/config.h</b>. "
          "Modifier ce fichier puis recompiler avec PlatformIO avant de flasher."),
        sp(4),
        p("Paramètres à configurer avant déploiement", H2),
        make_table([
            ["Constante",              "Valeur défaut",      "À modifier"],
            ["WIFI_SSID",              "\"MonReseau\"",      "SSID de votre réseau WiFi"],
            ["WIFI_PASSWORD",          "\"MotDePasse\"",     "Mot de passe WiFi"],
            ["RPI_HOST",               "\"192.168.1.10\"",   "Adresse IP fixe du Raspberry Pi"],
            ["RPI_PORT",               "5001",               "Port Flask (défaut 5001)"],
            ["ADC_DRY",                "3100",               "Valeur ADC capteur sol à sec (calibrer)"],
            ["ADC_WET",                "1200",               "Valeur ADC capteur sol saturé (calibrer)"],
            ["ANEMOMETER_ADC_CH",      "4",                  "Canal Input 0-5V (INPUT_05V_CH05) — CH01–04 = SoilWatch"],
            ["WIND_V_ZERO",            "0.4f",               "Tension sortie à vent nul (V) — datasheet QS-FS01"],
            ["WIND_V_FULL",            "2.0f",               "Tension sortie à vitesse max (V) — datasheet QS-FS01"],
            ["WIND_MS_MAX",            "32.4f",              "Vitesse max correspondante (m/s) — datasheet QS-FS01"],
            ["WIND_ADC_SAMPLES",       "8",                  "Nombre de lectures ADC moyennées par mesure"],
        ], [5*cm, 3.5*cm, 8*cm]),
        sp(6),
        p("Compilation et flash (PlatformIO)", H2),
        p("cd arduino_edge_control\npio run --target upload --environment edge_control", CODE),
        sp(4),
        p("Surveillance série", H2),
        p("pio device monitor --baud 115200", CODE),
        p("Les logs apparaissent au format : [NIVEAU] [MODULE] message. "
          "Exemple : [INFO] [SOIL] Zone 1 ADC=2507 → 61.2%", NOTE),
        PageBreak(),
    ]

    # ── 11. API REST ───────────────────────────────────────────────────────
    story += [
        p("11. API REST Arduino ↔ Raspberry Pi", H1), hr(),
        p("La communication est initiée <b>exclusivement par le Raspberry Pi</b>. "
          "L'Arduino expose un serveur HTTP léger sur le port <b>80</b>. "
          "Toutes les réponses sont en <b>JSON</b>, encodage UTF-8. "
          "Base URL : <b>http://&lt;IP_ARDUINO&gt;/api</b>"),
        sp(8),
    ]

    # 10.1 GET /api/sensors
    story += [
        p("11.1   GET /api/sensors", H2),
        p("Retourne les lectures de tous les capteurs en une seule requête. "
          "Appelé par le Raspberry Pi à chaque cycle d'automatisation (toutes les 60 s). "
          "C'est l'endpoint le plus utilisé — il concentre humidité sol, températures et vent."),
        sp(4),
        p("Réponse JSON :", H3),
        p("""{
  "temperature_c":   26.0,
  "temp_serre_c":    38.9,
  "wind_speed_kmh":  16.0,
  "zones": [
    { "zone_id": 1, "soil_moisture_pct": 61.2, "raw_adc": 2507, "valid": true },
    { "zone_id": 2, "soil_moisture_pct": 67.6, "raw_adc": 2769, "valid": true },
    { "zone_id": 3, "soil_moisture_pct": 53.7, "raw_adc": 2197, "valid": true },
    { "zone_id": 4, "soil_moisture_pct": 39.4, "raw_adc": 1615, "valid": true }
  ]
}""", CODE),
        make_table([
            ["Champ",                  "Type",    "Description"],
            ["temperature_c",          "float",   "Température extérieure DS18B20 #0, en °C"],
            ["temp_serre_c",           "float",   "Température intérieure serre DS18B20 #1, en °C"],
            ["wind_speed_kmh",         "float",   "Vitesse du vent calculée sur 3s, en km/h"],
            ["zones[].zone_id",        "int",     "Identifiant de zone (1–4)"],
            ["zones[].soil_moisture_pct","float", "Humidité volumétrique 0–100% après calibration"],
            ["zones[].raw_adc",        "int",     "Valeur brute ADC 0–4095 (utile pour calibration)"],
            ["zones[].valid",          "bool",    "False si le capteur est hors-ligne ou déconnecté"],
        ], [4*cm, 2*cm, 10.5*cm]),
        sp(8),
    ]

    # 10.2 GET /api/actuators/status
    story += [
        p("11.2   GET /api/actuators/status", H2),
        p("Retourne l'état actuel de tous les actionneurs : vannes d'irrigation et lucarne de serre. "
          "Le Raspberry Pi appelle cet endpoint après chaque commande pour confirmer l'exécution."),
        sp(4),
        p("Réponse JSON :", H3),
        p("""{
  "roof_state": "open",
  "valves": [
    { "zone_id": 1, "state": "close" },
    { "zone_id": 2, "state": "open"  },
    { "zone_id": 3, "state": "close" },
    { "zone_id": 4, "state": "close" }
  ]
}""", CODE),
        make_table([
            ["Champ",          "Valeurs possibles",                    "Description"],
            ["roof_state",     "open · close · moving_open · moving_close · error",
                               "État du vérin lucarne. 'moving_*' = en cours de déplacement"],
            ["valves[].state", "open · close",                        "État de la vanne pour cette zone"],
        ], [3.5*cm, 6.5*cm, 6.5*cm]),
        sp(8),
    ]

    # 10.3 POST /api/actuators/valve/<zone_id>
    story += [
        p("11.3   POST /api/actuators/valve/&lt;zone_id&gt;", H2),
        p("Commande l'ouverture ou la fermeture d'une vanne d'irrigation. "
          "Le paramètre <b>zone_id</b> est passé dans l'URL (1–4). "
          "L'Arduino envoie une impulsion de 50 ms sur le relais correspondant."),
        sp(4),
        p("Corps de la requête :", H3),
        p('{ "state": "open" }   // ou "close"', CODE),
        make_table([
            ["Champ",  "Valeurs",          "Obligatoire", "Description"],
            ["state",  "\"open\" · \"close\"", "Oui",    "État désiré pour la vanne"],
        ], [2.5*cm, 3.5*cm, 2.5*cm, 8*cm]),
        sp(4),
        p("Réponse succès :", H3),
        p('{ "ok": true }', CODE),
        p("Réponse erreur (400) :", H3),
        p('{ "ok": false, "error": "state doit etre \'open\' ou \'close\'" }', CODE),
        sp(8),
    ]

    # 10.4 POST /api/actuators/roof
    story += [
        p("11.4   POST /api/actuators/roof", H2),
        p("Commande l'ouverture ou la fermeture de la lucarne de serre via le vérin linéaire. "
          "Le moteur s'arrête automatiquement à la détection du fin de course (max 60 s). "
          "Si la fin de course n'est pas atteinte, l'état passe à 'error'."),
        sp(4),
        p("Corps de la requête :", H3),
        p('{ "state": "open" }   // ou "close"', CODE),
        p("Réponse :", H3),
        p('{ "ok": true }', CODE),
        p("L'état réel du vérin est accessible via GET /api/actuators/status (roof_state). "
          "La valeur 'moving_open' ou 'moving_close' indique que le déplacement est en cours.", NOTE),
        sp(8),
    ]

    # 10.5 GET /api/health
    story += [
        p("11.5   GET /api/health", H2),
        p("Endpoint de supervision. Le Raspberry Pi l'appelle périodiquement pour vérifier "
          "que l'Arduino est joignable et fonctionnel. En mode simulation, "
          "cet endpoint est également exposé par l'émulateur sur le port 8081."),
        sp(4),
        p("Réponse JSON :", H3),
        p("""{
  "status":           "ok",
  "firmware_version": "1.0.0",
  "uptime_s":         2847,
  "wifi_rssi":        -65
}""", CODE),
        make_table([
            ["Champ",            "Type",   "Description"],
            ["status",           "string", "'ok' si le firmware fonctionne normalement"],
            ["firmware_version", "string", "Version du firmware (config.h FIRMWARE_VERSION)"],
            ["uptime_s",         "int",    "Durée de fonctionnement depuis le dernier reset, en secondes"],
            ["wifi_rssi",        "int",    "Force du signal WiFi en dBm (idéal > −70 dBm)"],
        ], [4*cm, 2*cm, 10.5*cm]),
        sp(8),
        p("Récapitulatif des endpoints", H2),
        make_table([
            ["Endpoint",                         "Méthode", "Fréquence appel",    "Rôle"],
            ["/api/sensors",                     "GET",     "60 s (automatisme)", "Lecture tous capteurs"],
            ["/api/actuators/status",            "GET",     "À la demande",       "État vannes + lucarne"],
            ["/api/actuators/valve/&lt;id&gt;",  "POST",    "À la demande",       "Commande vanne"],
            ["/api/actuators/roof",              "POST",    "À la demande",       "Commande lucarne"],
            ["/api/health",                      "GET",     "5 min (supervision)","État Arduino + WiFi"],
        ], [5.5*cm, 2*cm, 4*cm, 5*cm]),
        PageBreak(),
    ]

    # ── 12. BASCULE PROD ───────────────────────────────────────────────────
    story += [
        p("12. Bascule Simulation → Production", H1), hr(),
        p("Le système bascule intégralement en production en modifiant uniquement le fichier "
          "<b>garden_manager/.env</b> et en redémarrant Flask. "
          "Aucune modification de code n'est nécessaire."),
        sp(4),
        p("Modifications dans .env", H2),
        p("SIMULATION_MODE=false\nARDUINO_API_URL=http://192.168.1.XXX:80/api\nFLASK_DEBUG=false", CODE),
        sp(4),
        p("En mode production :", BODY),
        p("• L'émulateur Arduino (port 8081) ne démarre <b>pas</b>.", BODY_SMALL),
        p("• ArduinoClient appelle directement l'IP physique de l'Arduino.", BODY_SMALL),
        p("• Les profils météo simulés sont désactivés dans les Paramètres.", BODY_SMALL),
        p("• L'accélérateur de simulation (SIMULATION_SPEED) n'a aucun effet sur les intervalles.", BODY_SMALL),
        sp(4),
        p("Redémarrage sur Raspberry Pi", H2),
        p("git pull origin main\nsudo systemctl restart monjardin.service", CODE),
        PageBreak(),
    ]

    # ── 12. CHECKLIST ──────────────────────────────────────────────────────
    story += [
        p("12. Checklist de mise en service", H1), hr(),
        p("Firmware Arduino", H2),
        make_table([
            ["✓", "Étape",                                                      "Référence"],
            ["☐", "Mettre à jour WIFI_SSID et WIFI_PASSWORD dans config.h",     "config.h:4-5"],
            ["☐", "Mettre à jour RPI_HOST avec l'IP fixe du Raspberry Pi",      "config.h:9"],
            ["☐", "Calibrer ADC_DRY et ADC_WET pour vos capteurs SoilWatch",    "config.h:26-27"],
            ["☐", "Vérifier câblage QS-FS01 : alimentation ≥ 7V, signal sur ADC 4", "config.h, AnemometerSensor.cpp"],
            ["☐", "Vérifier alimentation 24V vannes GARDENA (solénoïde NC)",     "ValveController.cpp"],
            ["☐", "Vérifier bouton LCD : constante POWER_ON (lib Arduino_EdgeControl)", "ButtonController.cpp"],
            ["☐", "Vérifier affichage LCD au boot (écran 'MonJardin v1')",       "DisplayController.cpp"],
            ["☐", "Compiler et flasher via PlatformIO",                         "platformio.ini"],
            ["☐", "Vérifier logs série : 4 zones ADC, 2 DS18B20 détectés",      "Serial 115200"],
            ["☐", "Tester GET http://<IP_ARDUINO>/api/health depuis le Pi",      "RestServer"],
        ], [0.8*cm, 11.5*cm, 4.2*cm]),
        sp(6),
        p("Raspberry Pi / Flask", H2),
        make_table([
            ["✓", "Étape",                                                      "Référence"],
            ["☐", "Mettre une IP fixe au Raspberry Pi sur le réseau local",     "dhcpcd.conf"],
            ["☐", "Modifier .env : SIMULATION_MODE=false",                      ".env"],
            ["☐", "Modifier .env : ARDUINO_API_URL=http://<IP>:80/api",         ".env"],
            ["☐", "Modifier .env : FLASK_DEBUG=false",                          ".env"],
            ["☐", "Tester GET /api/health depuis l'interface web",              "Page Arduino"],
            ["☐", "Vérifier lecture humidité toutes les 60 s en DB",            "Page Journal"],
            ["☐", "Tester arrosage manuel Zone 1 → vérifier ouverture physique","Dashboard"],
            ["☐", "Tester fermeture vanne → vérifier fermeture physique",       "Dashboard"],
            ["☐", "Tester ouverture/fermeture lucarne serre",                   "Dashboard"],
            ["☐", "Vérifier alertes email si humidité < seuil",                 "Paramètres"],
        ], [0.8*cm, 11.5*cm, 4.2*cm]),
        sp(8),
        hr(),
        p(f"MonJardin v1.0 · Documentation générée le {datetime.date.today().strftime('%d %B %Y')} · Patrick Pinard · Vullierens, Vaud",
          CAPTION),
    ]

    doc.build(story)
    print(f"PDF généré : {OUT_PATH}")

if __name__ == "__main__":
    build()
