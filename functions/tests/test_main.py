import json
import os
from dataclasses import dataclass

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("INGESTION_SIGNAL_TOPIC", "test-topic")

import main  # noqa: E402


@dataclass
class _FakeCloudEvent:
    data: dict


class _FakeFuture:
    def result(self):
        return "fake-message-id"


class _FakePublisher:
    def __init__(self):
        self.published = []

    def topic_path(self, project_id, topic_id):
        return f"projects/{project_id}/topics/{topic_id}"

    def publish(self, topic_path, data):
        self.published.append((topic_path, json.loads(data.decode("utf-8"))))
        return _FakeFuture()


def test_on_raw_file_arrival_publishes_ingestion_signal(monkeypatch):
    fake_publisher = _FakePublisher()
    monkeypatch.setattr(main, "_get_publisher_client", lambda: fake_publisher)

    event = _FakeCloudEvent(
        data={
            "bucket": "shifahealthai-raw",
            "name": "sources/x.csv",
            "contentType": "text/csv",
            "size": "10",
            "timeCreated": "2026-09-22T00:00:00Z",
        }
    )

    main.on_raw_file_arrival(event)

    assert len(fake_publisher.published) == 1
    topic_path, payload = fake_publisher.published[0]
    assert topic_path == "projects/test-project/topics/test-topic"
    assert payload == {
        "event_type": "RAW_FILE_ARRIVED",
        "bucket": "shifahealthai-raw",
        "object_name": "sources/x.csv",
        "content_type": "text/csv",
        "size_bytes": 10,
        "time_created": "2026-09-22T00:00:00Z",
    }
