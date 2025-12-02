# Benutzerhandbuch – AA Image Processor

## 1. Überblick
Desktop-App zum Zuschneiden von Bildern auf feste Aspect Ratios, optionales Upscaling mit hoher Qualität und Export mehrerer WebP-Varianten.

## 2. Setup
```bash
# Conda-Environment erstellen
conda create -n aa-image-processor python=3.11
conda activate aa-image-processor

# Abhängigkeiten installieren
pip install -r requirements.txt

# Desktop-Integration
chmod +x start_image_processor.sh
cp image_processor.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications

# Starten
./start_image_processor.sh [optional/path/zum/bild]
```

## 3. Kommandozeilen-Aufrufe (CLI)

Die App kann programmgesteuert mit verschiedenen Modi und Bildern gestartet werden:

### Syntax
```bash
python -m src.app [BILD] [OPTIONS]
```

### Parameter
- `BILD` (optional): Pfad zu einer Bilddatei zum Laden beim Start (supports `~` expansion)
- `-v, --view {single|gallery}`: Startansicht (Standard: `single`)

### Beispiele

#### 1. Nur App öffnen (leer)
```bash
python -m src.app
```
→ App startet ohne geladenes Bild in Single-View

#### 2. Bild in Single-View öffnen
```bash
python -m src.app ~/Pictures/photo.jpg
```
→ Bild wird geladen, Single-View aktiv (Standard)

#### 3. Bild in Gallery-View öffnen
```bash
python -m src.app ~/Pictures/photo.jpg --view gallery
python -m src.app ~/Pictures/photo.jpg -v gallery  # Kurzform
```
→ Bild wird geladen → Gallery-View aktiviert sich nach ~100ms
→ Ganzer Ordner wird als Thumbnail-Grid angezeigt

#### 4. Nur Gallery-View (kein Bild)
```bash
python -m src.app --view gallery
```
→ App öffnet in leerer Gallery-View, keine Datei vorgeladen

### Praktische Anwendungsfälle

**Batch-Bearbeitung aus Terminal:**
```bash
# Mehrere Bilder schnell nacheinander in Gallery-View öffnen
for img in ~/Pictures/*.jpg; do
  python -m src.app "$img" -v gallery
done
```

**File Manager Integration (via .desktop file):**
```ini
[Desktop Entry]
Name=AA Image Processor (Gallery)
Exec=python -m src.app %F --view gallery
MimeType=image/jpeg;image/png;image/webp;
Type=Application
```

**Alias im Shell-Profil (~/.bashrc oder ~/.zshrc):**
```bash
alias img='python -m src.app'
alias img-gal='python -m src.app --view gallery'

# Verwendung:
img ~/Pictures/photo.jpg
img-gal ~/Pictures/photo.jpg
```

### Interne Funktionsweise

Die CLI-Verarbeitung erfolgt in `src/app.py`:

1. **Argumente parsen** (`_parse_args()`)
   - `image`: Bilddatei-Pfad
   - `--view`: single oder gallery

2. **Pfad validieren**
   - `expanduser()`: `~` → `/home/user/`
   - Existenz-Check: ungültige Pfade → None

3. **MainWindow initialisieren** (`MainWindow.__init__()`)
   - `initial_path`: zu ladende Datei
   - `initial_view`: Startansicht ("single" oder "gallery")

4. **Nach UI-Setup** (`_open_initial_image()`)
   - Falls `initial_path` vorhanden: `_handle_file_drop(path)` → Bild laden
   - Falls `initial_view == "gallery"`: `QTimer.singleShot(100, _set_view_mode("gallery"))` → View wechseln

---

## 3. Bedienoberfläche

### File Browser (links, ein-/ausblendbar)
- **Verzeichnis-Navigation**: Vollständiger Baum ab HOME-Verzeichnis
- **Thumbnail-Grid**: Alle Bilder im gewählten Ordner mit Miniaturansichten (256×256px)
- **Hover-Metadaten**: Tooltip zeigt Dateiinfo (Typ, Größe, Auflösung, Änderungsdatum)
- **Öffnen**: Klick auf Thumbnail lädt Bild direkt in Editor
- **Rechtsklick**: "Im Dateimanager anzeigen" öffnet System-Dateimanager
- **Toggle**: Browser ein-/ausblenden über Toolbar-Button
- **Cache**: Automatisches Thumbnail-Caching nach freedesktop.org-Standard

### Hauptbereich
- **Datei öffnen**: Menü „Datei → Bild öffnen …", Drag & Drop, CLI-Parameter oder File Browser.
- **100% Lupe**: Beim Hovern über Bild erscheint 400×400px Lupe in 1:1 Originalgröße; verschwindet automatisch nahe Crop-Handles.
- **Zoom**: Slider 10% - 200% für Canvas-Vergrößerung.
- **Aspect Ratios**: Buttons 1:1, 2:3, … 9:16; „Eigene Ratio …" erlaubt freie Eingabe; „Rahmen entfernen" neutralisiert den Crop.
- **Crop-Rahmen**: per Maus verschieben/skalieren; fixiertes Verhältnis.
- **Anpassungen**: Slider für Helligkeit, Kontrast, Sättigung, Schärfe (0.2 - 3.0×).
- **Farbtemperatur**: Slider −100 (kalt/blau) bis +100 (warm/orange).
- **RGB-Balance**: Separate Kontrolle für Rot, Grün, Blau (jeweils −100 bis +100).
- **Auto-Modi**: Zyklischer Button "Auto (1/3)" → "Auto (2/3)" → "Auto (3/3)":
  - **Auto 1 (Photoshop)**: Aggressive Histogram-Optimierung (±25-35% Brightness, +50% Contrast, ±40 RGB)
  - **Auto 2 (Konservativ)**: Sanfte Verbesserung nur bei komprimiertem Histogramm (±20-25% Brightness, +30% Contrast)
  - **Auto 3 (Nur Farbe)**: Reine Farbkorrektur ohne Helligkeit/Kontrast-Änderung (±45 RGB)
- **Reset**: Stellt alle Slider auf Standardwerte zurück.
- **Metadaten**: Unterhalb der Regler werden Dateiname/Auflösung angezeigt; das Textfeld akzeptiert `key=value`-Zeilen.
- **Statusfenster**: Zeigt Export-Fortschritt und Verarbeitungsschritte.

### History & Export
- **History**: Undo (`Ctrl+Z`), Redo (`Ctrl+Shift+Z`), Reset zum Original (`Ctrl+R`).
- **Speichern** (`Ctrl+S`): Exportiert drei WebP-Varianten ins Original-Verzeichnis (Original/960px/480px oder 4K/1080p/720p für 16:9/9:16).
- **Speichern unter...**: Dialog für freie Wahl von Basename und Zielverzeichnis; alle Varianten werden mit neuem Namen/Ort generiert.
- **Results Viewer**: Button "Ergebnisse" zeigt Grid-Vergleich von Original und allen Exporten mit identischer 100%-Lupen-Funktion.
- **Upscaling**: Verwendet schnelles LANCZOS-Resampling für hochwertige Skalierung ohne GPU-Abhängigkeit.

## 4. Troubleshooting
| Problem | Lösung |
| --- | --- |
| Schrift wirkt unscharf unter X11 | App mit `FONTCONFIG_FILE=assets/fonts/fontconfig-local.conf python -m src.app` starten. |
| Import schlägt fehl („Datei wird nicht unterstützt“) | Nur JPEG, PNG, WebP, BMP, TIFF sind erlaubt. Konvertiere vorab. |
| Export erzeugt keine Dateien | Sicherstellen, dass zuvor ein Ausschnitt erstellt wurde (`Ctrl+Shift+C`). Statusbar zeigt Erfolgsmeldung. |
| Desktop-Eintrag fehlt im Launcher | `cp image_processor.desktop ~/.local/share/applications/ && update-desktop-database ~/.local/share/applications` |
| Undo/Redo ausgegraut | Erst einen Crop durchführen; Buttons aktivieren sich sobald ein Zustand vorliegt. |

## 5. Changelog (Kurzfassung)
- **v0.1**: Grundlegende App-Shell, Crop-Rahmen, WebP-Export.
- **v0.2**: Qualitäts-Pipeline mit Lanczos + Unsharp Mask, Settings aus JSON.
- **v0.3**: Farb-/Temperatur-Controls, Auto-Farbbalance, History (Undo/Redo/Reset).
- **v0.4**: Desktop-Integration (.desktop, Icon, CLI-Parameter) + Dokumentation & Testplan.
- **v0.5**: 100% Lupen-Funktion, Zoom-Slider, Results Viewer Dialog, RGB-Balance-Slider.
- **v0.6**: Drei Auto-Optimierungsmodi mit starken Variationen, Magnifier in CropOverlay.
- **v0.7**: File Browser mit Thumbnail-Cache, Rechtsklick-Menü, "Speichern unter..."-Dialog, Full-Height-Layout.
- **v0.8** (2025-11-25):
  - Save As Dialog komplett behoben (Pfad-Validierung, korrekte Dialog-Akzeptanz)
  - Save As UI verbessert (Ordner-Icon, einheitliche Blautöne, Tooltips)
  - Auto 1/2/3 mit Zauberstab-Icons
  - Umfangreiches Debug-Logging im Status-Fenster
  - Variable Aspect Ratio (?:?) komplett behoben: Custom-Ratios skalieren jetzt korrekt auf Canvas-Größe

Für detaillierte Phasen siehe `docs/development_plan.md`.
