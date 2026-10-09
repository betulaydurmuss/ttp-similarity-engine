"""Regenerate every brand asset from the two source PNGs.

    pip install pillow potracer
    python tools/brand/build_brand.py

Reads  docs/brand/source/yildiz-emblem.png   (white emblem on black)
       docs/brand/source/yildiz-wordmark.png (white lockup on transparent)
Writes web/src/lib/brand.js, web/public/favicon.svg, web/public/favicon.png,
       docs/brand/yildiz-lockup-{dark,light}.svg
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import potrace
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "brand" / "source"
INK_DARK = "#e9eef5"
INK_LIGHT = "#0b0f17"
STAR = "#ffb54a"
VOID = "#04060a"


def trace(mask):
    return potrace.Bitmap(mask).trace(
        turdsize=8,
        turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
        alphamax=1.0,
        opticurve=True,
        opttolerance=0.2,
    )


def bounds(curve):
    points = [curve.start_point]
    for segment in curve:
        points.append(segment.end_point)
        points.extend([segment.c] if segment.is_corner else [segment.c1, segment.c2])
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def to_path(curves, scale, dx=0.0, dy=0.0):
    def number(value):
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def point(p):
        return f"{number((p.x - dx) * scale)} {number((p.y - dy) * scale)}"

    parts = []
    for curve in curves:
        parts.append(f"M{point(curve.start_point)}")
        for segment in curve:
            if segment.is_corner:
                parts.append(f"L{point(segment.c)}L{point(segment.end_point)}")
            else:
                parts.append(f"C{point(segment.c1)} {point(segment.c2)} {point(segment.end_point)}")
        parts.append("Z")
    return "".join(parts)


def emblem_paths():
    mask = np.array(Image.open(SOURCE / "yildiz-emblem.png").convert("L")) > 128
    height, width = mask.shape
    curves = [
        (c, bounds(c))
        for c in trace(mask)
        if not ((bounds(c)[2] - bounds(c)[0]) > 0.95 * width and (bounds(c)[3] - bounds(c)[1]) > 0.95 * height)
    ]
    x0 = min(b[0] for _, b in curves)
    y0 = min(b[1] for _, b in curves)
    x1 = max(b[2] for _, b in curves)
    y1 = max(b[3] for _, b in curves)
    side = max(x1 - x0, y1 - y0)
    scale = 100.0 / side
    ox = x0 - (side - (x1 - x0)) / 2
    oy = y0 - (side - (y1 - y0)) / 2

    def is_star(b):
        return b[0] > 0.55 * width and b[1] > 0.19 * height and b[3] < 0.4 * height and (b[2] - b[0]) < 0.2 * width

    star = [c for c, b in curves if is_star(b)]
    body = [c for c, b in curves if not is_star(b)]
    sb = [bounds(c) for c in star]
    center = (
        round(((min(b[0] for b in sb) + max(b[2] for b in sb)) / 2 - ox) * scale, 2),
        round(((min(b[1] for b in sb) + max(b[3] for b in sb)) / 2 - oy) * scale, 2),
    )
    return to_path(body, scale, ox, oy), to_path(star, scale, ox, oy), center


def word_letters():
    rgba = np.array(Image.open(SOURCE / "yildiz-wordmark.png").convert("RGBA"))
    mask = rgba[:, :, 3] > 128
    split = mask.shape[1] * 0.275
    letters = [(c, bounds(c)) for c in trace(mask) if bounds(c)[0] > split]
    top = min(b[1] for _, b in letters)
    bottom = max(b[3] for _, b in letters)
    left = min(b[0] for _, b in letters)
    scale = 100.0 / (bottom - top)

    groups = []
    for curve, b in sorted(letters, key=lambda cb: (cb[1][2] - cb[1][0]) * (cb[1][3] - cb[1][1]), reverse=True):
        host = next(
            (g for g in groups if g["box"][0] <= b[0] and b[2] <= g["box"][2] and g["box"][1] <= b[1] and b[3] <= g["box"][3]),
            None,
        )
        if host:
            host["curves"].append(curve)
        else:
            groups.append({"box": b, "curves": [curve]})
    groups.sort(key=lambda g: g["box"][0])
    width = round((max(g["box"][2] for g in groups) - left) * scale, 2)
    return width, [
        {
            "d": to_path(g["curves"], scale, left, top),
            "x": round((g["box"][0] - left) * scale, 2),
            "w": round((g["box"][2] - g["box"][0]) * scale, 2),
        }
        for g in groups
    ]


def main() -> None:
    body, star, center = emblem_paths()
    width, letters = word_letters()

    rows = ",\n".join(f"  {{ x: {l['x']}, w: {l['w']}, d: '{l['d']}' }}" for l in letters)
    (ROOT / "web/src/lib/brand.js").write_text(
        f"export const EMBLEM_BODY =\n  '{body}';\n\n"
        f"export const EMBLEM_STAR =\n  '{star}';\n\n"
        f"export const STAR_CENTER = [{center[0]}, {center[1]}];\n\n"
        f"export const WORD_WIDTH = {width};\n\n"
        f"export const WORD_LETTERS = [\n{rows}\n];\n",
        encoding="utf-8",
    )

    (ROOT / "web/public/favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 112 112">'
        f'<rect x="-6" y="-6" width="112" height="112" rx="22" fill="{VOID}"/>'
        f'<path fill="{INK_DARK}" fill-rule="evenodd" d="{body}"/><path fill="{STAR}" d="{star}"/></svg>\n',
        encoding="utf-8",
    )

    emblem = Image.open(SOURCE / "yildiz-emblem.png").convert("L")
    white = Image.new("RGBA", emblem.size, (255, 255, 255, 0))
    white.putalpha(emblem)
    white = white.crop(white.getbbox())
    side = max(white.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(white, ((side - white.width) // 2, (side - white.height) // 2))
    favicon = Image.new("RGBA", (64, 64), (4, 6, 10, 255))
    favicon.alpha_composite(square.resize((52, 52), Image.LANCZOS), (6, 6))
    favicon.save(ROOT / "web/public/favicon.png", optimize=True)

    scale = 0.5
    total = 122 + width * scale
    paths = "".join(f'<path d="{l["d"]}"/>' for l in letters)
    for name, ink in (("dark", INK_DARK), ("light", INK_LIGHT)):
        (ROOT / f"docs/brand/yildiz-lockup-{name}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total:.1f} 100" role="img" aria-label="YILDIZ CTI">'
            f'<path fill="{ink}" fill-rule="evenodd" d="{body}"/><path fill="{STAR}" d="{star}"/>'
            f'<g fill="{ink}" fill-rule="evenodd" transform="translate(122 25) scale({scale})">{paths}</g></svg>\n',
            encoding="utf-8",
        )
    print(f"marka varlıkları üretildi: {len(letters)} harf, yıldız merkezi {center}")


if __name__ == "__main__":
    main()
