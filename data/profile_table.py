# data/profile_table.py

import pandas as pd


def build_chokepoint_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the chokepoint profile table (one row per chokepoint).

    This table contains:
    - vessel mix and dominance (data-derived)
    - typical capacity range
    - structural classifications (exposure_type, meaningful_bypass)
    """

    # --------------------
    # 1. Aggregate totals
    # --------------------
    count_cols = [
        "n_container",
        "n_dry_bulk",
        "n_general_cargo",
        "n_roro",
        "n_tanker",
        "n_cargo",
        "n_total",
    ]

    capacity_cols = [
        "capacity_container",
        "capacity_dry_bulk",
        "capacity_general_cargo",
        "capacity_roro",
        "capacity_tanker",
        "capacity_cargo",
        "capacity",
    ]

    agg = (
        df.groupby(["portid", "portname"], as_index=False)[count_cols + capacity_cols]
        .sum(numeric_only=True)
    )

    # --------------------
    # 2. Vessel shares
    # --------------------
    vessel_types = [
        "n_container",
        "n_dry_bulk",
        "n_general_cargo",
        "n_roro",
        "n_tanker",
    ]

    for col in vessel_types:
        agg[f"share_{col[2:]}"] = agg[col] / agg["n_total"]

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

    # --------------------
    # 3. Capacity range
    # --------------------
    cap_dist = (
        df.groupby(["portid", "portname"])["capacity"]
        .quantile([0.25, 0.50, 0.75])
        .unstack()
        .reset_index()
        .rename(
            columns={
                0.25: "capacity_p25",
                0.50: "capacity_median",
                0.75: "capacity_p75",
            }
        )
    )

    profile = agg.merge(cap_dist, on=["portid", "portname"], how="left")

    profile["typical_capacity_range"] = (
        profile["capacity_p25"].round(0).astype("Int64").astype(str)
        + " – "
        + profile["capacity_p75"].round(0).astype("Int64").astype(str)
    )

    # --------------------
    # 4. Structural classification
    # --------------------
    exposure_map = {
        "Strait of Hormuz": "Energy",
        "Bab el-Mandeb Strait": "Energy",
        "Yucatan Channel": "Energy",

        "Suez Canal": "Mixed",
        "Panama Canal": "Mixed",
        "Bosporus Strait": "Mixed",
        "Kerch Strait": "Mixed",
    }

    bypass_map = {
        # Reroutable shortcuts
        "Suez Canal": "Yes",
        "Panama Canal": "Yes",
        "Malacca Strait": "Yes",
        "Lombok Strait": "Yes",
        "Sunda Strait": "Yes",
        "Ombai Strait": "Yes",
        "Makassar Strait": "Yes",
        "Cape of Good Hope": "Yes",
        "Magellan Strait": "Yes",
        "Gibraltar Strait": "Yes",
        "Dover Strait": "Yes",

        # Gateways
        "Strait of Hormuz": "No",
        "Bab el-Mandeb Strait": "No",
        "Bosporus Strait": "No",
        "Kerch Strait": "No",
        "Bering Strait": "No",
    }

    profile["exposure_type"] = (
        profile["portname"].map(exposure_map).fillna("Trade")
    )

    profile["meaningful_bypass"] = (
        profile["portname"].map(bypass_map).fillna("No")
    )

    return profile

