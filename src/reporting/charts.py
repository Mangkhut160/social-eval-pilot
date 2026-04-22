from __future__ import annotations

import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties


_CHART_FONT_PATH_CANDIDATES = (
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
)


@lru_cache(maxsize=1)
def _resolve_chart_font() -> FontProperties | None:
    for candidate in _CHART_FONT_PATH_CANDIDATES:
        if candidate.exists():
            return FontProperties(fname=str(candidate))
    return None


def generate_radar_chart_base64(labels: list[str], values: list[float]) -> str:
    if not labels or not values:
        return ""

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values_cycle = values + values[:1]
    angles_cycle = angles + angles[:1]

    figure, axis = plt.subplots(figsize=(4, 4), subplot_kw={"polar": True})
    axis.plot(angles_cycle, values_cycle, linewidth=2)
    axis.fill(angles_cycle, values_cycle, alpha=0.25)
    axis.set_xticks(angles)
    axis.set_xticklabels(labels, fontsize=8, fontproperties=_resolve_chart_font())
    axis.set_yticklabels([])
    axis.set_ylim(0, 100)

    buffer = BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=150)
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
