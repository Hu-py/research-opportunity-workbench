from copy import deepcopy
import pytest
from backend.paper_understanding import (load_cases, retrieve_cases, validate_evidence,
    validate_understanding, MODULES, reading_request, audit_understanding)

EVIDENCE = {'doi':'10.1234/test','title':'Source comparison','authors':['A'],
            'reading_status':'abstract_reviewed','acquisition':[],
            'passages':[{'id':'a','locator':'Abstract','source_url':'https://example.org',
                         'text':'Recorded events differ between sources.'}]}


def output():
    claim={'text':'Records differ, not necessarily behavior.','status':'analyst_inference',
           'references':[{'passage_id':'a','quote':'Recorded events differ'}],
           'uncertainty':'Observation process unverified'}
    return {'paper_doi':EVIDENCE['doi'],'reading_status':'abstract_reviewed',
            'modules':{k:[deepcopy(claim)] for k in MODULES},'remaining_questions':[]}


def test_exemplars_keep_confirmation_and_target_exclusion():
    cases=load_cases()
    assert [c['card']['case_id'] for c in cases]==['PU-001','PU-002']
    assert cases[0]['card']['human_feedback']['status']=='priority_confirmed'
    assert cases[1]['card']['human_feedback']['status']=='pending_case_specific_review'
    selected=retrieve_cases('10.3390/ijgi10110740',['scientific_problem_reframing','causal_boundary'])
    assert [c['card']['case_id'] for c in selected]==['PU-002']


def test_unknown_quotes_and_reading_inflation_fail():
    raw=output();assert validate_understanding(raw,EVIDENCE)
    raw['modules']['prior_question'][0]['references'][0]['quote']='invented'
    with pytest.raises(ValueError,match='Quote'):validate_understanding(raw,EVIDENCE)
    raw=output();raw['reading_status']='fulltext_reviewed'
    with pytest.raises(ValueError,match='inflation'):validate_understanding(raw,EVIDENCE)


def test_source_claim_requires_evidence_and_all_modules():
    raw=output();raw['modules']['prior_question'][0].update(status='source_supported',references=[])
    with pytest.raises(ValueError,match='Unsupported'):validate_understanding(raw,EVIDENCE)
    raw=output();raw['modules'].pop('transfer')
    with pytest.raises(ValueError,match='Eight'):validate_understanding(raw,EVIDENCE)


def test_fulltext_needs_access_and_verification_is_separate():
    e={**EVIDENCE,'reading_status':'fulltext_reviewed'}
    with pytest.raises(ValueError,match='access'):validate_evidence(e)
    e['fulltext_access_basis']='user supplied';assert validate_evidence(e)
    e['reading_status']='evidence_verified'
    with pytest.raises(ValueError,match='verification'):validate_evidence(e)


def test_r0_r1_share_paper_and_r0_excludes_examples():
    cases=load_cases();s0,p0=reading_request('R0',EVIDENCE,cases)
    s1,p1=reading_request('R1',EVIDENCE,cases)
    assert p0['papers']==p1['papers'] and 'reasoning_exemplars' not in p0
    assert s1.startswith(s0)
    e={**EVIDENCE,'reading_status':'fulltext_reviewed','fulltext_access_basis':'user supplied'}
    s,p=reading_request('R0',e,[])
    assert 'fulltext' in p['papers'][0] and 'abstract' not in p['papers'][0]


def test_audit_locates_all_errors_without_rewriting_source():
    raw=output();raw['modules']['prior_question'][0]['references'][0]['passage_id']='wrong'
    before=deepcopy(raw)
    audit=audit_understanding(raw,EVIDENCE)
    bad=[x for x in audit['quote_checks'] if not x['exact_location_match']]
    assert len(bad)==1 and bad[0]['matching_pages']==['a']
    assert raw==before and audit['entailment_verified'] is False
