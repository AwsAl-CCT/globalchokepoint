import streamlit as st
import pandas as pd
import plotly.express as px

from data.portwatch_api import load_portwatch_data
from data.profile_table import build_chokepoint_profile
from data.stress_table import build_weekly_stress_table
from data.chokepoints_geo import load_chokepoint_locations


# ============================================================
# App configuration
# ============================================================

st.set_page_config(
    page_title="Global Maritime Chokepoint Monitoring",
    layout="wide",
)

st.title("Global Maritime Chokepoint Monitoring")


# ============================================================
# Data loading (cached)
# ============================================================

@st.cache_data(ttl=86400)
def load_data():
    """Load raw PortWatch chokepoint data (cached)."""
    return load_portwatch_data()

df = load_data()


# ============================================================
# Build analytical tables
# ============================================================

profile_table = build_chokepoint_profile(df)

weekly_stress_table = build_weekly_stress_table(
    df,
    baseline_start="2019-01-01",
    baseline_end="2019-12-31",
)


# ============================================================
# Latest state per chokepoint
# ============================================================

latest_stress = (
    weekly_stress_table
    .sort_values(["portname", "period_start"])
    .groupby("portname", as_index=False)
    .tail(1)
    .reset_index(drop=True)
)

current_state = (
    profile_table
    .merge(latest_stress, on=["portid", "portname"], how="inner")
)


# ============================================================
# Add geolocation
# ============================================================

geo_df = load_chokepoint_locations()

current_state = current_state.merge(
    geo_df, on="portname", how="left"
)


# ============================================================
# Stress derivation (capacity-based)
# ============================================================

# Continuous stress magnitude
current_state["capacity_stress"] = (
    1 - current_state["capacity_index"]
).clip(lower=0)


def stress_band(stress: float) -> str:
    """Map continuous stress into categorical risk bands."""
    if stress < 0.15:
        return "Neutral"
    elif stress < 0.30:
        return "Watch"
    elif stress < 0.50:
        return "Stressed"
    else:
        return "Severe"


current_state["stress_band"] = current_state["capacity_stress"].apply(stress_band)

# Explicit category order (IMPORTANT)
stress_order = ["Severe", "Stressed", "Watch", "Neutral"]

current_state["stress_band"] = pd.Categorical(
    current_state["stress_band"],
    categories=stress_order,
    ordered=True,
)

# Human-readable tooltip label
current_state["capacity_stress_label"] = (
    (current_state["capacity_stress"] * 100)
    .round(0)
    .astype(int)
    .astype(str)
    + "% capacity reduction"
)

# Dampened size scaling (visual balance)
current_state["stress_size"] = (
    current_state["capacity_stress"]
    .clip(lower=0.15)
    .pow(0.6)
)

# ------------------------------------------------------------
# Human-readable tooltip fields (presentation layer)
# ------------------------------------------------------------

# More descriptive stress wording (what the user sees)
stress_band_full_map = {
    "Severe": "Severely stressed",
    "Stressed": "Stressed",
    "Watch": "Watch (mild stress)",
    "Neutral": "Operating normally",
}

current_state["stress_band_full"] = current_state["stress_band"].astype(str).map(stress_band_full_map)

# Human-readable stress percent
current_state["stress_pct"] = (current_state["capacity_stress"] * 100).round(0).astype(int)

# Human-readable “mostly passes through here” text
exposure_label_map = {
    "Energy": "Mostly: Energy flows",
    "Trade": "Mostly: Trade flows",
    "Mixed": "Mostly: Mixed flows (energy + trade)",
}
current_state["exposure_human"] = current_state["exposure_type"].map(exposure_label_map).fillna("Mostly: Trade flows")

# Human-readable vessel dominance
current_state["dominant_vessel_human"] = (
    "Most ships: " + current_state["dominant_vessel_type"].astype(str).str.title()
)

# Human-readable size explanation (prevents confusion)
current_state["size_human"] = "Marker size: magnitude of stress (scaled)"

# ------------------------------------------------------------
# Estimated magnitude of capacity disruption (for marker size explanation)
# ------------------------------------------------------------

# Avoid division errors
current_state["baseline_capacity_est"] = (
    current_state["capacity"] / current_state["capacity_index"]
).where(current_state["capacity_index"] > 0)

current_state["disrupted_capacity_est"] = (
    current_state["baseline_capacity_est"] * current_state["capacity_stress"]
)

# Human-readable size label (billions / millions, rounded)

def format_capacity(value):
    if pd.isna(value):
        return "not available"
    if value >= 1_000_000_000:
        return f"~{value/1_000_000_000:.1f} billion units"
    elif value >= 1_000_000:
        return f"~{value/1_000_000:.0f} million units"
    else:
        return f"~{value:,.0f} units"

current_state["size_human"] = current_state["disrupted_capacity_est"].apply(format_capacity)

# ------------------------------------------------------------
# Stress-encoded chokepoint map (with custom tooltip)
# ------------------------------------------------------------

fig = px.scatter_map(
    current_state,
    lat="lat",
    lon="lon",
    color="stress_band",
    category_orders={"stress_band": stress_order},
    color_discrete_map={
        "Neutral": "#6f9460",
        "Watch":   "#f1c40f",
        "Stressed":"#e67e22",
        "Severe":  "#e74c3c",
    },
    size="stress_size",
    size_max=35,
    zoom=1.8,
    height=620,
    # Pass extra fields for the tooltip
    custom_data=[
        "portname",
        "stress_band_full",
        "stress_pct",
        "capacity_stress_label",
        "exposure_human",
        "dominant_vessel_human",
        "size_human",
    ],
)

# Custom tooltip using customdata (clean, fully controlled)
fig.update_traces(
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "%{customdata[1]}<br><br>"
        "<b>Current stress:</b> %{customdata[2]}% (%{customdata[3]})<br>"
        "<b>Flow profile:</b> %{customdata[4]}<br>"
        "<b>Dominant traffic:</b> %{customdata[5]}<br>"
        "<b>Estimated weekly impact:</b> %{customdata[6]}"
        "<extra></extra>"
    )
)

fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    legend_title_text="Stress level",
    map_center=dict(lat=15, lon=20),
    map_zoom=1.8,
)

st.subheader("Global Chokepoint Stress Map")
st.caption("Colour shows stress severity (thresholded). Size reflects magnitude of capacity disruption.")

st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
