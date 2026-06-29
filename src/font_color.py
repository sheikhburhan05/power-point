"""Extract and apply PowerPoint font colors (RGB, theme, inherited)."""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_THEME_COLOR


def extract_font_brightness(font) -> float | None:
    """Return theme-color brightness modifier when present (e.g. -0.9 darkens bg2 to near-black)."""
    try:
        color = font.color
        if color.type in (MSO_COLOR_TYPE.RGB, MSO_COLOR_TYPE.SCHEME, MSO_COLOR_TYPE.PRESET):
            brightness = color.brightness
            if brightness != 0.0:
                return brightness
    except Exception:
        pass
    return None


def extract_font_color(font) -> tuple[str | None, str | None, str | None, float | None]:
    """Return (color_rgb, color_theme, color_type, color_brightness) for a font."""
    try:
        color = font.color
        brightness = extract_font_brightness(font)
        if color.type == MSO_COLOR_TYPE.RGB and color.rgb is not None:
            return str(color.rgb), None, "rgb", brightness
        if color.type == MSO_COLOR_TYPE.SCHEME and color.theme_color is not None:
            return None, color.theme_color.name, "scheme", brightness
        if color.type == MSO_COLOR_TYPE.PRESET and color.preset_color is not None:
            return None, color.preset_color.name, "preset", brightness
    except Exception:
        pass
    return None, None, "inherit", None


def _best_color_from_runs(runs) -> tuple[str | None, str | None, str | None, float | None]:
    """Pick the most explicit color from a list of runs (prefer rgb > scheme > inherit)."""
    best: tuple[str | None, str | None, str | None, float | None] = (
        None,
        None,
        "inherit",
        None,
    )
    priority = {"inherit": 0, "preset": 1, "scheme": 2, "rgb": 3}
    for run in runs:
        candidate = extract_font_color(run.font)
        if priority.get(candidate[2] or "inherit", 0) >= priority.get(best[2] or "inherit", 0):
            best = candidate
            if best[2] == "rgb":
                break
    return best


def apply_font_color(
    font,
    color_rgb: str | None = None,
    color_theme: str | None = None,
    color_type: str | None = None,
    color_brightness: float | None = None,
) -> None:
    """Apply stored color to a font run."""
    if color_type == "rgb" and color_rgb:
        try:
            hex_rgb = color_rgb.strip().lstrip("#")
            font.color.rgb = RGBColor(
                int(hex_rgb[0:2], 16),
                int(hex_rgb[2:4], 16),
                int(hex_rgb[4:6], 16),
            )
            if color_brightness is not None:
                font.color.brightness = color_brightness
        except Exception:
            pass
        return

    if color_type == "scheme" and color_theme:
        try:
            font.color.theme_color = MSO_THEME_COLOR[color_theme]
            if color_brightness is not None:
                font.color.brightness = color_brightness
        except Exception:
            pass
        return

    # inherit: do not set theme color — original "inherit" renders as default black
    # via the slide/master. Forcing TEXT_1 incorrectly turns it gray in many themes.
    if color_type == "inherit":
        return

    if color_type == "preset" and color_theme:
        try:
            from pptx.enum.dml import MSO_PRESET_COLOR

            font.color.preset_color = MSO_PRESET_COLOR[color_theme]
            if color_brightness is not None:
                font.color.brightness = color_brightness
        except Exception:
            pass
