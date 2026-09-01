import pytest
from scripts.run_t080_value_target_semantics_audit import _stable, audit

def test_missing_and_unavailable_are_distinct():
    assert _stable(None, "x")["status"] == "missing"

def test_incomplete_identity_fails_closed():
    with pytest.raises(RuntimeError): _stable({"stable_id":"x"}, "teacher")

def test_checkpoint_loader_mismatch_fails_closed(tmp_path):
    p=tmp_path/"x"; p.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="checkpoint SHA"):
        audit(p,p,lambda _: ({},{}))
