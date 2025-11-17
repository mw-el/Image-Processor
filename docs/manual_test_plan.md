# Manueller Testplan – AA Image Processor

Dieser Plan deckt die End-to-End-Szenarien ab, die vor einem Release durchgespielt werden sollen.

## 1. Installation & Start
1. Virtuelle Umgebung erzeugen (`python3.11 -m venv .venv`, Aktivierung, `pip install -r requirements.txt`).
2. `python -m src.app` ohne Argument starten – Fenster sollte erscheinen, Statusbar meldet „Bereit“.
3. CLI-Start mit Datei: `python -m src.app example.jpg` – Bild muss sofort geladen sein.
4. Desktop-Integration: `./scripts/install_desktop.sh "$PWD/.venv/bin/python -m src.app"`, danach per Dateimanager ein Bild via Doppelklick öffnen.

## 2. Zuschneiden & Varianten
1. Bild via Drag & Drop laden.
2. Ratio-Buttons durchprobieren (1:1 ... 9:16) – Rahmen muss jeweils zentriert & korrekt skalieren.
3. „Rahmen entfernen“ klicken → Overlay verschwindet.
4. Custom-Ratio verwenden (z. B. 5:7) – Eingabe validieren, Rahmen sollte erscheinen.
5. Rahmen verschieben/skalieren, anschließend „Ausschnitt übernehmen“. Statusbar bestätigt.
6. `Ctrl+S` bzw. Button „Speichern“ – WebP-Dateien `__name.webp`, `_name.webp`, `name.webp` liegen neben der Quelle.
7. Bei 16:9 bzw. 9:16 muss der Export 4K/1080p/720p-Varianten liefern; Dateinamen enthalten Auflösung + Ratio-Suffix (z. B. `_bild_1920x1080_16x9.webp`).
8. Metadatenfeld (`key=value`) bearbeiten und erneut speichern – prüfen, ob Angaben übernommen werden (Dateien öffnen und XMP prüfen).

## 3. Bildanpassungen
1. Helligkeit-, Kontrast-, Sättigungs- und Schärfe-Slider bewegen – Vorschau aktualisiert live.
2. Temperatur-Slider bewegen; Loslassen sollte Zustand sichern (Undo/Redo testen).
3. Auto-Farbbalance anwenden und anschließend Undo (`Ctrl+Z`) + Redo (`Ctrl+Shift+Z`).
4. „Reset“-Button in der Slider-Reihe drücken – alle Slider springen auf 1.00 zurück, Vorschau zeigt Originalzustand.
5. Reset-zum-Original (`Ctrl+R`) – Nachfrage bestätigen, ursprüngliche Datei erneut laden.

## 4. Fehlerszenarien
1. Nicht unterstütztes Format laden → Fehlermeldung im Dialog + Statusbar.
2. Cropping ohne geladenes Bild auslösen → Hinweisdialog.
3. Speichern ohne Varianten (`Ctrl+S`) → Fehlermeldung.
4. CLI-Start mit nicht existierender Datei → Statusbar-Hinweis „Datei nicht gefunden“.

## 5. Performance
1. Großes Bild (z. B. >6000px) laden, Cropping + Export durchführen – App bleibt responsiv.
2. Mehrere Undo/Redo-Schritte (>10) durchlaufen, Speicherverbrauch beobachten (Linux `htop`).

## 6. Plattform-spezifisch (Linux/X11)
1. Font-Rendering kontrollieren (`FONTCONFIG_FILE=assets/fonts/fontconfig-local.conf python -m src.app`).
2. Icon im App-Launcher prüfen (Gnome/KDE) – wird korrekt angezeigt?

Nach Abschluss jedes Blocks Resultate notieren und bei Abweichungen Issues erstellen.
