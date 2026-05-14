import streamlit as st
import pandas as pd
import plotly.express as px

from data.portwatch_api import load_portwatch_data
from data.profile_table import build_chokepoint_profile
from data.stress_table import build_weekly_stress_table
from data.chokepoints_geo import load_chokepoint_locations
from logic.interpretation import build_interpretation

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
)

current_state = profile_table.merge(
    latest_stress,
    on=["portid", "portname"],
    how="inner",
)


# ============================================================
# Add geolocation
# ============================================================

geo_df = load_chokepoint_locations()

current_state = current_state.merge(
    geo_df,
    on="portname",
    how="left",
)


# ============================================================
# Stress derivation
# ============================================================

current_state["capacity_stress"] = (1 - current_state["capacity_index"]).clip(lower=0)


def stress_band(stress):
    if stress < 0.15:
        return "Neutral"
    elif stress < 0.30:
        return "Slightly stressed"
    elif stress < 0.50:
        return "Stressed"
    else:
        return "Severe"


stress_order = ["Severe", "Stressed", "Slightly stressed", "Neutral"]

current_state["stress_band"] = (
    current_state["capacity_stress"]
    .apply(stress_band)
    .astype("category")
    .cat.reorder_categories(stress_order, ordered=True)
)


# ============================================================
# Human‑readable fields
# ============================================================

current_state["stress_pct"] = (current_state["capacity_stress"] * 100).round(0).astype(int)

current_state["capacity_stress_label"] = (
    current_state["stress_pct"].astype(str) + "% capacity reduction"
)

current_state["stress_band_full"] = current_state["stress_band"].map({
    "Severe": "Severely stressed",
    "Stressed": "Stressed",
    "Slightly stressed": "Slightly stressed",
    "Neutral": "Operating normally",
})

current_state["exposure_human"] = current_state["exposure_type"].map({
    "Energy": "Mostly: Energy flows",
    "Trade": "Mostly: Trade flows",
    "Mixed": "Mostly: Mixed flows (energy + trade)",
}).fillna("Mostly: Trade flows")

current_state["dominant_vessel_human"] = (
    "Most ships: " + current_state["dominant_vessel_type"].astype(str).str.title()
)


# ============================================================
# Capacity impact estimate (tooltip + interpretation)
# ============================================================

current_state["baseline_capacity_est"] = (
    current_state["capacity"] / current_state["capacity_index"]
).where(current_state["capacity_index"] > 0)

current_state["disrupted_capacity_est"] = (
    current_state["baseline_capacity_est"] * current_state["capacity_stress"]
)


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

current_state["stress_size"] = (
    current_state["capacity_stress"].clip(lower=0.15).pow(0.6)
)


# ============================================================
# Layout
# ============================================================

map_col, info_col = st.columns([4.5, 1.5], gap="large")


# ============================================================
# Right‑hand controls
# ============================================================

with info_col:
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    st.markdown("### Focus on a chokepoint")

    selected_chokepoint = st.selectbox(
        "Select a chokepoint",
        options=sorted(current_state["portname"].unique()),
        index=None,
        placeholder="Search for a chokepoint…",
    )

    st.markdown("### Filter stress levels")

    stress_filters = {
        level: st.checkbox(level, value=True, key=f"filter_{level}")
        for level in stress_order
    }

    st.markdown("---")

    st.markdown("#### Baseline definition")
    st.markdown(
        "Normal conditions are defined using **average weekly maritime capacity "
        "observed during 2019**, a pre‑disruption reference year."
    )


# ============================================================
# Apply stress filters
# ============================================================

active_stress_levels = [
    level for level, enabled in stress_filters.items() if enabled
]

filtered_state = current_state[
    current_state["stress_band"].isin(active_stress_levels)
].copy()


# ============================================================
# Guarded chokepoint focus logic
# ============================================================

selection_active = selected_chokepoint is not None
selection_visible = (
    selection_active
    and selected_chokepoint in filtered_state["portname"].values
)

if selection_visible:
    focused_state = filtered_state[
        filtered_state["portname"] == selected_chokepoint
    ]
    map_center = {
        "lat": focused_state.iloc[0]["lat"],
        "lon": focused_state.iloc[0]["lon"],
    }
    map_zoom = 5.5

else:
    focused_state = filtered_state
    map_center = {"lat": 15, "lon": 20}
    map_zoom = 1.8


# ============================================================
# Build map
# ============================================================

fig = px.scatter_map(
    focused_state,
    lat="lat",
    lon="lon",
    color="stress_band",
    category_orders={"stress_band": stress_order},
    color_discrete_map={
        "Neutral": "#6f9460",
        "Slightly stressed": "#f1c40f",
        "Stressed": "#e67e22",
        "Severe": "#e74c3c",
    },
    size="stress_size",
    size_max=35,
    zoom=map_zoom,
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
    map_center=map_center,
    showlegend=False,
)

with map_col:
    st.subheader("Global Chokepoint Stress Map")
    st.caption(
        "**Colour:** severity of disruption relative to normal conditions.  "
        "**Size:** estimated weekly capacity impact."
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ============================================================
# Interpretation panel (protected)
# ============================================================

st.markdown("---")

if selection_active and selection_visible:
    cp_row = focused_state.iloc[0]

    result = build_interpretation(cp_row)

    st.subheader(f"Interpretation: {selected_chokepoint}")
    st.markdown(result["paragraph"])

    # Info cards under the interpretation (compact reinforcement)
    st.markdown("#### Key signals")
    cards = result["cards"]

    # Render cards in rows of 3 for clean layout
    for i in range(0, len(cards), 3):
        cols = st.columns(3)
        for col, card in zip(cols, cards[i:i+3]):
            with col:
                st.metric(label=card["label"], value=card["value"])

elif selection_active and not selection_visible:
    st.info(
        f"**{selected_chokepoint}** is currently hidden by the selected stress filters. "
        "Enable its stress level to view the interpretation."
    )

else:
    st.info("Select a chokepoint to view a detailed interpretation.")
