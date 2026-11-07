"""One paid call maximum; evaluate coverage on the frozen development case only."""
from backend.ai_lab import PROMPTS, _validated
from backend.topic_advisor import ExperimentModel, artifacts, save, encode
from research_workbench.core import session_factory


def main():
    factory = session_factory('sqlite:///data/topic-advisor/experiments.db')
    context = next(x['content'] for x in artifacts(factory, 'context') if x['content']['case'] == 'heat')
    model = ExperimentModel(factory, 'data/topic-advisor/experiment.lock')
    before = len(artifacts(factory, 'model_call'))
    report = {'case': 'heat', 'hypothesis': 'stage-specific cardinality prevents evidence omission',
              'expected_papers': len(context['papers']), 'baseline_constraint': 'all lists <=3',
              'baseline_maximum_coverage_if_obeyed': 3 / len(context['papers'])}
    try:
        raw = model.call(PROMPTS['reader'], context)
        parsed = _validated('reader', raw, context)
        report.update(status='passed', observed_papers=len(parsed['papers']), result=parsed)
    except Exception as exc:
        report.update(status='failed', error=type(exc).__name__,
                      reason=str(exc)[:200] if type(exc).__name__ in ('ModelCallError', 'ValueError') else '')
    report['new_requests'] = len(artifacts(factory, 'model_call')) - before
    save(factory, 'reader_probe', report)
    print(encode(report))


if __name__ == '__main__':
    main()
