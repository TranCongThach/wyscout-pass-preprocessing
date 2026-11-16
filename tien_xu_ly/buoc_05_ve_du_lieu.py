"""BƯỚC 05 — Vẽ dữ liệu đã làm sạch để kiểm tra trực quan và bàn giao.

Xuất phân bố điểm bắt đầu và mẫu vector; hiển thị riêng kết quả unknown.
Điểm cuối nghi ngờ không rõ (E1) chỉ vẽ dấu sao ở điểm bắt đầu, không vẽ vector giả.
Đây là hình dữ liệu, không thực hiện phân cụm hoặc đánh giá mô hình.
"""

import logging
from pathlib import Path

from matplotlib import patches
from matplotlib.figure import Figure
import pandas as pd

OUTCOME_STYLE = {
    "accurate": ("#22cfb8", "Chính xác"),
    "not_accurate": ("#ff5269", "Không chính xác"),
    "unknown": ("#d1d5db", "Chưa rõ kết quả"),
}


def draw_pitch(ax, pitch_color: str = "#16382b", line_color: str = "white") -> None:
    """Vẽ sân minh họa theo tỷ lệ 105:68; các trục và dữ liệu vẫn là phần trăm."""
    ax.set_facecolor(pitch_color)
    ax.add_patch(patches.Rectangle((0, 0), 100, 100, fill=False, ec=line_color, lw=1.6))
    ax.plot([50, 50], [0, 100], color=line_color, lw=1.3)
    ax.add_patch(patches.Ellipse((50, 50), 2 * 9.15 / 105 * 100, 2 * 9.15 / 68 * 100,
                                 fill=False, ec=line_color, lw=1.3))
    for depth_m, width_m in [(16.5, 40.3), (5.5, 18.3)]:
        depth, width = depth_m / 105 * 100, width_m / 68 * 100
        for left in [0, 100 - depth]:
            ax.add_patch(patches.Rectangle((left, 50 - width / 2), depth, width,
                                           fill=False, ec=line_color, lw=1.2))
    ax.scatter([11 / 105 * 100, 50, 100 - 11 / 105 * 100], [50, 50, 50],
               color=line_color, s=12)
    ax.set(xlim=(-2, 102), ylim=(-2, 102), xlabel="X (%)", ylabel="Y (%)")
    ax.set_aspect(68 / 105)


def create_distribution_figure(df: pd.DataFrame) -> Figure:
    """Tách phần tạo hình để kiểm tra được số điểm của cả ba nhóm kết quả."""
    fig = Figure(figsize=(12, 8), dpi=150)
    ax = fig.subplots()
    draw_pitch(ax)
    for outcome, (color, label) in OUTCOME_STYLE.items():
        subset = df[df["pass_outcome"] == outcome]
        if not subset.empty:
            ax.scatter(subset["x_start"], subset["y_start"], c=color, s=15, alpha=.55,
                       label=f"{label}: {len(subset):,}", edgecolors="none")
    match_ids = df["match_id"].unique()
    match_text = ", ".join(map(str, match_ids[:3]))
    if len(match_ids) > 3:
        match_text += f", ... ({len(match_ids)} trận)"
    ax.set_title(f"Phân bố điểm bắt đầu — {len(df):,} đường chuyền\n"
                 f"Trận: {match_text}", pad=12)
    ax.legend(loc="upper right", framealpha=.9)
    fig.tight_layout()
    return fig


def create_directions_figure(df: pd.DataFrame) -> Figure:
    """Mẫu cố định seed=42 để các lần chạy có thể so sánh trực quan."""
    fig = Figure(figsize=(12, 8), dpi=150)
    ax = fig.subplots()
    draw_pitch(ax)
    sample = df.sample(n=min(180, len(df)), random_state=42)
    outcomes_seen = set()
    for row in sample.itertuples(index=False):
        if row.end_unknown:
            ax.scatter(row.x_start, row.y_start, marker="*", c="gold", s=70,
                       label="Điểm cuối nghi ngờ chưa rõ (E1)" if "E1" not in outcomes_seen else None)
            outcomes_seen.add("E1")
            continue
        color, label = OUTCOME_STYLE[row.pass_outcome]
        ax.annotate("", xy=(row.x_end, row.y_end), xytext=(row.x_start, row.y_start),
                    arrowprops={"arrowstyle": "->", "color": color, "alpha": .65, "lw": 1})
        if row.pass_outcome not in outcomes_seen:
            ax.plot([], [], color=color, label=label)
            outcomes_seen.add(row.pass_outcome)
    ax.set_title(f"Mẫu {len(sample)} đường chuyền — tọa độ phần trăm", pad=12)
    if outcomes_seen:
        ax.legend(loc="upper right", framealpha=.9)
    fig.tight_layout()
    return fig


def generate_pitch_visualizations(
    df: pd.DataFrame, output_dist_path: str, output_dir_path: str, logger: logging.Logger,
) -> None:
    for path, make_figure in [
        (Path(output_dist_path), create_distribution_figure),
        (Path(output_dir_path), create_directions_figure),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        figure = make_figure(df)
        figure.savefig(path, bbox_inches="tight")
        figure.clear()
        logger.info("Đã lưu hình dữ liệu: %s", path)
