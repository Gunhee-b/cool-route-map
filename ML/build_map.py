"""Generate interactive HTML maps (Folium/Leaflet) and KPI summary charts using Real-Feel temperature."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import folium
import matplotlib
import networkx as nx

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import CITIES, DEFAULT_HEAT_ALPHA, RESULTS_DIR
from cool_router import compute_shortest_and_cool_routes, find_nearest_node


def _temp_to_hex(temp_c: float, t_min: float, t_max: float) -> str:
    """Map street temperature to a clean blue -> green -> yellow -> orange -> red palette."""
    if t_max <= t_min:
        return "#3b82f6"
    ratio = max(0.0, min(1.0, (temp_c - t_min) / (t_max - t_min)))
    stops = [
        (0.00, (37, 99, 235)),   # Cool blue
        (0.30, (16, 185, 129)),  # Shaded green
        (0.55, (250, 204, 21)),  # Warm yellow
        (0.80, (249, 115, 22)),  # Hot orange
        (1.00, (220, 38, 38)),   # Very hot red
    ]
    for i in range(len(stops) - 1):
        r0, c0 = stops[i]
        r1, c1 = stops[i + 1]
        if r0 <= ratio <= r1:
            t = (ratio - r0) / (r1 - r0)
            rgb = tuple(int(c0[k] + t * (c1[k] - c0[k])) for k in range(3))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
    return "#dc2626"


def build_city_map(
    city_key: str,
    G: nx.Graph,
    benchmark_summary: dict[str, Any],
    alpha: float = DEFAULT_HEAT_ALPHA,
    out_html: Path | None = None,
) -> Path:
    """Build a standalone interactive HTML map colored by ground-level Real-Feel temperature (°C)."""
    cfg = CITIES[city_key]
    if out_html is None:
        out_html = RESULTS_DIR / f"{city_key}_cool_routes.html"
    out_html.parent.mkdir(parents=True, exist_ok=True)

    m = folium.Map(
        location=[cfg["center_lat"], cfg["center_lon"]],
        zoom_start=16,
        tiles=None,
        control_scale=True,
    )
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors, Humanitarian OpenStreetMap Team",
        name="Clean Street Map (OSM HOT)",
        max_zoom=19,
        show=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap France &copy; OpenStreetMap contributors",
        name="English-Label Street Map (OSM FR)",
        max_zoom=19,
        show=False,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Satellite Imagery (Esri)",
        max_zoom=19,
        show=False,
    ).add_to(m)

    rf_vals = [d["real_feel_c"] for _, _, d in G.edges(data=True)]
    rf_min, rf_max = min(rf_vals), max(rf_vals)

    # Layer 1: All walkable streets colored by ground-level Real-Feel temperature
    heat_layer = folium.FeatureGroup(name="Ground-Level Real-Feel Heat Map (°C)", show=True)
    for _, _, data in G.edges(data=True):
        color = _temp_to_hex(data["real_feel_c"], rf_min, rf_max)
        tooltip = (
            f"<b>{data['name']}</b> ({data['highway']})<br>"
            f"<b>Real-Feel: {data['real_feel_c']:.1f} °C</b><br>"
            f"Air Temp: {data['temp_c']:.1f} °C | Humidity: {data['humidity_pct']:.0f}%<br>"
            f"Shade: {data['shade_pct']:.0f}% | Length: {data['length_m']:.0f} m"
        )
        folium.PolyLine(
            locations=data["coords"],
            color=color,
            weight=3.2,
            opacity=0.72,
            tooltip=tooltip,
        ).add_to(heat_layer)
    heat_layer.add_to(m)

    # Layer 2..N: Demo pedestrian trips comparing Shortest Path vs. Cool Path
    trip_summaries_html = []
    for idx, trip in enumerate(cfg["demo_trips"]):
        s_node = find_nearest_node(G, trip["start"][0], trip["start"][1])
        e_node = find_nearest_node(G, trip["end"][0], trip["end"][1])
        comp = compute_shortest_and_cool_routes(G, s_node, e_node, alpha=alpha)
        short_r = comp["shortest"]
        cool_r = comp["cool"]

        fg = folium.FeatureGroup(name=f"Trip {idx + 1}: {trip['name']}", show=(idx == 0))

        folium.PolyLine(
            locations=short_r.coords,
            color="#991b1b",
            weight=6,
            opacity=0.85,
            dash_array="8, 8",
            tooltip=(
                f"<b>Shortest Path</b><br>"
                f"Distance: {short_r.distance_m:.0f} m ({short_r.walk_time_min:.1f} min)<br>"
                f"<b>Real-Feel: {short_r.avg_real_feel_c:.2f} °C</b> (Air: {short_r.avg_temp_c:.1f} °C, RH: {short_r.avg_humidity_pct:.0f}%)<br>"
                f"Shade: {short_r.avg_shade_pct:.0f}%"
            ),
        ).add_to(fg)

        folium.PolyLine(
            locations=cool_r.coords,
            color="#0284c7",
            weight=6.5,
            opacity=0.95,
            tooltip=(
                f"<b>Cool Path (Recommended)</b><br>"
                f"Distance: {cool_r.distance_m:.0f} m ({cool_r.walk_time_min:.1f} min)<br>"
                f"<b>Real-Feel: {cool_r.avg_real_feel_c:.2f} °C</b> (Air: {cool_r.avg_temp_c:.1f} °C, RH: {cool_r.avg_humidity_pct:.0f}%)<br>"
                f"Shade: {cool_r.avg_shade_pct:.0f}%<br>"
                f"<b>Saved: -{comp['real_feel_reduction_c']:.2f} °C Real-Feel</b> (+{comp['extra_distance_m']:.0f} m)"
            ),
        ).add_to(fg)

        folium.Marker(
            location=[G.nodes[s_node]["lat"], G.nodes[s_node]["lon"]],
            tooltip=f"Start: {trip['name'].split('→')[0].strip()}",
            icon=folium.Icon(color="green", icon="play", prefix="fa"),
        ).add_to(fg)
        folium.Marker(
            location=[G.nodes[e_node]["lat"], G.nodes[e_node]["lon"]],
            tooltip=f"Destination: {trip['name'].split('→')[-1].strip()}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        ).add_to(fg)

        fg.add_to(m)

        trip_summaries_html.append(
            f"<div style='margin-top:6px;padding-top:6px;border-top:1px solid #e5e7eb;'>"
            f"<b>Trip {idx + 1}: {trip['name']}</b><br>"
            f"<span style='color:#991b1b;'>Shortest:</span> {short_r.distance_m:.0f} m | {short_r.avg_real_feel_c:.1f} °C feels-like<br>"
            f"<span style='color:#0284c7;'>Cool Path:</span> {cool_r.distance_m:.0f} m | {cool_r.avg_real_feel_c:.1f} °C feels-like<br>"
            f"<span style='color:#059669;'><b>Result: -{comp['real_feel_reduction_c']:.2f} °C real-feel</b> "
            f"(+{comp['extra_distance_m']:.0f} m / +{comp['extra_time_min']:.1f} min)</span>"
            f"</div>"
        )

    folium.LayerControl(collapsed=False).add_to(m)

    panel_html = f"""
    <div style="
        position: fixed; bottom: 20px; left: 20px; z-index: 9999;
        background: rgba(255,255,255,0.95); padding: 14px 16px; border-radius: 10px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18); max-width: 345px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 12.5px; color: #1f2937; line-height: 1.45;
    ">
        <div style="font-size:14.5px;font-weight:700;margin-bottom:4px;color:#111827;">
            OnEvolution Cool-Route Map — {cfg['display_name']}
        </div>
        <div style="font-size:11.5px;color:#4b5563;margin-bottom:8px;">
            {G.number_of_edges():,} walkable streets | Base: {cfg['base_temp_c']:.1f} °C air, <b>{cfg['base_humidity_pct']:.0f}% RH</b><br>
            {benchmark_summary['n_trips']}-trip avg: <b>-{benchmark_summary['avg_real_feel_reduction_c']:.2f} °C Real-Feel</b>
            ({benchmark_summary['avg_heat_exposure_reduction_pct']:.1f}% less excess heat)
            for <b>+{benchmark_summary['avg_extra_dist_pct']:.1f}%</b> distance
        </div>
        <div style="margin-bottom:8px;">
            <span style="display:inline-block;width:20px;height:4px;background:#0284c7;vertical-align:middle;"></span>
            Cool Path (Recommended) &nbsp;
            <span style="display:inline-block;width:20px;height:0;border-top:3px dashed #991b1b;vertical-align:middle;"></span>
            Shortest Path
        </div>
        <div style="margin-bottom:6px;">
            <div style="height:8px;border-radius:4px;background:linear-gradient(to right,#2563eb,#10b981,#facc15,#f97316,#dc2626);"></div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#4b5563;">
                <span>{rf_min:.1f} °C Real-Feel</span>
                <span>{rf_max:.1f} °C Real-Feel</span>
            </div>
        </div>
        {''.join(trip_summaries_html)}
    </div>
    """
    m.get_root().html.add_child(folium.Element(panel_html))

    m.save(str(out_html))
    return out_html


def build_kpi_chart(summaries: dict[str, dict[str, Any]], out_png: Path | None = None) -> Path:
    """Create a clean KPI comparison chart for Seoul (humid) vs. Madrid (dry)."""
    if out_png is None:
        out_png = RESULTS_DIR / "kpi_summary.png"
    out_png.parent.mkdir(parents=True, exist_ok=True)

    city_keys = list(summaries.keys())
    labels = [
        f"{CITIES[k]['display_name'].split(' (')[0]}\n({CITIES[k]['base_humidity_pct']:.0f}% RH)"
        for k in city_keys
    ]

    rf_red = [summaries[k]["avg_real_feel_reduction_c"] for k in city_keys]
    shade_gain = [summaries[k]["avg_shade_gain_pct"] for k in city_keys]
    extra_dist_pct = [summaries[k]["avg_extra_dist_pct"] for k in city_keys]
    heat_exp_red = [summaries[k]["avg_heat_exposure_reduction_pct"] for k in city_keys]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.7), dpi=150)
    fig.suptitle(
        "OnEvolution Cool-Route KPI Benchmark (Ground-Level Real-Feel: Heat Index + Shade)",
        fontsize=12.2,
        fontweight="bold",
        y=0.98,
    )

    x = range(len(labels))
    bars1 = axes[0].bar(x, rf_red, color=["#0284c7", "#0d9488"], width=0.48)
    axes[0].set_title("Average Real-Feel Temperature Saved (°C)")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(labels, fontsize=10.5)
    axes[0].set_ylabel("Real-Feel Saved (°C)")
    axes[0].set_ylim(0, max(rf_red + [1.0]) * 1.32)
    axes[0].grid(axis="y", linestyle="--", alpha=0.4)
    for bar, val in zip(bars1, rf_red):
        axes[0].text(bar.get_x() + bar.get_width() / 2, val + 0.08, f"-{val:.2f} °C", ha="center", fontweight="bold")

    width = 0.25
    b_heat = axes[1].bar([i - width for i in x], heat_exp_red, width=width, label="Excess Heat Reduced (%)", color="#10b981")
    b_shade = axes[1].bar(list(x), shade_gain, width=width, label="Shade Gained (% pts)", color="#3b82f6")
    b_dist = axes[1].bar([i + width for i in x], extra_dist_pct, width=width, label="Extra Walking Distance (%)", color="#f97316")
    axes[1].set_title("Cooling Benefit vs. Walking Distance Trade-off")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(labels, fontsize=10.5)
    axes[1].set_ylabel("Percentage (%)")
    max_y = max(heat_exp_red + shade_gain + extra_dist_pct + [10.0])
    axes[1].set_ylim(0, max_y * 1.28)
    axes[1].grid(axis="y", linestyle="--", alpha=0.4)
    axes[1].legend(fontsize=8.5, loc="upper right")

    for bars in (b_heat, b_shade, b_dist):
        for bar in bars:
            h = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width() / 2, h + 0.6, f"{h:.1f}%", ha="center", fontsize=8.5)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_png)
    plt.close(fig)
    return out_png
