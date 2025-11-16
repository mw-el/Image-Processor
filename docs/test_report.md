# Testreport – AA Image Processor

## Automatisierte Tests
- Befehl: `python -m unittest discover -s tests -v`
- Deckung:
  - `test_processing_pipeline`: prüft Zielbreiten & Aspect Ratio beim Resizing.
  - `test_export_service`: verifiziert WebP-Namensschema + Dateierzeugung.
  - `test_image_store`: sichert Undo/Redo/Reset-Verhalten.
- Ergebnis (2025-11-16): 5 Tests, alle erfolgreich.

## Manuelle Tests
Siehe `docs/manual_test_plan.md`. Run-Log (2025-11-16):
- Installation/Start ✔️
- CLI-Start mit Datei ✔️
- Crop/Aspect Ratio & Export ✔️
- Anpassungen + Undo/Redo + Reset ✔️
- Fehlerszenarien (Format, Export ohne Varianten, fehlender Pfad) ✔️
- Fontconfig/Launcher-Test (Gnome) ✔️

## Offene Punkte
- Noch keine formale Performance-Metrik; subjektiv responsive für 8k-Testbild.
- Zusätzliche Plattformtests (Windows/macOS) stehen noch aus.
