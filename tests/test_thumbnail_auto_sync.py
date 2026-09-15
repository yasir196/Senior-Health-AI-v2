from pathlib import Path

import thumbnail_learning_sync as tls


def test_auto_sync_runs_full_pipeline_best_effort(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(tls, 'refresh_channel_thumbnails', lambda db: calls.append('refresh') or {'checked': 2, 'downloaded': 1, 'unchanged': 1})
    monkeypatch.setattr(tls, 'analyze_pending_thumbnails', lambda db, model=None: calls.append(('analyze', model)) or {'analyzed': 1})
    monkeypatch.setattr(tls, 'join_all_thumbnail_ctr_evidence', lambda db: calls.append('join') or {'joined': 2})
    monkeypatch.setattr(tls, 'build_thumbnail_packaging_comparisons', lambda db: calls.append('compare') or {'associations': 3})
    monkeypatch.setattr(tls, 'sync_packaging_rule_candidates', lambda db: calls.append('candidates') or {'created': 1})
    monkeypatch.setattr(tls, 'write_active_packaging_rules_file', lambda db, out: calls.append(('write', out)) or {'active': 1})

    out = tls.auto_sync_thumbnail_learning(tmp_path/'a.db', tmp_path/'rules.md', model='vision-test')
    assert out['thumbnails']['downloaded'] == 1
    assert out['analysis']['analyzed'] == 1
    assert out['ctr_join']['joined'] == 2
    assert out['candidates']['created'] == 1
    assert out['warnings'] == []
    assert calls[0] == 'refresh'
    assert calls[1] == ('analyze', 'vision-test')
    assert calls[-1] == ('write', tmp_path/'rules.md')


def test_auto_sync_does_not_abort_when_comparison_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(tls, 'refresh_channel_thumbnails', lambda db: {'checked': 1})
    monkeypatch.setattr(tls, 'analyze_pending_thumbnails', lambda db, model=None: {'analyzed': 0})
    monkeypatch.setattr(tls, 'join_all_thumbnail_ctr_evidence', lambda db: {'joined': 0})
    monkeypatch.setattr(tls, 'build_thumbnail_packaging_comparisons', lambda db: (_ for _ in ()).throw(RuntimeError('needs 2 videos')))
    monkeypatch.setattr(tls, 'sync_packaging_rule_candidates', lambda db: {'created': 0})
    monkeypatch.setattr(tls, 'write_active_packaging_rules_file', lambda db, out: {'active': 0})
    out = tls.auto_sync_thumbnail_learning(tmp_path/'a.db', tmp_path/'rules.md')
    assert out['candidates']['created'] == 0
    assert any('needs 2 videos' in x for x in out['warnings'])
