from transform import build_ingestion_signal


def test_build_ingestion_signal_maps_gcs_finalize_payload():
    data = {
        "bucket": "shifahealthai-raw",
        "name": "sources/intake.csv",
        "contentType": "text/csv",
        "size": "1024",
        "timeCreated": "2026-09-22T10:00:00.000Z",
    }

    signal = build_ingestion_signal(data)

    assert signal == {
        "event_type": "RAW_FILE_ARRIVED",
        "bucket": "shifahealthai-raw",
        "object_name": "sources/intake.csv",
        "content_type": "text/csv",
        "size_bytes": 1024,
        "time_created": "2026-09-22T10:00:00.000Z",
    }


def test_build_ingestion_signal_handles_missing_optional_fields():
    data = {"bucket": "b", "name": "n"}

    signal = build_ingestion_signal(data)

    assert signal["content_type"] is None
    assert signal["size_bytes"] is None
    assert signal["time_created"] is None
