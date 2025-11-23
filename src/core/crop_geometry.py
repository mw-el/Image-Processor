from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


RectTuple = Tuple[float, float, float, float]


def _rect_intersection(a: RectTuple, b: RectTuple) -> RectTuple:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    return (x1, y1, width, height)


@dataclass
class CropGeometry:
    selection: RectTuple
    image_bounds: RectTuple
    scale: float

    def selection_size(self) -> tuple[int, int]:
        return (
            max(1, int(round(self.selection[2]))),
            max(1, int(round(self.selection[3]))),
        )

    def intersection(self) -> RectTuple:
        return _rect_intersection(self.selection, self.image_bounds)

    def has_whitespace(self) -> bool:
        inter = self.intersection()
        epsilon = 0.25
        return inter[2] < self.selection[2] - epsilon or inter[3] < self.selection[3] - epsilon

    def to_payload(self) -> dict[str, Any]:
        return {
            "selection": list(self.selection),
            "image_bounds": list(self.image_bounds),
            "scale": float(self.scale),
        }

    @classmethod
    def from_payload(cls, data: Optional[dict[str, Any]]) -> Optional["CropGeometry"]:
        if not data:
            return None
        selection = tuple(float(v) for v in data.get("selection", []))
        image_bounds = tuple(float(v) for v in data.get("image_bounds", []))
        if len(selection) != 4 or len(image_bounds) != 4:
            return None
        scale = float(data.get("scale", 1.0))
        return cls(selection=selection, image_bounds=image_bounds, scale=scale)

