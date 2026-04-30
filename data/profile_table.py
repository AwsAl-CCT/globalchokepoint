
import pandas as pd
import numpy as np

def build_chokepoint_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the chokepoint profile (one row per chokepoint).
    """

    count_cols = [
        "n_container", "n_dry_bulk", "n_general_cargo",
        "n_roro", "n_tanker", "n_cargo", "n_total"
    ]

    cap_cols = [
        "capacity_container", "capacity_dry_bulk",
        "capacity_general_cargo", "capacity_roro",
        "capacity_tanker", "capacity_cargo", "capacity"
    ]

    agg = (
        df.groupby(["portid", "portname"], as_index=False)[count_cols + cap_cols]
        .sum(numeric_only=True)
    )

    # Vessel shares
    vessel_cols = ["n_container", "n_dry_bulk", "n_general_cargo", "n_roro", "n_tanker"]
    for c in vessel_cols:
        agg[f"share_{c[2:]}"] = agg[c] / agg["n_total"]

    share_cols = [c for c in agg.columns if c.startswith("share_")]

    agg["dominant_vessel_type"] = (
        agg[share_cols]
        .idxmax(axis=1)
        .str.replace("share_", "", regex=False)
        .str.replace("_", " ", regex=False)
    )

    agg["max_vessel_share"] = agg[share_cols].max(axis=1)

    def dominance_strength(x):
        if x >= 0.60:
            return "Strong"
        elif x >= 0.40:
            return "Moderate"
        return "Weak"

    agg["dominance_strength"] = agg["max_vessel_share"].apply(dominance_strength)

    # Capacity distribution (IQR)
    cap_dist = (
        df.groupby(["portid", "portname"])["capacity"]
        .quantile([0.25, 0.50, 0.75])
        .unstack()
        .reset_index()
        .rename(columns={0.25: "capacity_p25", 0.5: "capacity_median", 0.75: "capacity_p75"})
    )

    profile = agg.merge(cap_dist, on=["portid", "portname"], how="left")

    profile["typical_capacity_range"] = (
        profile["capacity_p25"].round(0).astype("Int64").astype(str)
        + " – "
        + profile["capacity_p75"].round(0).astype("Int64").astype(str)
    )

    return profile

