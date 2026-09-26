"""
Sentinel-2 NDWI tests (roadmap 5.4, Hours 19-22).

Covers:
- the NDWI formula and the corridor analyzer's honest labelling
  (demo bands must always carry is_simulated=True)
- zone centroids: all 12 demo zones, inside the Lucknow bbox
- scene selection: clearest in window, newest wins ties, all-cloudy
  fallback, empty window
- the endpoint: 404s, graceful CATALOG_UNAVAILABLE degradation, no
  fabricated scores, real NDWI computation when reflectance is supplied

The catalog fetch is monkeypatched in endpoint tests -- no live network
in the suite. One manual live smoke run is done outside pytest.
"""

import urllib.error

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.data.db_schema import Zone, BillingRecord
from backend.app.engines import ml_billing_anomaly as mba
from backend.app.engines import satellite
from backend.app.main import app

client = TestClient(app)   # no lifespan: get_db serves the live DB (read-only here)


@pytest.fixture(autouse=True)
def isolate_detector_state():
    """Endpoint tests may train the detector; restore global state after."""
    saved = mba._detector
    yield
    mba._detector = saved


@pytest.fixture()
def trained_detector():
    """Train on live billing exactly as app startup does, so the endpoint's
    ML path (and its counts) match what the running server reports."""
    db = SessionLocal()
    try:
        rows = db.query(BillingRecord).all()
    finally:
        db.close()
    frame = pd.DataFrame([{
        "billed_litres": r.billed_litres,
        "benchmark_litres": r.benchmark_litres,
        "household_size": r.household_size or 4,
    } for r in rows])
    mba.train_detector(frame)


# ---------------------------------------------------------------------------
# Formula
# ---------------------------------------------------------------------------
def test_ndwi_formula_known_values():
    assert satellite.calculate_ndwi(0.42, 0.18) == pytest.approx(0.4, abs=1e-9)
    assert satellite.calculate_ndwi(0.8, 0.2) == pytest.approx(0.6, abs=1e-9)
    assert satellite.calculate_ndwi(0.3, 0.3) == pytest.approx(0.0, abs=1e-9)
    assert satellite.calculate_ndwi(0.2, 0.8) == pytest.approx(-0.6, abs=1e-9)


def test_ndwi_formula_zero_division_returns_zero():
    assert satellite.calculate_ndwi(0.0, 0.0) == 0.0


def test_ndwi_formula_is_antisymmetric():
    a, b = 0.37, 0.11
    assert satellite.calculate_ndwi(a, b) == pytest.approx(
        -satellite.calculate_ndwi(b, a), abs=1e-12
    )


def test_thresholds_are_documented():
    assert satellite.SUGGESTION_THRESHOLD < satellite.ANOMALY_THRESHOLD
    assert 0.0 < satellite.SUGGESTION_THRESHOLD < 1.0
    assert 0.0 < satellite.ANOMALY_THRESHOLD < 1.0


# ---------------------------------------------------------------------------
# Corridor analyzer: honest labelling
# ---------------------------------------------------------------------------
def test_corridor_defaults_are_labelled_simulated():
    result = satellite.analyze_pipe_corridor("zone_6", 26.869, 80.942)
    assert result["band_source"] == "calibrated_demo"
    assert result["is_simulated"] is True
    assert result["ndwi_score"] == pytest.approx(0.4, abs=1e-4)
    assert result["surface_moisture_anomaly"] is True   # 0.4 > 0.35
    assert result["confidence"] == "HIGH"


def test_corridor_with_real_bands_is_not_simulated():
    result = satellite.analyze_pipe_corridor(
        "zone_8", 26.885, 81.000, green_band_val=0.2, nir_band_val=0.3
    )
    assert result["band_source"] == "provided_reflectance"
    assert result["is_simulated"] is False
    assert result["surface_moisture_anomaly"] is False  # ndwi = -0.2
    assert result["confidence"] == "NORMAL"


def test_corridor_marginal_band_below_anomaly_threshold():
    # ndwi = (0.30 - 0.20) / 0.50 = 0.20 -> suggestion range, not anomaly
    result = satellite.analyze_pipe_corridor(
        "zone_1", 26.845, 80.942, green_band_val=0.30, nir_band_val=0.20
    )
    assert result["ndwi_score"] == pytest.approx(0.2, abs=1e-4)
    assert result["surface_moisture_anomaly"] is False


# ---------------------------------------------------------------------------
# Centroids
# ---------------------------------------------------------------------------
def test_all_12_demo_zones_have_lucknow_centroids():
    demo_zones = {f"zone_{i}" for i in range(1, 13)}
    assert demo_zones <= set(satellite.LUCKNOW_ZONE_CENTROIDS)

    for zid, (lat, lng) in satellite.LUCKNOW_ZONE_CENTROIDS.items():
        assert 26.5 <= lat <= 27.2, f"{zid} lat {lat} outside Lucknow"
        assert 80.5 <= lng <= 81.3, f"{zid} lng {lng} outside Lucknow"


# ---------------------------------------------------------------------------
# Scene selection
# ---------------------------------------------------------------------------
def _feature(cloud, when, fid="scene-1"):
    return {"id": fid, "properties": {"datetime": when, "eo:cloud_cover": cloud}}


def test_pick_scene_prefers_clearest():
    features = [
        _feature(80.0, "2026-09-24T05:00:00Z", "cloudy-new"),
        _feature(5.0, "2026-09-14T05:00:00Z", "clear-old"),
        _feature(12.0, "2026-09-20T05:00:00Z", "ok"),
    ]
    scene = satellite._pick_scene(features)
    assert scene["id"] == "clear-old"
    assert scene["cloud_cover"] == 5.0


def test_pick_scene_newest_wins_cloud_tie():
    features = [
        _feature(10.0, "2026-09-10T05:00:00Z", "older"),
        _feature(10.0, "2026-09-22T05:00:00Z", "newer"),
    ]
    assert satellite._pick_scene(features)["id"] == "newer"


def test_pick_scene_all_cloudy_falls_back_to_newest():
    features = [
        _feature(95.0, "2026-09-08T05:00:00Z", "old-broc"),
        _feature(88.0, "2026-09-25T05:00:00Z", "new-broc"),
    ]
    scene = satellite._pick_scene(features)
    assert scene["id"] == "new-broc"
    assert scene["cloud_cover"] == 88.0     # reported honestly


def test_pick_scene_empty_window_returns_none():
    assert satellite._pick_scene([]) is None


# ---------------------------------------------------------------------------
# Catalog fetch (network mocked at _get_json)
# ---------------------------------------------------------------------------
def test_fetch_builds_stac_query_and_parses_scene(monkeypatch):
    captured = {}

    def fake_get_json(url, timeout=6.0):
        captured["url"] = url
        return {"features": [
            _feature(8.0, "2026-09-21T05:10:22Z", "S2B_44RQA_20260921"),
            _feature(40.0, "2026-09-11T05:10:22Z", "S2A_44RQA_20260911"),
        ]}

    monkeypatch.setattr(satellite, "_get_json", fake_get_json)
    scene = satellite.fetch_latest_sentinel2_scene(26.869, 80.942, days=30)

    assert scene["id"] == "S2B_44RQA_20260921"
    assert scene["cloud_cover"] == 8.0
    assert "collections=sentinel-2-l2a" in captured["url"]
    assert "bbox=" in captured["url"]
    assert "datetime=" in captured["url"]
    # bbox must be a 0.02-degree box around the centroid (lng, lat order)
    bbox = captured["url"].split("bbox=")[1].split("&")[0]
    w, s, e, n = [float(v) for v in bbox.split(",")]
    assert s < 26.869 < n and w < 80.942 < e


def test_fetch_propagates_network_failure(monkeypatch):
    def boom(url, timeout=6.0):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(satellite, "_get_json", boom)
    with pytest.raises(urllib.error.URLError):
        satellite.fetch_latest_sentinel2_scene(26.869, 80.942)


# ---------------------------------------------------------------------------
# Endpoint (live DB reads; catalog fetch mocked)
# ---------------------------------------------------------------------------
def test_ndwi_endpoint_unknown_zone_404():
    assert client.get("/data/satellite/ndwi/zone_nope").status_code == 404


def test_ndwi_endpoint_ok_path_no_fabricated_score(monkeypatch, trained_detector):
    monkeypatch.setattr(
        satellite, "fetch_latest_sentinel2_scene",
        lambda lat, lng, days=30: {
            "id": "S2B_44RQA_20260921", "datetime": "2026-09-21T05:10:22Z",
            "cloud_cover": 8.0, "platform": "sentinel-2b",
        },
    )
    res = client.get("/data/satellite/ndwi/zone_2")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "OK"
    assert data["scene"]["id"] == "S2B_44RQA_20260921"
    assert data["is_simulated"] is False
    assert data["ndwi_score"] is None
    assert data["ndwi_status"] == "bands_not_configured"
    assert data["surface_moisture_anomaly"] is None
    assert "invented" in data["message"]

    # ground evidence: zone_2 is a seeded theft zone (9 flagged records
    # under the live Isolation Forest, same as the BillingAudit screen)
    assert data["billing_flagged_records"] == 9
    assert data["billing_detection_method"] == "isolation_forest"
    assert data["zone_flagged"] is True
    assert "billing_anomaly" in data["flag_sources"]
    assert data["coordinates"]["lat"] == pytest.approx(26.890)
    assert "Sentinel-2 L2A" in data["data_source"]


def test_ndwi_endpoint_computes_when_reflectance_supplied(monkeypatch):
    monkeypatch.setattr(
        satellite, "fetch_latest_sentinel2_scene",
        lambda lat, lng, days=30: None,      # empty window
    )
    res = client.get("/data/satellite/ndwi/zone_8?green=0.5&nir=0.2")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "NO_SCENE"
    assert data["ndwi_status"] == "computed"
    assert data["ndwi_score"] == pytest.approx((0.5 - 0.2) / (0.5 + 0.2), abs=1e-4)
    assert data["anomaly_threshold"] == satellite.ANOMALY_THRESHOLD
    assert data["surface_moisture_anomaly"] is True    # 0.4286 > 0.35
    assert data["billing_flagged_records"] == 0        # clean reference zone


def test_ndwi_endpoint_degrades_gracefully_offline(monkeypatch):
    def offline(lat, lng, days=30):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(satellite, "fetch_latest_sentinel2_scene", offline)
    res = client.get("/data/satellite/ndwi/zone_6")
    assert res.status_code == 200                 # graceful, not a 500
    data = res.json()
    assert data["status"] == "CATALOG_UNAVAILABLE"
    assert data["scene"] is None
    assert data["ndwi_score"] is None
    assert "failed" in data["message"]
    assert data["zone_flagged"] in (True, False)  # ground evidence still served


def test_ndwi_endpoint_zone_without_centroid(monkeypatch):
    """Zones outside the demo set (agent fixtures) degrade to NO_COORDINATES."""
    db = SessionLocal()
    try:
        db.add(Zone(id="ZONE-NO-CENTROID", name="No Centroid", tariff_rate=0.005))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        satellite, "fetch_latest_sentinel2_scene",
        lambda lat, lng, days=30: pytest.fail("must not query without centroid"),
    )
    try:
        res = client.get("/data/satellite/ndwi/ZONE-NO-CENTROID")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "NO_COORDINATES"
        assert data["scene"] is None
        assert data["coordinates"] is None
    finally:
        # never leave a fixture zone in the shared demo DB
        db = SessionLocal()
        try:
            db.query(Zone).filter(Zone.id == "ZONE-NO-CENTROID").delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()
