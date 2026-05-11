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
    geo_df,
    on="portname",
    how="left"
)


# ============================================================
# Stress derivation (capacity-based)
# ============================================================

# Continuous stress magnitude relative to baseline
current_state["capacity_stress"] = (
    1 - current_state["capacity_index"]
).clip(lower=0)


def stress_band(stress: float) -> str:
    """
    Map continuous stress into categorical risk bands.
    """
    if stress < 0.15:
        return "Neutral"
    elif stress < 0.30:
        return "Slightly stressed"
    elif stress < 0.50:
        return "Stressed"
    else:
        return "Severe"


current_state["stress_band"] = current_state["capacity_stress"].apply(stress_band)

# Explicit category order for filters and visual encoding
stress_order = ["Severe", "Stressed", "Slightly stressed", "Neutral"]

current_state["stress_band"] = pd.Categorical(
    current_state["stress_band"],
    categories=stress_order,
    ordered=True,
)


# ============================================================
# Human-readable fields for tooltips
# ============================================================

# More descriptive stress wording
stress_band_full_map = {
    "Severe": "Severely stressed",
    "Stressed": "Stressed",
    "Slightly stressed": "Slightly stressed",
    "Neutral": "Operating normally",
}

current_state["stress_band_full"] = (
    current_state["stress_band"]
    .astype(str)
    .map(stress_band_full_map)
)

# Human-readable stress percentage
current_state["stress_pct"] = (
    current_state["capacity_stress"] * 100
).round(0).astype(int)

# Human-readable “mostly passes through here” label
exposure_label_map = {
    "Energy": "Mostly: Energy flows",
    "Trade": "Mostly: Trade flows",
    "Mixed": "Mostly: Mixed flows (energy + trade)",
}

current_state["exposure_human"] = (
    current_state["exposure_type"]
    .map(exposure_label_map)
    .fillna("Mostly: Trade flows")
)

# Human-readable vessel dominance
current_state["dominant_vessel_human"] = (
    "Most ships: " + current_state["dominant_vessel_type"].astype(str).str.title()
)

# Human-readable stress label
current_state["capacity_stress_label"] = (
    current_state["stress_pct"].astype(str) + "% capacity reduction"
)


# ============================================================
# Estimated magnitude of capacity disruption (for size tooltip)
# ============================================================

# Estimated baseline capacity implied by current state and capacity index
current_state["baseline_capacity_est"] = (
    current_state["capacity"] / current_state["capacity_index"]
).where(current_state["capacity_index"] > 0)

# Estimated disrupted capacity
current_state["disrupted_capacity_est"] = (
    current_state["baseline_capacity_est"] * current_state["capacity_stress"]
)


def format_capacity(value):
    """
    Format estimated weekly impacted capacity for tooltip readability.
    Keeps the user-defined wording style.
    """
    if pd.isna(value):
        return "not available"
    if value >= 1_000_000_000:
        return f"~{value/1_000_000_000:.1f} billion units"
    elif value >= 1_000_000:
        return f"~{value/1_000_000:.0f} million units"
    else:
        return f"~{value:,.0f} units"


current_state["size_human"] = current_state["disrupted_capacity_est"].apply(format_capacity)


# ============================================================
# Marker sizing (visual balancing only)
# ============================================================

current_state["stress_size"] = (
    current_state["capacity_stress"]
    .clip(lower=0.15)
    .pow(0.6)
)


# ============================================================
# Layout: map + explanatory / control column
# ============================================================

map_col, info_col = st.columns([4.5, 1.5], gap="large")


# ------------------------------------------------------------
# Right-column controls and explanatory text
# NOTE:
# Controls are defined BEFORE the figure so they can be used
# to filter the map data.
# ------------------------------------------------------------

with info_col:
    # Spacer to align content visually with the map body
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)

    st.markdown("### Filter stress levels")

    stress_filters = {
        "Severe": st.checkbox("Severe", value=True, key="filter_severe"),
        "Stressed": st.checkbox("Stressed", value=True, key="filter_stressed"),
        "Slightly stressed": st.checkbox("Slightly stressed", value=True, key="filter_slightly_stressed"),
        "Neutral": st.checkbox("Neutral", value=True, key="filter_neutral"),
    }

    st.markdown("#### How to use this map")
    st.markdown(
        "*Use the checkboxes above to focus on specific stress levels.*"
    )

    st.markdown("---")

    st.markdown("#### Baseline definition")
    st.markdown(
        "Normal conditions are defined using **average weekly maritime capacity "
        "observed during 2019**, a pre‑disruption reference year before COVID‑19, "
        "major canal restrictions, and recent geopolitical conflicts."
    )


# ============================================================
# Apply stress-level filters
# ============================================================

active_stress_levels = [
    level for level, enabled in stress_filters.items() if enabled
]

filtered_state = current_state[
    current_state["stress_band"].isin(active_stress_levels)
].copy()


# ============================================================
# Build stress-encoded chokepoint map
# ============================================================

fig = px.scatter_map(
    filtered_state,
    lat="lat",
    lon="lon",
    color="stress_band",
    category_orders={"stress_band": stress_order},
    color_discrete_map={
        "Neutral": "#6f9460",            # light green / healthy
        "Slightly stressed": "#f1c40f",  # yellow
        "Stressed": "#e67e22",           # orange
        "Severe": "#e74c3c",             # red
    },
    size="stress_size",
    size_max=35,
    zoom=1.8,
    height=620,
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

# Fully controlled tooltip
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
    showlegend=False,   # native legend replaced by Streamlit filter controls
)


# ============================================================
# Render map
# ============================================================

with map_col:
    st.subheader("Global Chokepoint Stress Map")
    st.caption(
        "**Colour:** severity of disruption relative to normal conditions.  "
        "**Size:** estimated weekly capacity impact."
    )
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False}
    )
