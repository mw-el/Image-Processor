# Entwicklungsplan – AA Image Processor

## Überblick
Lokale Desktop-App zur Bildbearbeitung und Export mehrerer WebP-Varianten mit ratio-basierter Zuschneidefunktion, Upscaling/Sharpening und einfachen Farbkorrekturen. Dieser Plan dient als rote Linie, an der wir Schritt für Schritt arbeiten und nach Unterbrechungen sofort weiterführen können.

## Development Principles
1. **Separation of Concern** – GUI, State-Management und Bildverarbeitung klar trennen (z. B. UI-Controller, ImageStore, ProcessingPipeline).
2. **Fail Fast** – Eingaben/ Zustände früh validieren und Fehler sichtbar machen (Dialoge, Logs) statt stillschweigend fortzufahren.
3. **Keep It Simple, Stupid** – Minimal vertikaler Slice pro Feature, konsistente Patterns wiederverwenden, unnötige Abhängigkeiten vermeiden.
4. **Qualität zuerst** – Bei Skalierung/Schärfung hochwertige Algorithmen (z. B. Lanczos + Unsharp Mask) bevorzugen, Tests für kritische Pfade schreiben.
5. **Bedienbarkeit** – Deutsche Beschriftungen, klare Buttons für Ratios/Effekte, Undo/Redo plus Reset zum Original.

## Technologien & Architektur-Rahmen
- **UI**: Titica Bootstrap-basiertes Theme in Desktop-GUI (z. B. Qt/PySide oder GTK) mit X11-Font-Rendering-Konfiguration (Fontconfig/LCD).
- **Bildverarbeitung**: Pillow + OpenCV (o. ä.) für Crop, Resize, Sharpen, Farbkorrekturen.
- **Struktur**: MVC-ähnlich – `ImageStore` (Original, aktuelle Version, History), `ProcessingPipeline`, `ExportService`.
- **Datei-Integration**: Drag & Drop + Dateidialog, später `.desktop`-Einbindung inklusive Icon & MIME-Handler.

## Arbeitsweise & Fortschritts-Tracking
- Alle Aufgaben unten sind Checkboxen. Nach Abschluss **direkt im Plan** `[x]` setzen.
- Nach jedem Arbeitsschritt einen Eintrag unter **Status-Updates** anhängen: `- YYYY-MM-DD HH:MM (TZ) – Kurzbeschreibung`.
- Bei Unterbrechung zuerst fertige Checkboxen prüfen und ggf. markieren, dann neuen Status-Eintrag ergänzen.
- Änderungen an diesem Plan per Commit oder Dokumentation begleiten, wie gewohnt.

## Phasen & Aufgaben
### Phase 0 – Projektfundament
- [x] Repositorystand prüfen, Grundstruktur (src/, assets/, docs/) anlegen.
- [x] Toolchain definieren (z. B. Python-Version, Dependency-Manager), Basis-README um Setup erweitern.
- [x] Titica-Bootstrap-Theme & globale Styles (inkl. Fontconfig-Init) vorbereiten.

### Phase 1 – Kernarchitektur & State
- [x] Grundlegende App-Shell mit Fenster, Menüleiste, Drag & Drop + Dateidialog.
- [x] `ImageStore`: Laden/Speichern von Original, Arbeitskopie, History-Struktur.
- [x] Fehlerbehandlung + Logging (Fail-Fast-Pfade, UI-Feedback).

### Phase 2 – Ratio-Rahmen & Crop-Engine
- [x] Anzeige des Bildes inkl. Overlay-Layer für Ratio-Rahmen (Buttons: 1:1, 2:3, 3:4, 16:9, 3:2, 4:3, 9:16, Custom).
- [x] Custom-Ratio-Dialog (Eingabe von Breite/Höhe mit Validierung).
- [x] Interaktives Resizing/Positionieren des Rahmens bei fixem Verhältnis + Zentrierung bei Auswahl.
- [x] Crop-Pipeline, die ausgewählte Region extrahiert und an ProcessingPipeline übergibt.

### Phase 3 – Skalierung, Schärfung & Export
- [x] Upscaling/Downscaling mit Qualitätspriorisierung (z. B. Lanczos) + Unsharp Mask.
- [x] Export-Service für WebP: Varianten `__name.webp` (max), `_name.webp` (960px Breite), `name.webp` (480px) sowie ratio/resolution-Suffixe.
- [x] Qualität/Effort-Settings evaluieren und als Defaults dokumentieren.
- [x] Tests für Namenserzeugung, Skalierung und Qualitäts-Parameter.

### Phase 4 – Bildverbesserungen & Controls
- [x] UI-Slider für Helligkeit, Kontrast, Sättigung, Schärfe (0.2 - 3.0×).
- [x] Farbtemperatur-Slider (-100 bis +100).
- [x] RGB-Balance-Slider (Rot, Grün, Blau separat, -100 bis +100).
- [x] Drei Auto-Optimierungsmodi (Photoshop-Stil, Konservativ, Nur Farbe).
- [x] AdjustmentController für State Management mit Live-Callbacks.
- [x] ProcessingPipeline um alle Parameter erweitert (inkl. Kombination mit Crop-Resultaten).
- [x] Live-Vorschau mit schnellem Re-Render im UI nach Parameteränderungen.

### Phase 5 – Undo/Redo & Reset
- [x] History-Stack implementieren (Undo/Redo, begrenzte Größe, Speicheroptimierung).
- [x] Reset-zum-Original-Button und Confirm-Dialog, falls ungespeicherte Änderungen bestehen.
- [x] Tests/QA-Szenarien für Sequenzen von Aktionen inkl. Rückgängig/Wiederholen.

### Phase 6 – Desktop-Integration & Packaging
- [x] `.desktop`-Datei + Icon erstellen, Default-App/MIME-Registrierung dokumentieren.
- [x] CLI-Support (optional) zum Öffnen einer Datei via Kommandozeile oder Double-Click.
- [x] Installations-/Packaging-Skript (z. B. venv + launcher) und Release-Anleitung.
- [x] End-to-End-Manueller Testplan (verschiedene Bilder, Ratios, Exports, Farbtools).

### Phase 7 – Feinschliff & Review
- [x] Code-Review gegen Development Principles durchführen, Refactorings einpflegen.
- [x] Abschluss-Tests (funktional, Performance, Fehlerfälle) dokumentieren.
- [x] Finale Doku: Benutzerhandbuch, Troubleshooting (Font-Rendering, Abhängigkeiten), Changelog.

### Phase 8 – Erweiterte Features (Post-Release)
- [x] **100% Lupen-Funktion im Haupt-Canvas**: Hover-basierte 400×400px Lupe mit 1:1 Originalgröße.
- [x] **Intelligentes Lupen-Verhalten**: Automatische Deaktivierung nahe Crop-Handles (24px Radius).
- [x] **Results Viewer Dialog**: Grid-Ansicht von Original + Exporten mit identischer Lupen-Funktion.
- [x] **Zoom-Funktion**: Canvas-Zoom 10% - 200% mit Slider und Label.
- [x] **Erweiterte Auto-Balance**: Drei Modi mit Histogram-Analyse und konfigurierbaren Limits.
- [x] **RGB-Balance History**: Vollständige Integration in Undo/Redo-System.
- [x] **Magnifier im CropOverlay**: Lupen-Logik ins Overlay verlagert für bessere Event-Behandlung.
- [x] **File Browser Integration**: Vollhöhen-Sidebar mit Verzeichnisbaum und Thumbnail-Grid.
- [x] **Thumbnail-Cache-System**: Freedesktop.org-Standard-konformes Caching (~/.cache/thumbnails/normal/).
- [x] **Metadata-Tooltips**: Hover-Anzeige von Dateiinfo (Typ, Größe, Auflösung, Datum) auf Thumbnails.
- [x] **Rechtsklick-Menü**: "Im Dateimanager anzeigen" für direkten Zugriff auf Systemdateimanager.
- [x] **Speichern unter...**: Zusätzlicher Export-Dialog für freie Wahl von Basename und Zielverzeichnis.
- [x] **Full-Height Browser**: Browser-Spalte nutzt gesamte Fensterhöhe inkl. Toolbar-Bereich.
- [x] **Export-Code-Refactoring**: Gemeinsame Export-Logik in wiederverwendbarer Methode (_do_export_variants).

## Status-Updates (chronologisch)
- 2025-11-16 18:29 CET – Phase 0: Repositorystand geprüft und Projektstruktur (src/, assets/, docs/) erstellt.
- 2025-11-16 18:30 CET – Phase 0: Toolchain festgelegt und README mit Setup-/Workflow-Hinweisen erstellt.
- 2025-11-16 18:30 CET – Phase 0: Titica-Bootstrap-Stylesheet & Fontconfig-Vorlage vorbereitet.
- 2025-11-16 18:42 CET – Phase 1: App-Shell, ImageStore und Logging/Fehlerbehandlung implementiert.
- 2025-11-16 19:16 CET – Phase 2: Ratio-Buttons, Custom-Ratio-Dialog und Crop-Overlay-Platzhalter implementiert.
- 2025-11-16 19:51 CET – Phase 2: Crop-Overlay mit Drag/Resize-Interaktion und fester Aspect Ratio umgesetzt.
- 2025-11-16 20:07 CET – Phase 2: Crop-Pipeline integriert, Ausschnitt übernimmt Bilddaten in den Workflow.
- 2025-11-16 20:23 CET – Phase 3: Qualitätsorientierte Skalierung + Unsharp Mask in Pipeline integriert.
- 2025-11-16 20:30 CET – Phase 3: WebP-Exportservice mit Defaultpräfixen eingebunden.
- 2025-11-16 20:30 CET – Phase 3: Qualitäts-Defaults dokumentiert und Unit-Tests ergänzt.
- 2025-11-16 20:37 CET – Phase 4: Farb-/Kontrast-Buttons, Temperatur-Slider & Auto-Farbbalance mit Live-Vorschau umgesetzt.
- 2025-11-16 20:46 CET – Phase 5: Undo/Redo, Reset-zum-Original und Tests für Historylogik umgesetzt.
- 2025-11-16 21:29 CET – Phase 6: Desktop-Icon, .desktop-Datei, CLI-Startparameter und Install-Skript ergänzt.
- 2025-11-16 21:29 CET – Phase 6: Manueller End-to-End-Testplan erstellt.
- 2025-11-16 21:29 CET – Phase 7: Code-Review, Testberichte und Benutzerhandbuch abgeschlossen.
- 2025-11-17 15:50 CET – Refactoring: MainWindow nutzt ImageSession/AdjustmentController konsequent, neue Tests für Ratio- & Reglerlogik.
- 2025-11-18 18:00 CET – Phase 8: RGB-Balance Slider (Rot, Grün, Blau) mit History-Integration implementiert.
- 2025-11-18 18:15 CET – Phase 8: Drei Auto-Optimierungsmodi implementiert (Photoshop-Stil, Konservativ, Nur Farbe).
- 2025-11-18 18:30 CET – Phase 8: Results Viewer Dialog mit Grid-Layout und Lupen-Funktion für Export-Vergleich.
- 2025-11-18 18:45 CET – Phase 8: 100% Lupen-Funktion im Haupt-Canvas mit intelligentem Verhalten nahe Crop-Handles.
- 2025-11-18 19:00 CET – Phase 8: Variationsbreite der Auto-Modi erhöht (Brightness ±20-25%, Contrast +35%, RGB ±30-35).
- 2025-11-18 19:10 CET – Phase 8: Button-Umbenennung "Balance" → "Auto" mit Zyklus-Modi (1/3, 2/3, 3/3).
- 2025-11-18 19:20 CET – Dokumentation: README und Development Plan mit allen neuen Features aktualisiert.
- 2025-11-18 22:30 CET – Phase 8: File Browser Architektur erstellt (ThumbnailCache, ImageMetadata, FileTree, ThumbnailGrid).
- 2025-11-18 22:45 CET – Phase 8: File Browser Integration in MainWindow mit QSplitter und Toggle-Button.
- 2025-11-18 23:00 CET – Phase 8: Rechtsklick-Kontextmenü "Im Dateimanager anzeigen" für Thumbnails implementiert.
- 2025-11-18 23:15 CET – Phase 8: "Speichern unter..."-Dialog implementiert mit Export-Code-Refactoring (_do_export_variants).
- 2025-11-18 23:30 CET – Phase 8: Full-Height Browser-Layout - Sidebar nutzt gesamte Fensterhöhe, Toolbar rechts daneben.
- 2025-11-18 23:45 CET – Dokumentation: README, Development Plan mit File Browser Features aktualisiert.
- 2025-11-23 – UI-Verbesserungen: Icons immer weiß, File Browser startet ausgeblendet, Recent Files/Folders Buttons mit Dropdown-Menü (persistent, 15 Einträge).
- 2025-11-23 – Auto-Balance Button: Zauberstab-Icon (fa5s.magic) statt mdi6.auto-fix.
- 2025-11-23 – Custom Ratio Dialog: Vorausfüllung mit letzten Werten.
- 2025-11-23 16:51 CET – Custom Ratio Bug behoben: Ratio-Anwendung validiert Bild/Pixmap und setzt den Rahmen nur nach Erfolg.
- 2025-11-25 18:30 CET – Save As Dialog komplett behoben: QDialog.DialogCode.Accepted-Vergleich, Pfad-Validierung, Error-Handling.
- 2025-11-25 18:35 CET – Save As Dialog UI: Ordner-Icon, blaue Button-Farben (#2196F3), Tooltips.
- 2025-11-25 18:40 CET – Auto-Balance Icons: Zauberstab-Icons für Auto 1/2/3 Modi implementiert.
- 2025-11-25 18:45 CET – Debug-Logging: Umfangreiches Status-Log für Crop- und Save-Operationen zur Fehlerdiagnose.

## Bekannte Bugs / Offene Punkte

### Behoben: Save As Dialog speicherte nicht

**Status**: Behoben (2025-11-25)

**Problem**: Der "Speichern unter..." Dialog zeigte sich, aber das Speichern funktionierte nicht. Dateien wurden nicht am gewählten Ort gespeichert.

**Root Cause**: Dialog-Akzeptanz-Check verwendete `dialog.Accepted` statt `QDialog.DialogCode.Accepted`. Die Instanzattribut-Fallback-Methode war nicht zuverlässig.

**Lösung**:
- Dialog-Vergleich korrigiert zu `QDialog.DialogCode.Accepted` (main_window.py:1418)
- QDialog-Import hinzugefügt
- Vollständige Pfad-Validierung mit Try/Except in save_as_dialog.py
- Umfangreiches Debug-Logging im Status-Fenster für Save-Operationen

### Behoben: Save As Dialog UI-Verbesserungen

**Status**: Behoben (2025-11-25)

**Verbesserungen**:
- Ordner-Icon (mdi6.folder-open) zum Browse-Button hinzugefügt
- Button-Farben auf Hauptfenster-Blau (#2196F3) angepasst
- Tooltip "Ordner wählen" hinzugefügt

### Behoben: Auto-Balance Icons

**Status**: Behoben (2025-11-25)

**Verbesserung**: Auto 1, Auto 2, Auto 3 Modi zeigen jetzt Zauberstab-Icons (fa5s.magic) mit weißer Farbe.

### BEKANNTES PROBLEM: Variable Aspect Ratio (?:?) zeigt inkonsistent Crop-Rahmen

**Status**: Teilweise behoben, bleibt offen (2025-11-25)

**Problem**: Bei Eingabe eigener Aspect Ratios im "?:?"-Dialog erscheint der Crop-Rahmen manchmal nicht oder inkonsistent.

**Bisherige Fixes**:
- `_enter_crop_mode()` zeigt jetzt Basisbild korrekt an (main_window.py:797)
- `crop_overlay.set_selection()` ruft explizit `self.show()` auf (crop_overlay.py:52)
- Umfangreiches Debug-Logging im Status-Fenster

**Verbleibendes Issue**: Trotz Fixes erscheint der Rahmen nicht konsistent. Weitere Untersuchung nötig, aber **niedrige Priorität**, da:
- Save As Dialog (wichtiger) jetzt funktioniert
- Voreingestellte Ratios (1:1, 2:3, 3:4, 16:9, etc.) funktionieren einwandfrei
- Workaround: Nutzer können voreingestellte Ratios verwenden

**Debug-Hinweise**: Status-Log zeigt detaillierte Meldungen für Custom Ratio Dialog, _apply_ratio, Canvas-Bereiche und Overlay-Aktivierung.
