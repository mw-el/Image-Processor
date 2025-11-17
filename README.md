# AA Image Processor

Lokale Desktop-Anwendung zum Zuschneiden von Bildern anhand vordefinierter Aspect Ratios und Export mehrerer WebP-Varianten (maximale Auflösung, 960px, 480px) inklusive Upscaling, Schärfung und Farbkorrekturen.

## Toolchain & Abhängigkeiten
- **Programmiersprache**: Python 3.11
- **GUI**: PySide6 (Qt) mit Titica-Bootstrap-Theme
- **Bildverarbeitung**: Pillow, OpenCV, NumPy/SciPy
- **Paketverwaltung**: Pip + `requirements.txt`

### Setup (Linux/X11)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Projektstruktur
```
AA_Image_Processor/
├── assets/
│   ├── fonts/
│   └── icons/
├── docs/
│   └── development_plan.md
├── requirements.txt
├── src/
│   └── ui/
│       └── themes/
└── README.md
```

## Titica Bootstrap & Font Rendering
- Basistheme liegt unter `src/ui/themes/titica_bootstrap.qss` (Qt Stylesheet), angelehnt an Bootstrap-Farb- und Komponentenlogik.
- Für klares Schriftbild unter X11 liegt in `assets/fonts/fontconfig-local.conf` eine Fontconfig-Vorlage (LCD-Filter + Hinting). Über `FONTCONFIG_FILE=assets/fonts/fontconfig-local.conf` kann die App beim Start sicherstellen, dass die Einstellungen aktiv sind.

## Qualitäts- und Export-Defaults
- Alle Parameter liegen in `config/settings.json` (wird beim Start geladen, fallback auf Defaults).
- **Scaling & Schärfung**: `processing.variant_widths`, `sharpen_*`, `resample_method` (z. B. `"LANCZOS"`).
- **WebP-Export**: Präfixe, Zielbreiten, Qualität/Effort (`quality`, `method`). Dateien landen neben der Quellbild-Datei.

## Tests
```bash
python -m unittest discover -s tests
```
Tests decken Resize-/Variantenerzeugung und das WebP-Benennungsschema des Exportservices ab.

## Bedienung
- Zuschneiden über Ratio-Buttons + Custom-Dialog; „Rahmen entfernen“ neutralisiert die Auswahl.
- Live-Anpassungen via Slider (Helligkeit, Kontrast, Sättigung, Schärfe, Temperatur) + Auto-Farbbalance wirken direkt auf die Vorschau; der Button „Reset“ setzt alle Slider zurück.
- Undo/Redo (`Ctrl+Z` / `Ctrl+Shift+Z`) sowie "Zurück zum Original" (`Ctrl+R`) greifen auf den internen History-Stack zu.
- Export/Speichern (`Ctrl+S`) legt die Varianten (`__name.webp`, `_name.webp`, `name.webp`) direkt neben der Originaldatei ab; 16:9/9:16 erhalten automatisch 4K/1080p/720p-Ausgaben mit Auflösungs- und Ratio-Suffix im Namen.
- CLI: `python -m src.app <bilddatei>` öffnet optional direkt eine Datei (z. B. als Bild-Handler).
- Rechts unter den Reglern werden Dateiname, Auflösung und Metadaten (bearbeitbar als `key=value`) angezeigt.

## Development Workflow
- Detaillierter Entwicklungsplan: `docs/development_plan.md` (mit Checklisten + Timestamps).
- Prinzipien: Separation of Concern, Fail Fast, KISS, Qualität zuerst.
- Tests und QA-Szenarien werden pro Phase ergänzt (siehe Plan).

## Desktop-Integration
- Icon (SVG) liegt unter `assets/icons/app_icon.svg`.
- `.desktop`-Vorlage: `resources/desktop/aa-image-processor.desktop` (Platzhalter `AA_IMAGE_PROCESSOR_BIN` wird vom Install-Skript ersetzt).
- Installation im User-Kontext:
  ```bash
  ./scripts/install_desktop.sh "$PWD/.venv/bin/python -m src.app"
  ```
  Danach ggf. im Dateimanager als Standard-App für Bilder festlegen.

## Nächste Schritte
Siehe Phase 0/1 im Entwicklungsplan. Nach jedem Meilenstein Checkbox abhaken und Status-Update mit Zeitstempel ergänzen.
