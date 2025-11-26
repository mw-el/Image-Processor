#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.core.settings import load_settings


CHECKS = {
    "ESRGAN": {
        "path_type": "file",
        "modules": ["torch", "basicsr", "realesrgan", "opencv-python", "numpy"],
    },
    "SDXL": {
        "path_type": "dir",
        "modules": ["torch", "diffusers", "transformers", "accelerate", "safetensors"],
    },
}


def _import_optional(name: str) -> tuple[bool, str]:
    module_name = name
    pip_name = name
    if name == "opencv-python":
        module_name = "cv2"
    if name == "torch":
        pip_name = "torch"
    try:
        importlib.import_module(module_name)
        return True, module_name
    except ImportError:
        return False, pip_name


def _check_path(path: Path, path_type: str) -> bool:
    if path_type == "file":
        return path.is_file()
    return path.is_dir()


def _resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def run_checks() -> int:
    settings = load_settings()
    status_lines: list[str] = []
    ok = True

    esrgan = settings.models.esrgan
    sdxl = settings.models.sdxl
    entries = [
        ("ESRGAN", esrgan.path, CHECKS["ESRGAN"]),
        ("SDXL", sdxl.path, CHECKS["SDXL"]),
    ]

    for label, configured_path, meta in entries:
        resolved = _resolve_path(configured_path)
        exists = _check_path(resolved, meta["path_type"])
        status_lines.append(f"[{label}] Pfad ({resolved}): {'OK' if exists else 'FEHLT'}")
        if not exists:
            ok = False

        missing_modules: list[str] = []
        for module in meta["modules"]:
            available, pip_name = _import_optional(module)
            if not available:
                missing_modules.append(pip_name)
        if missing_modules:
            ok = False
            status_lines.append(f"[{label}] Fehlende Pakete: {', '.join(sorted(set(missing_modules)))}")
        else:
            status_lines.append(f"[{label}] Python-Module: OK")

    for line in status_lines:
        print(line)

    if not ok:
        print("\nBitte fehlende Modelle/Pakete installieren, siehe README (KI-Upscaling & Outpainting).")
        return 1
    print("\nAlle Modelle und optionalen Abhängigkeiten vorhanden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_checks())

