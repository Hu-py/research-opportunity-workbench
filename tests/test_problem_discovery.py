from copy import deepcopy
import pytest
from backend.topic_advisor import advise, validate_problems


CONTEXT={'papers':[{'id':'p1','title':'Observed canopy cooling','abstract':'Air and surface temperature are different quantities.'}], 'datasets':[]}
PROBLEM={'id':'problem1','question':'Which process explains the discrepancy?',
         'importance':'Interventions differ by mechanism','knowledge_increment':'Distinguish two explanations',
         'evidence_status':'inferred_gap','source_refs':[{'paper_id':'p1','quote':'Air and surface temperature are different quantities.'}],
         'competing_explanations':[{'explanation':'measurement mismatch','prediction':'difference shrinks with matching'},
                                  {'explanation':'physical heterogeneity','prediction':'difference persists after matching'}],
         'distinguishing_observation':'Paired contemporaneous measurements'}
IDEA={'problem_id':'problem1','title':'Distinguish mechanisms','question':'Which mechanism?',
      'method':'Paired observation','why_now':'Unresolved measurement problem','paper_ids':['p1'],
      'dataset_ids':[],'baselines':['Unpaired analysis'],'minimal_experiment':'Compare paired outcomes','risks':['Access unknown']}


class Model:
    def __init__(self, verdict='reject', unresolved=None, candidate=None):
        self.calls=[]
        self.outputs=[{'problems':[deepcopy(PROBLEM)]},{'ideas':[deepcopy(candidate or IDEA)]},
                      {'reviews':[{'title':IDEA['title'],'verdict':verdict,'reason':'Measurement mismatch remains',
                                   'unresolved':['construct mismatch'] if unresolved is None else unresolved}]}]
    def call(self,system,payload,**kwargs):
        self.calls.append(payload)
        return self.outputs.pop(0)


def test_critic_veto_cannot_be_reintroduced_by_final_generation():
    model=Model()
    result=advise(model,CONTEXT)
    assert result['ideas']==[]
    assert result['trace']['withheld'][0]['problem_id']=='problem1'
    assert len(model.calls)==3
    assert model.calls[1]['problems'][0]['source_refs']==PROBLEM['source_refs']


def test_recommend_with_unresolved_issue_is_withheld():
    assert advise(Model('recommend'),CONTEXT)['ideas']==[]
    assert len(advise(Model('recommend',[]),CONTEXT)['ideas'])==1


def test_fabricated_source_and_duplicate_explanations_rejected():
    problem=deepcopy(PROBLEM);problem['source_refs'][0]['quote']='fabricated result'
    with pytest.raises(ValueError,match='quote'):validate_problems({'problems':[problem]},CONTEXT)
    problem=deepcopy(PROBLEM);problem['competing_explanations'][1]=problem['competing_explanations'][0]
    with pytest.raises(ValueError,match='Duplicate'):validate_problems({'problems':[problem]},CONTEXT)


def test_unlinked_candidate_cannot_reach_critic():
    candidate={**IDEA,'problem_id':'invented'};model=Model(candidate=candidate)
    with pytest.raises(ValueError,match='validated problem'):advise(model,CONTEXT)
    assert len(model.calls)==2


def test_no_grounded_problem_means_no_generation():
    model=Model();model.outputs=[{'problems':[]}]
    assert advise(model,CONTEXT)['ideas']==[]
    assert len(model.calls)==1


def test_single_envelope_provenance_is_unambiguous():
    model=Model('recommend',[])
    del model.outputs[1]['ideas'][0]['problem_id']
    model.outputs[1]['problem_id']='problem1'
    assert advise(model,CONTEXT)['ideas'][0]['problem_id']=='problem1'
