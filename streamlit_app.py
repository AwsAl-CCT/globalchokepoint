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

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

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

# Compute stress band
current_state["stress_band"] = current_state["capacity_stress"].apply(stress_band)

# Determine which categories actually appear
actual = current_state["stress_band"].unique()

# Keep your intended order, but only for categories that exist
valid_order = [c for c in stress_order if c in actual]

# Apply safe categorical ordering
current_state["stress_band"] = (
    current_state["stress_band"]
    .astype("category")
    .cat.set_categories(valid_order, ordered=True)
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
    "Energy": "Mostly Energy flows",
    "Trade": "Mostly Trade flows",
    "Mixed": "Mostly Mixed flows (Energy + Trade)",
}).fillna("Mostly Trade flows")

current_state["dominant_vessel_human"] = (
    "Most ships are " + current_state["dominant_vessel_type"].astype(str).str.title()
)


# ============================================================
# Capacity impact estimate
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

    # st.markdown("### Select a chokepoint")

    selected_chokepoint = st.selectbox(
        "Select a chokepoint",
        options=sorted(current_state["portname"].unique()),
        index=None,
        placeholder="Search for a chokepoint…",
    )

    st.markdown("Stress levels", help="Stress is measured relative to normal (2019 baseline). Higher stress means the chokepoint is operating further below its typical capacity.")

    # st.caption("Stress levels", help="Stress is measured relative to normal (2019 baseline). Higher stress means the chokepoint is operating further below its typical capacity.")


    stress_filters = {
        level: st.checkbox(level, value=True, key=f"filter_{level}")
        for level in stress_order
    }

    # message placeholder (right under checkboxes)
    stress_message = st.empty()

    st.markdown("---")

    st.markdown("#### Baseline definition")
    st.markdown(
        
"Normal conditions are defined using average weekly maritime capacity observed during 2019. "
    "This reference year reflects typical global shipping patterns before COVID-19 disruptions, "
    "major canal capacity constraints, and recent geopolitical shocks that have since affected key routes."
    )


# ============================================================
# Apply stress filters (guard)
# ============================================================

active_stress_levels = [
    level for level, enabled in stress_filters.items() if enabled
]

if not active_stress_levels:
    active_stress_levels = stress_order.copy()
    stress_message.info(
        "At least one stress level must be selected. Showing all stress levels."
    )
else:
    stress_message.empty()


filtered_state = current_state[
    current_state["stress_band"].isin(active_stress_levels)
].copy()


# ============================================================
# Focus logic
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
# Build map (clean)
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
        "Colour shows disruption severity. Size shows estimated capacity impact.",
        help="Colour indicates how far the chokepoint is operating below normal conditions. Size reflects the estimated volume of disrupted capacity, not just the number of ships."
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ============================================================
# Insights panel
# ============================================================

st.markdown("""
<style>
[data-testid="stMetricValue"] {
    font-size: 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)


if selection_active and selection_visible:

    cp_row = focused_state.iloc[0]
    result = build_interpretation(cp_row)

    st.subheader(f"Insights: {selected_chokepoint}")

    st.markdown(result["paragraph"])

    st.markdown("#### Key signals", help="Traffic refers to the number of ships passing through. Capacity reflects how much cargo those ships carry. Differences between the two can indicate changes in vessel size or loading.")
    
    cards = result["cards"]

    for i in range(0, len(cards), 3):
        cols = st.columns(3)
        for col, card in zip(cols, cards[i:i+3]):
            with col:
                st.metric(label=card["label"], value=card["value"])

elif selection_active and not selection_visible:
    st.info(
        f"{selected_chokepoint} is currently hidden by the selected stress filters."
    )

else:
    st.info("Select a chokepoint to view insights.")
