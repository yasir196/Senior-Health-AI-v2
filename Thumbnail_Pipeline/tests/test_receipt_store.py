import pytest
from Thumbnail_Pipeline.db import ReceiptStore
from Thumbnail_Pipeline.execution import evaluate_idempotency_gate

FP="a"*64

def test_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store=ReceiptStore()
    receipt={"fingerprint":FP,"backend_executed":True,"render_status":"rendered","finalized":False}
    path=store.save(receipt)
    assert path.as_posix().startswith("Thumbnail_Pipeline/db/receipts/")
    assert store.load(FP)==receipt

def test_store_creates_no_v2_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store=ReceiptStore(); store.save({"fingerprint":FP})
    assert not (tmp_path/"config.json").exists()
    assert not (tmp_path/"Analytics").exists()

def test_store_rejects_root_outside_isolated_folder():
    with pytest.raises(ValueError):
        ReceiptStore("Analytics/receipts")

def test_store_rejects_invalid_fingerprint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        ReceiptStore().save({"fingerprint":"bad"})

def test_persisted_receipt_drives_idempotency_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store=ReceiptStore()
    store.save({"fingerprint":FP,"backend_executed":True,"render_status":"rendered","finalized":True})
    gate=evaluate_idempotency_gate(FP,store.receipts_for(FP))
    assert gate["duplicate_execution_blocked"] is True
    assert gate["reason"]=="prior_finalized_execution"

def test_missing_receipt_returns_empty_collection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ReceiptStore().receipts_for(FP)==[]
