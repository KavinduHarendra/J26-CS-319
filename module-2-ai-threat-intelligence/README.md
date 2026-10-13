# AI Threat Intelligence Module

An explainable AI Threat Intelligence Module that classifies UAV RF observations as
**Normal**, **Jamming**, or **Unknown Anomaly** using a Rule-Based Jamming Detector
and a Statistical Anomaly Engine — no machine learning, fully explainable.

## Overview

This module provides a transparent, interpretable pipeline for analysing UAV RF signals
and detecting hostile interference patterns. Every classification decision is backed by
human-readable rules and statistical thresholds, making it audit-friendly and suitable
for safety-critical deployment.

## Project Structure

```
ai-threat-intel-module/
├── src/          # Core detection and classification logic
├── tests/        # Unit and integration tests (pytest)
├── data/         # RF observation datasets (raw & processed)
├── requirements.txt
└── README.md
```

## Getting Started

```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

## Classification Labels

| Label           | Description                                        |
|-----------------|----------------------------------------------------|
| Normal          | RF environment within expected baseline parameters |
| Jamming         | Rule-based match against known jamming signatures  |
| Unknown Anomaly | Statistical outlier that falls outside baseline    |
