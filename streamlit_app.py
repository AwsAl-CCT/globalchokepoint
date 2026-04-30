
import streamlit as st
from data.portwatch_api import load_portwatch_data
from data.profile_table import build_chokepoint_profile
from data.stress_table import build_weekly_stress_table

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

st.subheader("Current Chokepoint State + Geolocation (Validation)")
st.dataframe(
    current_state_geo[[
        "portname",
        "lat",
        "lon",
        "exposure_type",
        "dominant_vessel_type",
        "n_total_index",
        "capacity_index",
    ]].sort_values("portname")
)