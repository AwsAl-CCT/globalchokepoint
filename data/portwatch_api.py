# data/portwatch_api.py

import requests
import pandas as pd

BASE_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/"
    "ArcGIS/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
)

def _arcgis_get(params):
    r = requests.get(BASE_URL, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def load_portwatch_data(start_date: str = "2019-01-01") -> pd.DataFrame:
    """
    Load full daily PortWatch chokepoint data from the API.
    This should be cached in Streamlit.
    """
    start_ms = int(pd.Timestamp(start_date, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp.utcnow().timestamp() * 1000)

    rows = []
    offset = 0
    page_size = 1000

    while True:
        payload = _arcgis_get({
            "where": "1=1",
            "time": f"{start_ms},{end_ms}",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size
        })

        batch = payload.get("features", [])
        if not batch:
            break

        rows.extend(r["attributes"] for r in batch)
        offset += page_size

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], unit="ms")

    return df

