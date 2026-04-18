"""Constructeur de templates email HTML pour MonJardin."""
from datetime import datetime


_LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="40" height="40" style="display:block;">
  <rect width="64" height="64" rx="14" fill="#1a7f3c"/>
  <path d="M18 22 Q32 13 46 22" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.55"/>
  <path d="M22 28 Q32 21 42 28" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.75"/>
  <path d="M26 34 Q32 29 38 34" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.95"/>
  <circle cx="32" cy="37.5" r="2.8" fill="white"/>
  <path d="M32 40 L32 54" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M32 50 C32 50 23 47 22 41 C22 41 31 40 32 50Z" fill="white" opacity="0.85"/>
  <path d="M32 46 C32 46 41 43 42 37 C42 37 33 36 32 46Z" fill="white"/>
  <circle cx="26" cy="56" r="1.5" fill="white" opacity="0.45"/>
  <circle cx="32" cy="57.5" r="1.5" fill="white" opacity="0.6"/>
  <circle cx="38" cy="56" r="1.5" fill="white" opacity="0.45"/>
</svg>
"""

_LEVEL_STYLES = {
    "info":    {"color": "#0060cc", "bg": "#e8f0fc", "border": "#b3ccf5", "icon": "ℹ️", "label": "Information"},
    "success": {"color": "#1a7f3c", "bg": "#e6f4ec", "border": "#a3d9b5", "icon": "✅", "label": "Succès"},
    "warning": {"color": "#c46200", "bg": "#fef4e6", "border": "#f5d5a3", "icon": "⚠️", "label": "Avertissement"},
    "alert":   {"color": "#cc1f16", "bg": "#fde8e6", "border": "#f5b3af", "icon": "🚨", "label": "Alerte"},
}


def build_email_html(
    title: str,
    intro: str,
    rows: list[tuple[str, str]],
    level: str = "info",
    footer_note: str = "",
) -> str:
    """
    Retourne un email HTML complet.

    Args:
        title:       Titre principal affiché dans la carte.
        intro:       Texte introductif sous le titre.
        rows:        Liste de (label, valeur) pour le tableau de détails.
        level:       'info' | 'success' | 'warning' | 'alert'
        footer_note: Texte optionnel sous les détails.
    """
    s = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
    now = datetime.now().strftime("%d.%m.%Y à %H:%M:%S")

    rows_html = "".join(
        f"""<tr>
              <td style="padding:9px 14px;color:#6b7280;font-size:13px;border-bottom:1px solid #e5e7eb;
                         white-space:nowrap;font-weight:600;vertical-align:top;">{label}</td>
              <td style="padding:9px 14px;color:#111315;font-size:13px;border-bottom:1px solid #e5e7eb;
                         word-break:break-word;">{value}</td>
            </tr>"""
        for label, value in rows
    )

    footer_html = (
        f'<p style="font-size:12px;color:#9ca3af;margin:0;">{footer_note}</p>'
        if footer_note else ""
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:32px 16px;">
  <tr><td align="center">
  <table width="100%" style="max-width:560px;" cellpadding="0" cellspacing="0">

    <!-- Header -->
    <tr>
      <td style="background:#1a7f3c;border-radius:14px 14px 0 0;padding:24px 28px;">
        <table cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding-right:14px;vertical-align:middle;">{_LOGO_SVG}</td>
            <td style="vertical-align:middle;">
              <div style="font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">MonJardin</div>
              <div style="font-size:12px;color:rgba(255,255,255,.65);margin-top:1px;">Vullierens · Vaud — Jardin connecté</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Level badge + title -->
    <tr>
      <td style="background:#ffffff;padding:24px 28px 8px;">
        <div style="display:inline-block;background:{s['bg']};border:1px solid {s['border']};
                    color:{s['color']};border-radius:20px;padding:4px 12px;
                    font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px;">
          {s['icon']}&nbsp; {s['label']}
        </div>
        <h1 style="margin:0 0 8px;font-size:20px;font-weight:700;color:#111315;letter-spacing:-0.3px;">{title}</h1>
        <p style="margin:0 0 20px;font-size:14px;color:#3d4349;line-height:1.6;">{intro}</p>
      </td>
    </tr>

    <!-- Details table -->
    {f'''<tr>
      <td style="background:#ffffff;padding:0 28px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;border-collapse:collapse;">
          {rows_html}
        </table>
      </td>
    </tr>''' if rows_html else ''}

    <!-- Footer note -->
    {f'''<tr>
      <td style="background:#ffffff;padding:0 28px 20px;">
        <div style="background:#f8f9fa;border-radius:8px;padding:12px 14px;">
          {footer_html}
        </div>
      </td>
    </tr>''' if footer_note else ''}

    <!-- Footer bar -->
    <tr>
      <td style="background:#f8f9fa;border:1px solid #e5e7eb;border-top:none;
                 border-radius:0 0 14px 14px;padding:16px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:11px;color:#9ca3af;">
              Envoyé le {now} par MonJardin
            </td>
            <td align="right" style="font-size:11px;color:#9ca3af;">
              Jardin connecté · Vullierens
            </td>
          </tr>
        </table>
      </td>
    </tr>

  </table>
  </td></tr>
</table>
</body>
</html>"""
