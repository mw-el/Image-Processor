# AA Image Processor

Professionelle Desktop-Anwendung für Bildzuschnitt mit präzisen Aspect Ratios, intelligente Bildoptimierung und Export mehrerer WebP-Varianten. Mit Echtzeit-Vorschau, 100%-Lupen-Funktion, drei automatischen Optimierungsmodi und detaillierter manueller Kontrolle.

## Installation

**Quick Start:** See [INSTALL.md](INSTALL.md) for detailed installation instructions.

### Automatic Installation (Recommended)
```bash
bash install.sh
```

### Manual Setup (Linux/X11)

```bash
# Conda-Environment erstellen
conda create -n aa-image-processor python=3.11
conda activate aa-image-processor

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Toolchain & Abhängigkeiten

- **Programmiersprache**: Python 3.11+
- **GUI**: PySide6 (Qt) mit Titica-Bootstrap-Theme
- **Bildverarbeitung**: Pillow (LANCZOS resampling), NumPy, OpenCV
- **Paketverwaltung**: Conda (empfohlen)

## Projektstruktur
```
AA_Image_Processor/
├── assets/
│   ├── fonts/
│   └── icons/
├── docs/
│   ├── development_plan.md
│   ├── manual_test_plan.md
│   └── user_guide.md
├── config/
│   └── settings.json
├── models/                  # Optional: AI-Modelle für zukünftige Features
├── requirements.txt
├── src/
│   ├── app.py
│   ├── core/
│   │   ├── adjustments.py
│   │   ├── adjustment_controller.py
│   │   ├── crop_service.py
│   │   ├── image_processing.py
│   │   ├── image_session.py
│   │   ├── export_service.py
│   │   ├── thumbnail_cache.py
│   │   └── image_metadata.py
│   └── ui/
│       ├── main_window.py
│       ├── components/
│       │   ├── file_browser_sidebar.py
│       │   ├── file_tree.py
│       │   └── thumbnail_grid.py
│       ├── controllers/
│       ├── dialogs/
│       ├── views/
│       └── themes/
├── tests/
└── README.md
```

## Titica Bootstrap & Font Rendering
- Basistheme liegt unter `src/ui/themes/titica_bootstrap.qss` (Qt Stylesheet), angelehnt an Bootstrap-Farb- und Komponentenlogik.
- Für klares Schriftbild unter X11 liegt in `assets/fonts/fontconfig-local.conf` eine Fontconfig-Vorlage (LCD-Filter + Hinting). Über `FONTCONFIG_FILE=assets/fonts/fontconfig-local.conf` kann die App beim Start sicherstellen, dass die Einstellungen aktiv sind.

## Qualitäts- und Export-Defaults
- Alle Parameter liegen in `config/settings.json` (wird beim Start geladen, fallback auf Defaults).
- **Scaling & Schärfung**: `processing.variant_widths`, `sharpen_*`, `resample_method` (LANCZOS).
- **WebP-Export**: Präfixe, Zielbreiten, Qualität/Effort (`quality: 95`, `method: 6`). Dateien landen neben der Quellbild-Datei.
- **Upscaling**: PIL LANCZOS-Resampling für schnelle, hochwertige Skalierung ohne GPU-Abhängigkeit.
- **Adjustment-Limits**: Brightness/Contrast/Saturation 0.2-3.0×, RGB-Balance ±100, Temperature ±100.

## Tests
```bash
python -m unittest discover -s tests
```
Tests decken Resize-/Variantenerzeugung, WebP-Benennungsschema, Adjustment-Controller, Image-Session und Outpainting-Vorbereitung ab.

## Hauptfunktionen

### Integrierter File Browser
- **Verzeichnis-Navigation**: Vollständiger Verzeichnisbaum ab HOME-Verzeichnis
- **Thumbnail-Ansicht**: Grid-Darstellung aller Bilder im gewählten Ordner
- **Hover-Metadaten**: Tooltip mit Dateiinfo (Typ, Größe, Auflösung, Änderungsdatum)
- **Direktes Öffnen**: Klick auf Thumbnail lädt Bild in Editor
- **Rechtsklick-Menü**: "Im Dateimanager anzeigen" öffnet System-Dateimanager
- **Thumbnail-Cache**: Automatisches Caching nach freedesktop.org-Standard (~/.cache/thumbnails/normal/)
- **Netzwerk-Support**: Funktioniert mit lokalen und Netzwerk-Ordnern (SMB/NFS)
- **Toggle-Button**: Ein-/Ausblenden der Browser-Sidebar über Toolbar
- **Volle Höhe**: Browser-Spalte nutzt gesamte Fensterhöhe neben Hauptbereich

### Präziser Bildzuschnitt
- **Vordefinierte Ratios**: 1:1, 2:3, 3:4, 9:16, 3:2, 4:3, 16:9
- **Custom Ratio**: Freie Eingabe von Breite × Höhe
- **Interaktiver Rahmen**: Drag & Drop, Resize mit Aspect-Lock
- **Crop-Overlay**: Visuelles Feedback mit Handles

### 100% Lupen-Funktion
- **Haupt-Canvas**: Automatische Lupe beim Hovern über das Bild (400×400px in 1:1 Originalgröße)
- **Intelligentes Verhalten**: Lupe verschwindet automatisch nahe Crop-Handles für ungestörtes Bearbeiten
- **Results Viewer**: Vergleich von Original und Exporten mit identischer Lupen-Funktion
- **Flüssige Performance**: Optimiert für große Bilder

### Drei Auto-Optimierungsmodi
Zyklischer Button "Auto (1/3)" → "Auto (2/3)" → "Auto (3/3)" für schnellen Vergleich:

1. **Auto 1 (Photoshop-Stil)**: Histogram-basiertes Clipping
   - Brightness: ±25-35%, Contrast: bis +50%
   - RGB-Balance: ±40 für neutrale Tonwerte

2. **Auto 2 (Konservativ)**: Sanfte Verbesserung
   - Brightness: ±20-25%, Contrast: bis +30%
   - Greift bei komprimiertem Histogramm (<82% Range)

3. **Auto 3 (Nur Farbe)**: Reine Farbkorrektur
   - Keine Helligkeit/Kontrast-Änderung
   - RGB-Balance: ±45 basierend auf Median-Analyse

### Manuelle Bildanpassungen
- **Helligkeit, Kontrast, Sättigung, Schärfe**: Slider mit Live-Vorschau (0.2 - 3.0×)
- **Farbtemperatur**: -100 (kalt/blau) bis +100 (warm/orange)
- **RGB-Balance**: Separate Kontrolle für Rot, Grün, Blau (-100 bis +100)
- **Zoom**: 10% - 200% mit Slider-Steuerung
- **Reset-Button**: Alle Einstellungen auf Standard zurücksetzen

### Export & History
- **Undo/Redo**: Vollständiger History-Stack (`Ctrl+Z` / `Ctrl+Shift+Z`)
- **Zurück zum Original**: `Ctrl+R` verwirft alle Änderungen
- **Multi-Varianten Export** (`Ctrl+S`): Automatisch `__name.webp` (max), `_name.webp` (960px), `name.webp` (480px)
- **Speichern unter...**: Dialog zur freien Wahl von Basename und Zielverzeichnis - alle Varianten werden mit neuem Namen/Ort generiert
- **4K/HD-Varianten**: 16:9/9:16 erhalten zusätzlich 4K/1080p/720p mit Auflösungs-Suffix
- **Results Viewer**: Button "Ergebnisse" zeigt alle Exporte im Grid mit Lupen-Funktion

### Metadaten & Details
- **Dateiinfo**: Name, Auflösung, Statistiken
- **Metadaten-Editor**: Key=Value Format, wird in WebP eingebettet
- **Statuslog**: Detaillierte Protokollierung aller Aktionen
- **CLI-Support**: `python -m src.app <bilddatei>` für direktes Öffnen

## Development Workflow
- Detaillierter Entwicklungsplan: `docs/development_plan.md` (mit Checklisten + Timestamps).
- Prinzipien: Separation of Concern, Fail Fast, KISS, Qualität zuerst.
- Tests und QA-Szenarien werden pro Phase ergänzt (siehe Plan).

## Desktop-Integration

Die App kann als Standard-Bildbearbeiter/Viewer registriert werden:

**Automatische Installation:**
```bash
# Desktop-Datei installieren
cp image_processor.desktop ~/.local/share/applications/

# Startskript ausführbar machen
chmod +x start_image_processor.sh

# Als Standard-App registrieren
update-desktop-database ~/.local/share/applications
xdg-mime default image_processor.desktop image/jpeg image/png image/webp
```

**Starten:**
```bash
# Via Startskript (aktiviert Conda-Environment automatisch)
./start_image_processor.sh

# Mit spezifischer Bilddatei
./start_image_processor.sh /pfad/zum/bild.jpg

# Oder direkt
python -m src.app [bilddatei]
```

Das Icon `image_processor.png` wird automatisch verwendet.

## Tastenkürzel

| Kürzel | Funktion |
|--------|----------|
| `Ctrl+O` | Bild öffnen |
| `Ctrl+S` | Änderungen speichern / Export |
| `Ctrl+Shift+C` | Ausschnitt übernehmen |
| `Ctrl+Z` | Rückgängig |
| `Ctrl+Shift+Z` | Wiederholen |
| `Ctrl+R` | Zurück zum Original |
| `Ctrl+Q` | Beenden |

## Architektur

```
src/
├── app.py                    # Einstiegspunkt
├── core/
│   ├── adjustments.py        # Bildanpassungs-Algorithmen (Auto-Modi, RGB-Balance)
│   ├── adjustment_controller.py  # State Management für Anpassungen
│   ├── crop_service.py       # Crop-Geometrie-Berechnungen
│   ├── image_processing.py   # Processing Pipeline (Resize, Sharpen)
│   ├── image_session.py      # Session Management (Base Image, Ratios)
│   ├── export_service.py     # Multi-Varianten WebP-Export
│   ├── thumbnail_cache.py    # Thumbnail-Generierung & -Caching
│   ├── image_metadata.py     # Metadaten-Extraktion
│   └── settings.py           # Konfiguration & Defaults
└── ui/
    ├── main_window.py        # Haupt-UI Controller
    ├── components/
    │   ├── crop_overlay.py   # Crop-Rahmen + Lupen-Funktion
    │   ├── file_browser_sidebar.py  # Browser-Hauptkomponente
    │   ├── file_tree.py      # Verzeichnisbaum-Navigation
    │   └── thumbnail_grid.py # Thumbnail-Grid mit Rechtsklick-Menü
    ├── controllers/
    │   └── zoom_controller.py # Zoom-Steuerung
    ├── dialogs/
    │   ├── custom_ratio_dialog.py
    │   └── results_viewer.py # Export-Vergleichsansicht
    └── views/
        └── image_canvas.py   # Bilddarstellung & Canvas-Logik
```

## Performance-Optimierungen

- **Lazy Loading**: Lupen-Crops nur on-demand berechnet
- **Caching**: PIL-Images werden für Lupen-Funktion gecacht
- **Optimierte Skalierung**: LANCZOS Resampling für beste Qualität
- **Async Export**: WebP-Generierung optimiert für Geschwindigkeit

## Entwicklung

Siehe detaillierten Entwicklungsplan unter `docs/development_plan.md`.

**Core Principles:**
- Separation of Concerns (UI ↔ Logic ↔ Processing)
- Fail Fast (Frühe Validierung, klare Fehler)
- KISS (Einfachheit vor Komplexität)
- Qualität zuerst (Tests für kritische Pfade)
