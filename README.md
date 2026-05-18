# Global Maritime Chokepoint Monitoring

A Streamlit-based analytical dashboard for monitoring disruption and stress across key global maritime chokepoints.
You can see live app [here](https://globalchokepoint.streamlit.app/)
## Overview

This application tracks how major shipping routes are operating relative to normal conditions, using data-driven indicators to highlight where capacity constraints and operational disruptions are emerging.

The dashboard combines:
- Relative capacity performance (vs baseline)
- Traffic activity levels
- Stress classification
- Interpretable insights for each chokepoint

## Key Features

- Interactive global map showing chokepoint stress levels
- Colour-coded severity based on deviation from baseline conditions
- Size-scaled markers indicating estimated capacity impact
- Filterable stress levels for focused analysis
- Chokepoint-specific insights with plain-language interpretation
- Key signal cards highlighting traffic, capacity and flow patterns

## Methodology

- **Baseline year:** 2019  
  Selected as a reference for normal conditions prior to COVID-19 disruptions, canal restrictions, and recent geopolitical impacts.

- **Stress measurement:**  
  Based on deviation of capacity and traffic indices relative to the baseline.

- **Interpretation layer:**  
  Combines quantitative indicators with structured logic to explain the type, stability, and potential drivers of disruption.

## How to use

1. Filter stress levels to focus on relevant disruption ranges  
2. Select a chokepoint to analyse in detail  
3. Review map signals (colour and size)  
4. Use the insights panel to understand the underlying drivers  

## Tech Stack

- Python  
- Streamlit  
- Plotly  
- Pandas  

## Purpose

This project is designed as a practical analytical tool to:
- Demonstrate applied data analysis and visualisation
- Translate complex maritime data into actionable insights
- Support decision-making and situational awareness
