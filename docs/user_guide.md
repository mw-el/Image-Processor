# Benutzerhandbuch – AA Image Processor

## 1. Überblick
Desktop-App zum Zuschneiden von Bildern auf feste Aspect Ratios, optionales Upscaling mit hoher Qualität und Export mehrerer WebP-Varianten.

## 2. Setup
1. `python3.11 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Start: `python -m src.app [optional/path/zum/bild]`

## 3. Bedienoberfläche
- **Datei öffnen**: Menü „Datei → Bild öffnen …“, Drag & Drop oder CLI-Parameter.
- **Aspect Ratios**: Buttons 1:1, 2:3, … 9:16; „Eigene Ratio …“ erlaubt freie Eingabe; „Rahmen entfernen“ neutralisiert den Crop.
- **Crop-Rahmen**: per Maus verschieben/skalieren; fixiertes Verhältnis.
- **Anpassungen**: Slider für Helligkeit, Kontrast, Sättigung, Schärfe sowie Temperatur (−100 bis +100) wirken live auf die Vorschau; Auto-Farbbalance und „Reset“ (stellt alle Slider zurück) stehen daneben.
- **Metadaten**: Unterhalb der Regler werden Dateiname/Auflösung angezeigt; das Textfeld akzeptiert `key=value`-Zeilen, die beim Speichern in die Ausgabe übernommen werden.
- **History**: Undo (`Ctrl+Z`), Redo (`Ctrl+Shift+Z`), Reset zum Original (`Ctrl+R`).
- **Änderungen speichern**: `Ctrl+S` erstellt drei WebP-Dateien im selben Verzeichnis. Für 16:9/9:16 entstehen 4K/1080p/720p-Varianten, ansonsten Original/960px/480px; Dateinamen enthalten Auflösung + Ratio.

## 4. Troubleshooting
| Problem | Lösung |
| --- | --- |
| Schrift wirkt unscharf unter X11 | App mit `FONTCONFIG_FILE=assets/fonts/fontconfig-local.conf python -m src.app` starten. |
| Import schlägt fehl („Datei wird nicht unterstützt“) | Nur JPEG, PNG, WebP, BMP, TIFF sind erlaubt. Konvertiere vorab. |
| Export erzeugt keine Dateien | Sicherstellen, dass zuvor ein Ausschnitt erstellt wurde (`Ctrl+Shift+C`). Statusbar zeigt Erfolgsmeldung. |
| Desktop-Eintrag fehlt im Launcher | `./scripts/install_desktop.sh "$PWD/.venv/bin/python -m src.app"` ausführen und `update-desktop-database` laufen lassen. |
| Undo/Redo ausgegraut | Erst einen Crop durchführen; Buttons aktivieren sich sobald ein Zustand vorliegt. |

## 5. Changelog (Kurzfassung)
- **v0.1**: Grundlegende App-Shell, Crop-Rahmen, WebP-Export.
- **v0.2**: Qualitäts-Pipeline mit Lanczos + Unsharp Mask, Settings aus JSON.
- **v0.3**: Farb-/Temperatur-Controls, Auto-Farbbalance, History (Undo/Redo/Reset).
- **v0.4**: Desktop-Integration (.desktop, Icon, CLI-Parameter) + Dokumentation & Testplan.

Für detaillierte Phasen siehe `docs/development_plan.md`.
