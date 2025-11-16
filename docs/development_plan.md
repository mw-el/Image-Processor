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
- [x] UI-Buttons für Kontrast ±, Sättigung ±, Farbtemperatur ± (U-Slider) und Auto-Farbbalance.
- [x] ProcessingPipeline um entsprechende Parameter erweitern (inkl. Kombination mit Crop-Resultaten).
- [x] Live-Vorschau bzw. schneller Re-Render im UI nach Parameteränderungen.

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
