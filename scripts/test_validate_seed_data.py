from validate_seed_data import SEED_DIR, validate_all


def test_seed_data_has_no_errors():
    result = validate_all()
    assert result.ok, result.errors


def test_seed_data_within_mvp_volume_target():
    knowledge_rows = (SEED_DIR / "knowledge_metadata.csv").read_text(encoding="utf-8").splitlines()
    record_count = len(knowledge_rows) - 1  # minus header
    assert 30 <= record_count <= 50
