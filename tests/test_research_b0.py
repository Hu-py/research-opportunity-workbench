import pytest
from scripts.research_b0 import run_case, validate, METRICS
from research_workbench.core import session_factory


def test_checkpoint_skips_completed_provider_calls(tmp_path):
    factory=session_factory('sqlite:///'+str(tmp_path/'db.sqlite'))
    class Model:
        calls=0
        def call(self,*args,**kwargs):
            self.calls+=1
            return {'reviews':[{'label':'P0','reason':'Evidence is insufficient',**{k:1 for k in METRICS}}],
                    'preferred_label':'abstain','proposed_question':'Which mechanism explains the observation?',
                    'verification_needed':['measure outcome']}
    m=Model();p={'candidates':[{'label':'P0'}]};manifest={'reference_label':'P0'}
    assert run_case(factory,m,p,manifest)['status']=='completed'
    assert run_case(factory,m,p,manifest)['status']=='checkpoint_reused'
    assert m.calls==1


def test_failure_is_retained_and_not_retried(tmp_path):
    factory=session_factory('sqlite:///'+str(tmp_path/'db.sqlite'))
    class Model:
        calls=0
        def call(self,*args,**kwargs):
            self.calls+=1
            raise TimeoutError()
    m=Model();p={'candidates':[]}
    assert run_case(factory,m,p,{})['status']=='failed'
    assert run_case(factory,m,p,{})['previous_status']=='failed'
    assert m.calls==1


def test_missing_reviews_are_not_scored():
    with pytest.raises(ValueError,match='coverage'):
        validate({'reviews':[]},['P0'])


def test_interrupted_case_is_not_silently_restarted(tmp_path):
    from backend.topic_advisor import save
    from scripts.research_b0 import digest, PROMPT
    factory=session_factory('sqlite:///'+str(tmp_path/'db.sqlite'))
    payload={'candidates':[]}
    config={'protocol':'b0-v1','prompt':PROMPT,'model':'deepseek-v4-pro','max_tokens':2000}
    key=digest({'input':payload,'config':config})
    save(factory,'b0_attempt',{'key':key,'status':'started'})
    class NeverCall:
        def call(self,*args,**kwargs):
            raise AssertionError('An uncertain interrupted request must not auto-retry')
    assert run_case(factory,NeverCall(),payload,{})['previous_status']=='started'
