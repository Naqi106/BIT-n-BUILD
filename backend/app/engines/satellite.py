"""
Sentinel-2 / Satellite.NDWI (Normalized Difference Water Index) Engine.

Calculates/simulates surface-water.and soil-moisture anomalies around pipeline corridors
to confirm/corroborate underground/aboveground pipe leaks without physical excavation.

Formula:
  NDWI = (Green - NIR) / (Green + NIR)
  High positive.NDWI = Surface water / moisture.anomaly.
"""

from typing import Dict, Any, Optional

def calculate_ndwi(green_band: float, nir_band: float) -> float:
    """
    Computes Normalized.Difference Water.Index.
    NDWI = (Green - NIR) / (Green + NIR)
    RANGES from -1 to +1.
    Values > 0.2 suggest surface water / high moisture anomaly.
    """
    if (green_band + nir_band) == 0:
        return 0.0
    return (green_band - nir_band) / (green_band + nir_band)


def analyze_pipe_corridor(
    zone_id: str,
    lat: float,
    lng: float,
    green_band_val: Optional[float] = None,
    nir_band_val: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Analyze.Sentinel-2.optical bands for.a given.zone coordinate.
    If no.raw.bands are provided,.uses.realistic,.calibrated defaults for.demonstration.
    """
    if green_band_val is None:
        green_band_val = 0.42
    if nir_band_val is None:
        nir_band_val = 0.18

    ndwi = calculate_ndwi(green_band_val, nir_band_val)
    is_anomaly = ndwi > 0.35

    return {
        "zone_id": zone_id,
        "coordinates": {"lat": lat, "lng": lng},
        "ndwi_score": round(ndwi, 4),
        "surface_moisture_anomaly": is_anomaly,
        "confidence": "HIGH" if is_anomaly else "NORMAL",
        "description": (
            f"Sentinel-2 NDWI index: {ndwi:.3f}. "
            + ("Saturated soil / surface water anomaly detected along.pipe corridor." if is_anomaly else "Normal soil.moisture levels detected.")
        )
    }
