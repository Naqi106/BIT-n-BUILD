"""
Sentinel-2 / Satellite NDWI (Normalized Difference Water Index) Engine
-- Person 1 (Data + ML), roadmap section 5.4.

Role in AltoMare: a low-cost SECOND OPINION on a zone already flagged by
ground signals (billing anomalies, worsening NRW). NDWI is the standard
index:

    NDWI = (Green - NIR) / (Green + NIR)      range -1 .. +1

    > 0.2   suggests surface water / high soil moisture
    > 0.35  treated here as an anomaly (ANOMALY_THRESHOLD)

Honesty rules (repo convention: never show unlabelled fake data):
- Band reflectance (B03/B08) comes from real imagery when the caller
  provides it; this deployment has no Sentinel credentials configured, so
  the router reports ndwi_status="bands_not_configured" instead of
  inventing a score.
- The scene CATALOG is queried live and free of charge (Element84 Earth
  Search, no API key) so the demo shows a real Sentinel-2 acquisition.
- analyze_pipe_corridor()'s no-band path uses calibrated demonstration
  bands and says so via band_source / is_simulated on every response.
- Resolution caveat (roadmap 5.4): 10 m pixels only catch large,
  sustained leaks -- never a small one.
"""

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

# NDWI thresholds -----------------------------------------------------------
ANOMALY_THRESHOLD = 0.35   # > this => surface-moisture anomaly
SUGGESTION_THRESHOLD = 0.20  # > this => worth a human look (documented range)

# Approximate public centroids (±500 m) of each named Lucknow ward cluster.
# Coordinates are real localities; they are ward-level approximations, not
# surveyed pipeline positions.
LUCKNOW_ZONE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "zone_1":  (26.845, 80.942),   # Hazratganj & Kaiserbagh
    "zone_2":  (26.890, 80.963),   # Aliganj & Sector D
    "zone_3":  (26.965, 80.945),   # Indira Nagar
    "zone_4":  (26.945, 80.950),   # Gomti Nagar & Vibhuti Khand
    "zone_5":  (26.838, 80.950),   # Alambagh & Awadh Vihar
    "zone_6":  (26.869, 80.942),   # Chowk & Aminabad
    "zone_7":  (26.848, 80.906),   # Rajajipuram & Krishna Nagar
    "zone_8":  (26.885, 81.000),   # Chinhat & Faizabad Road
    "zone_9":  (26.908, 80.948),   # Mahanagar & Nirala Nagar
    "zone_10": (26.830, 80.895),   # Telibagh & Sushant Golf City
    "zone_11": (26.880, 80.985),   # Vikas Nagar & Jankipuram
    "zone_12": (26.775, 80.948),   # Cantonment & Sadar
}

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
CATALOG_WINDOW_DAYS = 30          # look back this far for a usable scene
MAX_CLOUD_COVER = 40.0            # % -- prefer clearer scenes in the window


def calculate_ndwi(green_band: float, nir_band: float) -> float:
    """
    Computes Normalized Difference Water Index.
    NDWI = (Green - NIR) / (Green + NIR), range -1 to +1.
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
    Analyze Sentinel-2 optical bands for a given zone coordinate.

    If no raw bands are provided, calibrated demonstration bands are used
    and the result is labelled band_source="calibrated_demo" +
    is_simulated=True so no consumer can present it as live imagery.
    """
    if green_band_val is None or nir_band_val is None:
        green_band_val = 0.42
        nir_band_val = 0.18
        band_source = "calibrated_demo"
        is_simulated = True
    else:
        band_source = "provided_reflectance"
        is_simulated = False

    ndwi = calculate_ndwi(green_band_val, nir_band_val)
    is_anomaly = ndwi > ANOMALY_THRESHOLD

    return {
        "zone_id": zone_id,
        "coordinates": {"lat": lat, "lng": lng},
        "ndwi_score": round(ndwi, 4),
        "surface_moisture_anomaly": is_anomaly,
        "confidence": "HIGH" if is_anomaly else "NORMAL",
        "band_source": band_source,
        "is_simulated": is_simulated,
        "description": (
            f"Sentinel-2 NDWI index: {ndwi:.3f}. "
            + (
                "Saturated soil / surface water anomaly detected along pipe corridor."
                if is_anomaly
                else "Normal soil moisture levels detected."
            )
        ),
    }


# ---------------------------------------------------------------------------
# Live, key-free Sentinel-2 catalog query
# ---------------------------------------------------------------------------
def _get_json(url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetch a STAC search URL as JSON. Raises on network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "AltoMare/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_scene(features: list) -> Optional[Dict[str, Any]]:
    """
    Choose the usable scene: lowest cloud cover up to MAX_CLOUD_COVER
    (newest wins ties); if every candidate is cloudier than that, fall
    back to the newest acquisition and report its cloud cover honestly.
    """
    if not features:
        return None

    def cloud_of(feature: Dict[str, Any]) -> float:
        value = feature.get("properties", {}).get("eo:cloud_cover")
        return 100.0 if value is None else float(value)

    def datetime_of(feature: Dict[str, Any]) -> str:
        return feature.get("properties", {}).get("datetime") or ""

    clear = [f for f in features if cloud_of(f) <= MAX_CLOUD_COVER]
    if clear:
        best_cloud = min(cloud_of(f) for f in clear)
        clearest = [f for f in clear if cloud_of(f) == best_cloud]
        chosen = max(clearest, key=datetime_of)      # newest of the clearest
    else:
        chosen = max(features, key=datetime_of)      # newest, cloud and all

    props = chosen.get("properties", {})
    cloud = props.get("eo:cloud_cover")
    return {
        "id": chosen.get("id"),
        "datetime": props.get("datetime"),
        "cloud_cover": round(float(cloud), 2) if cloud is not None else None,
        "platform": props.get("platform") or (props.get("instruments") or [None])[0],
    }


def fetch_latest_sentinel2_scene(
    lat: float, lng: float, days: int = CATALOG_WINDOW_DAYS
) -> Optional[Dict[str, Any]]:
    """
    Query the free Sentinel-2 L2A catalog (Element84 Earth Search, no API
    key) for scenes over a 0.02-degree box around (lat, lng).

    Returns the chosen scene dict, None when the window holds no scenes,
    or raises OSError/urllib errors on network failure -- callers degrade
    gracefully instead of fabricating a result.
    """
    start = datetime.now(timezone.utc) - timedelta(days=days)
    end = datetime.now(timezone.utc)
    bbox = (lng - 0.01, lat - 0.01, lng + 0.01, lat + 0.01)
    url = (
        f"{EARTH_SEARCH_URL}"
        f"?collections=sentinel-2-l2a"
        f"&bbox={bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}"
        f"&datetime={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&limit=20"
    )
    payload = _get_json(url)
    return _pick_scene(payload.get("features", []))
