# logic/interpretation.py
from __future__ import annotations

from typing import Dict, List, Any
import pandas as pd


# ------------------------------------------------------------
# Helper interpretation functions (ported from notebook)
# ------------------------------------------------------------

def describe_chokepoint_type(exposure_type: str, meaningful_bypass: str) -> str:
    """Return a concise structural description of the chokepoint."""
    bypass_text = (
        "has a meaningful maritime bypass"
        if meaningful_bypass == "Yes"
        else "has no meaningful maritime bypass"
    )

    if exposure_type == "Energy":
        base = "an energy-oriented chokepoint"
    elif exposure_type == "Trade":
        base = "a trade-oriented chokepoint"
    elif exposure_type == "Mixed":
        base = "a mixed energy-and-trade chokepoint"
    else:
        base = "a chokepoint with unclear exposure type"

    return f"{base} and {bypass_text}"


def describe_normal_dominance(dominant_vessel_type: str, dominance_strength: str) -> str:
    """Explain what normally dominates this chokepoint."""
    return (
        f"Traffic is normally dominated by {dominant_vessel_type} vessels, "
        f"with {dominance_strength.lower()} dominance."
    )


def describe_volatility(n_total_volatility: float) -> str:
    """Translate volatility into plain English."""
    if pd.isna(n_total_volatility):
        return "an unknown level of operational stability"
    elif n_total_volatility < 0.10:
        return "low volatility, suggesting relatively stable weekly operations"
    elif n_total_volatility < 0.20:
        return "moderate volatility, suggesting some operational instability"
    else:
        return "high volatility, suggesting clearly erratic weekly operations"


def classify_stress_type(
    n_total_index: float,
    capacity_index: float,
    n_total_volatility: float,
    meaningful_bypass: str
) -> str:
    """
    Diagnose the kind of stress.
    This explains the mechanism, not the severity label.
    """

    if n_total_index >= 0.95 and capacity_index >= 0.95:
        return "There is no clear current stress signal relative to baseline."

    if capacity_index < 0.75 and n_total_index >= 0.75:
        if meaningful_bypass == "Yes":
            return (
                "Stress appears capacity-led rather than count-led. "
                "Ship numbers are holding up better than carrying capacity, "
                "which is consistent with rerouting or avoidance of larger vessels."
            )
        return (
            "Stress appears capacity-led rather than count-led. "
            "Ship numbers are holding up better than carrying capacity, "
            "suggesting constrained high-capacity transit."
        )

    if n_total_index < 0.75 and capacity_index < 0.75:
        if n_total_volatility < 0.12:
            if meaningful_bypass == "Yes":
                return (
                    "Both traffic and capacity are well below normal, but volatility is low. "
                    "This suggests a sustained rerouting or avoidance pattern rather than a short-term shock."
                )
            return (
                "Both traffic and capacity are well below normal, and volatility is low. "
                "This points to a sustained structural constraint rather than a temporary disruption."
            )
        return (
            "Both traffic and capacity are well below normal, and volatility is elevated. "
            "This suggests an active disruption or unstable operating environment."
        )

    if n_total_index < 0.80 and capacity_index >= 0.80:
        return (
            "Stress appears count-led rather than capacity-led. "
            "Fewer ships are transiting, but average carrying capacity is holding up better."
        )

    if n_total_index > 1.05 and capacity_index < 0.95:
        return (
            "Traffic volumes are elevated but capacity is weaker. "
            "This may indicate congestion, route substitution, or a less efficient vessel mix."
        )

    return (
        "The chokepoint is operating away from baseline, but the stress pattern is mixed "
        "rather than clearly attributable to a single mechanism."
    )


# ------------------------------------------------------------
# Public API: build narrative + cards
# ------------------------------------------------------------

def build_interpretation(row: pd.Series) -> Dict[str, Any]:
    """
    Build a fluent interpretation for a selected chokepoint row.
    """

    portname = row.get("portname", "Selected chokepoint")

    chokepoint_type_text = describe_chokepoint_type(
        row.get("exposure_type", ""),
        row.get("meaningful_bypass", "No")
    )

    dominance_text = describe_normal_dominance(
        row.get("dominant_vessel_type", "unknown"),
        row.get("dominance_strength", "Weak")
    )

    n_total_index = float(row.get("n_total_index", 1.0))
    capacity_index = float(row.get("capacity_index", 1.0))
    n_total_volatility = float(row.get("n_total_volatility", float("nan")))

    volatility_text = describe_volatility(n_total_volatility)

    stress_type_text = classify_stress_type(
        n_total_index,
        capacity_index,
        n_total_volatility,
        row.get("meaningful_bypass", "No")
    )

    traffic_pct = n_total_index * 100
    capacity_pct = capacity_index * 100

    period_start = row.get("period_start", "")
    period_end = row.get("period_end", "")

    stress_band_full = row.get("stress_band_full", "").lower()
    stress_pct = row.get("stress_pct", None)
    size_human = row.get("size_human", "not available")
    exposure_human = row.get("exposure_human", "")
    dominant_vessel_human = row.get("dominant_vessel_human", "")

    paragraph = (
        f"**{portname}** is {chokepoint_type_text}. {dominance_text} "
        f"In the latest available week ({period_start} to {period_end}), total traffic is running at approximately "
        f"**{traffic_pct:.0f}%** of its baseline level, while carrying capacity is at about "
        f"**{capacity_pct:.0f}%** of baseline. "
        f"This means the chokepoint is currently **{stress_band_full}**. "
        f"Weekly activity shows {volatility_text}. "
        f"{stress_type_text}"
    )

    cards: List[Dict[str, str]] = []

    if stress_band_full:
        cards.append({"label": "Status", "value": stress_band_full.capitalize()})

    if stress_pct is not None:
        cards.append({"label": "Current stress", "value": f"{int(stress_pct)}% capacity reduction"})

    cards.append({"label": "Traffic vs baseline", "value": f"{traffic_pct:.0f}%"})
    cards.append({"label": "Capacity vs baseline", "value": f"{capacity_pct:.0f}%"})

    if exposure_human:
        cards.append({"label": "Flow profile", "value": exposure_human.replace("Mostly: ", "")})


    if dominant_vessel_human:
        dominance_strength = row.get("dominance_strength", "")

        value = dominant_vessel_human.replace("Most ships are ", "")

        if dominance_strength:
            value = f"{value} ({dominance_strength})"

        cards.append({
            "label": "Dominant vessel type",
            "value": value
        })

    cards.append({"label": "Estimated weekly impact", "value": size_human})

    return {"paragraph": paragraph, "cards": cards}
