"""Stage cardinality must not be overwritten by transport-level heuristics."""
from backend.topic_advisor import ExperimentModel, ADVISOR
from backend.ai_lab import PROMPTS, _validated
from research_workbench.core import session_factory


def test_reader_keeps_five_real_papers_and_exact_prompt(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    fixture = json.loads(Path('docs/topic-advisor/pilot-public-evidence.json').read_text())
    context = next(x['content'] for x in fixture['context'] if x['content']['case'] == 'heat')
    assert len(context['papers']) == 5
    captured = []
    def response(key, model, system, payload, **kwargs):
        captured.append(system)
        return {'papers': [{'paper_id': p['id'], 'problem': 'test problem',
                            'method': 'test method', 'limitations': 'not assessed',
                            'evidence_level': 'metadata'} for p in payload['papers']]}, {
                                'input_tokens': 100, 'output_tokens': 100}
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only')
    monkeypatch.setattr('backend.topic_advisor.request_json', response)
    factory = session_factory('sqlite:///' + str(tmp_path / 'test.db'))
    model = ExperimentModel(factory, str(tmp_path / 'lock'))
    parsed = _validated('reader', model.call(PROMPTS['reader'], context), context)
    assert len(parsed['papers']) == 5
    assert captured == [PROMPTS['reader']]
    assert 'ideas最多一个' in ADVISOR


def test_reader_still_rejects_three_of_five():
    import pytest
    context = {'papers': [{'id': str(i), 'abstract': ''} for i in range(5)]}
    raw = {'papers': [{'paper_id': str(i), 'problem': 'p', 'method': 'm',
                       'limitations': 'l'} for i in range(3)]}
    with pytest.raises(ValueError, match='遗漏'):
        _validated('reader', raw, context)
