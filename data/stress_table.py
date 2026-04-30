
import pandas as pd
import numpy as np

def build_weekly_stress_table(
    df: pd.DataFrame,
    baseline_start: str = "2019-01-01",
    baseline_end: str = "2019-12-31"
) -> pd.DataFrame:
    """
    Build the weekly stress table.
    """

    df = df.copy()
    df["period"] = df["date"].dt.to_period("W-SUN")
    df["period_start"] = df["period"].apply(lambda x: x.start_time)
    df["period_end"] = df["period"].apply(lambda x: x.end_time)

    count_fields = [
        "n_container", "n_dry_bulk", "n_general_cargo",
        "n_roro", "n_tanker", "n_cargo", "n_total"
    ]

    capacity_fields = [
        "capacity_container", "capacity_dry_bulk",
        "capacity_general_cargo", "capacity_roro",
        "capacity_tanker", "capacity_cargo", "capacity"
    ]

    weekly_avg = (
        df.groupby(
            ["portid", "portname", "period_start", "period_end"],
            as_index=False
        )[count_fields + capacity_fields]
        .mean()
    )

    weekly_avg = weekly_avg.rename(
        columns={c: f"{c}_avg" for c in count_fields + capacity_fields}
    )

    weekly_vol = (
        df.groupby(
            ["portid", "portname", "period_start", "period_end"]
        )["n_total"]
        .agg(["mean", "std"])
        .reset_index()
    )

    weekly_vol["n_total_volatility"] = weekly_vol["std"] / weekly_vol["mean"]
    weekly_vol = weekly_vol.drop(columns=["mean", "std"])

    weekly = weekly_avg.merge(
        weekly_vol,
        on=["portid", "portname", "period_start", "period_end"],
        how="left"
    )

    # Baseline
    baseline_start = pd.to_datetime(baseline_start)
    baseline_end = pd.to_datetime(baseline_end)

    baseline_subset = weekly[
        (weekly["period_start"] >= baseline_start) &
        (weekly["period_end"] <= baseline_end)
    ]

    baseline_cols = [c for c in weekly.columns if c.endswith("_avg")]

    baseline = (
        baseline_subset
        .groupby(["portid", "portname"], as_index=False)[baseline_cols]
        .mean()
    )

    baseline = baseline.rename(
        columns={c: f"baseline_{c[:-4]}" for c in baseline_cols}
    )

    weekly = weekly.merge(baseline, on=["portid", "portname"], how="left")

    # Core indices
    weekly["n_total_index"] = weekly["n_total_avg"] / weekly["baseline_n_total"]
    weekly["capacity_index"] = weekly["capacity_avg"] / weekly["baseline_capacity"]

    return weekly

