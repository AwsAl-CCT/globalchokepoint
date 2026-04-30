
import streamlit as st
from data.portwatch_api import load_portwatch_data
from data.profile_table import build_chokepoint_profile
from data.stress_table import build_weekly_stress_table
import plotly.express as px

st.set_page_config(layout="wide")

st.title("Global Maritime Chokepoint Monitoring")

# ---- Data load (cached) ----
@st.cache_data(ttl=86400)
def load_data():
    return load_portwatch_data()

df = load_data()

# ---- Build tables ----
profile_table = build_chokepoint_profile(df)

weekly_stress_table = build_weekly_stress_table(
    df,
    baseline_start="2019-01-01",   # ← FRONTEND CONTROL LATER
    baseline_end="2019-12-31"      # ← FRONTEND CONTROL LATER
)

# ---- Latest weekly stress per chokepoint ----
latest_stress = (
    weekly_stress_table
        .sort_values(["portname", "period_start"])
        .groupby("portname", as_index=False)
        .tail(1)
        .reset_index(drop=True)
)

# ---- Temporary display for verification ----
# st.subheader("Chokepoint Profile Table")
# st.dataframe(profile_table.head())

# st.subheader("Weekly Stress Table (sample)")
# st.dataframe(weekly_stress_table.head())

# ----  Build current (latest) state per chokepoint ----

# Get latest weekly row per chokepoint
latest_stress = (
    weekly_stress_table
        .sort_values(["portname", "period_start"])
        .groupby("portname", as_index=False)
        .tail(1)
        .reset_index(drop=True)
)

# Merge with profile table
current_state_table = (
    profile_table
        .merge(
            latest_stress,
            on=["portid", "portname"],
            how="inner"
        )
)

from data.chokepoints_geo import load_chokepoint_locations

geo_df = load_chokepoint_locations()

current_state_geo = (
    current_state_table
        .merge(
            geo_df,
            on="portname",
            how="left"
        )
)

# ---- STEP 5: Stress-encoded chokepoint map ----

fig = px.scatter_map(
    current_state_geo,
    lat="lat",
    lon="lon",
    hover_name="portname",
    hover_data={
        "exposure_type": True,
        "dominant_vessel_type": True,
        "dominance_strength": True,
        "n_total_index": ":.2f",
        "capacity_index": ":.2f",
        "n_total_volatility": ":.2f",
    },
    color="capacity_index",
    color_continuous_scale="RdYlGn_r",
    range_color=(0.4, 1.2),  # anchors interpretation
    size=(current_state_geo["capacity_index"] - 1).abs(),
    size_max=30,
    zoom=1,
    height=600,
)

fig.update_layout(
    margin={"r": 0, "t": 0, "l": 0, "b": 0}
)

st.subheader("Global Chokepoint Stress Map (Capacity-Based)")
st.plotly_chart(fig, use_container_width=True)