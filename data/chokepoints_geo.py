# data/chokepoints_geo.py

import pandas as pd


def load_chokepoint_locations() -> pd.DataFrame:
    """
    Static lat/lon centroids for PortWatch chokepoints.
    Approximate; intended for visualisation only.
    """

    data = [
        ("Suez Canal", 30.585, 32.265),
        ("Panama Canal", 9.080, -79.680),
        ("Strait of Hormuz", 26.566, 56.250),
        ("Bab el-Mandeb Strait", 12.800, 43.300),
        ("Malacca Strait", 2.500, 101.000),

        ("Bosporus Strait", 41.100, 29.000),
        ("Dover Strait", 51.000, 1.500),
        ("Gibraltar Strait", 36.000, -5.500),
        ("Oresund Strait", 56.000, 12.700),

        ("Taiwan Strait", 24.000, 119.000),
        ("Korea Strait", 34.000, 129.000),
        ("Tsugaru Strait", 41.300, 140.500),
        ("Luzon Strait", 20.000, 121.000),

        ("Lombok Strait", -8.500, 116.000),
        ("Ombai Strait", -9.500, 125.000),
        ("Sunda Strait", -5.900, 105.900),
        ("Makassar Strait", -2.500, 118.000),

        ("Torres Strait", -10.500, 142.000),
        ("Magellan Strait", -53.000, -70.000),
        ("Yucatan Channel", 21.500, -86.800),

        ("Windward Passage", 20.000, -74.500),
        ("Mona Passage", 18.000, -68.000),

        ("Balabac Strait", 7.800, 117.000),
        ("Mindoro Strait", 12.500, 120.800),

        ("Bering Strait", 65.900, -168.900),
        ("Kerch Strait", 45.300, 36.500),

        ("Cape of Good Hope", -34.350, 18.470),
    ]

    return pd.DataFrame(data, columns=["portname", "lat", "lon"])
