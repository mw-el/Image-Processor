# Code Review – Development Principles Check

| Prinzip | Status | Hinweise |
| --- | --- | --- |
| Separation of Concern | ✅ | UI (Qt) getrennt von Core-Modulen (`core/`), Settings/Export/Processing kapsuliert. |
| Fail Fast | ✅ | Dialoge + Statusbar melden Fehler unmittelbar; Logging konfiguriert (`core/logger.py`). |
| KISS | ✅ | Einstellungen via JSON, klare Pipelines ohne überflüssige Abhängigkeiten. |
| Qualität zuerst | ✅ | Lanczos + Unsharp Mask, Tests für Skalierung/Export/ImageStore. |
| Bedienbarkeit | ✅ | Deutsche UI-Texte, History-Shortcuts, Desktop-Integration, CLI-Startpfad. |

## Offene Punkte
- Weitere Plattformtests (macOS/Windows) stehen noch aus.
- Langfristig kann ein Setting-Editor integriert werden.


Review durchgeführt am 2025-11-16.
