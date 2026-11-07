"""Bounded, resumable public-paper reading experiment using the original ledger."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from backend.paper_understanding import (CASE_ROOT, reading_request, retrieve_cases,
    request_hash, validate_evidence, validate_understanding, audit_understanding)
from backend.topic_advisor import ExperimentModel, artifacts, save, encode
from research_workbench.core import session_factory

LEDGER = Path('data/topic-advisor/experiments.db')
OUT = CASE_ROOT / 'runs/PU-003'


def factory():
    if not LEDGER.is_file():
        raise RuntimeError('Original ledger absent; no paid calls permitted')
    f = session_factory('sqlite:///' + str(LEDGER))
    calls = artifacts(f, 'model_call')
    audit = json.loads(Path('docs/topic-advisor/discovery-comparison.json').read_text())
    if len(calls) < 33 or not {r['id'] for r in audit['model_calls']} <= {r['id'] for r in calls}:
        raise RuntimeError('Original ledger cannot be reconciled')
    return f


def export(f):
    OUT.mkdir(parents=True, exist_ok=True)
    records = artifacts(f, 'paper_reading')
    # Public-only runner: input paper/cases reviewed before execution.
    for r in records:
        c = r['content']
        public = {**r, 'content': {k:v for k,v in c.items() if k != 'payload'}}
        public['content']['input_storage'] = 'Original local ledger: paper_reading_request/paper_reading. Full text not redistributed.'
        if c['arm'] == 'R2' and 'raw_output' in c:
            try:
                public['content']['citation_audit'] = audit_understanding(c['raw_output'], c['payload']['paper'])
            except ValueError:
                public['content']['citation_audit'] = {'status':'invalid_structure'}
        (OUT / (c['arm'] + '-' + c['request_hash'][:12] + '.json')).write_text(
            json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    calls = artifacts(f, 'model_call')
    new = calls[33:]
    def usage(rows):
        return {'attempts': len(rows), 'conservative_cny': round(sum(
            r['content'].get('charged_bound', r['content']['reservation']) for r in rows), 6),
            'known_input_tokens': sum(r['content'].get('usage', {}).get('input_tokens', 0) for r in rows),
            'known_output_tokens': sum(r['content'].get('usage', {}).get('output_tokens', 0) for r in rows),
            'unknown_usage_calls': sum(not bool(r['content'].get('usage')) for r in rows)}
    (OUT / 'usage.json').write_text(json.dumps({'round': usage(new), 'cumulative': usage(calls),
        'calls': new}, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('arm', choices=['freeze', 'R0', 'R1', 'R2', 'export'])
    p.add_argument('--evidence', default='data/paper-understanding/PU-003/evidence.json')
    p.add_argument('--retry-failed', action='store_true')
    p.add_argument('--revision', type=int, choices=[1,2], default=1)
    args = p.parse_args()
    f = factory()
    if args.arm == 'export':
        export(f); return
    evidence = validate_evidence(json.loads(Path(args.evidence).read_text()))
    evidence_hash = hashlib.sha256(encode(evidence).encode()).hexdigest()
    cases = retrieve_cases(evidence['doi'], ['scientific_problem_reframing', 'causal_boundary'])
    OUT.mkdir(parents=True, exist_ok=True)
    frozen_path = OUT / 'freeze.json'
    if args.arm == 'freeze':
        if frozen_path.exists():
            raise RuntimeError('Freeze exists; never overwrite experiment conditions')
        prompt, payload = reading_request('R0', evidence, [])
        frozen_path.write_text(json.dumps({'base_commit': subprocess.check_output(
            ['git','rev-parse','HEAD'], text=True).strip(), 'system': prompt,
            'payload_hash': hashlib.sha256(encode(payload).encode()).hexdigest(),
            'evidence_hash': evidence_hash, 'case_hashes': [c['card_sha256'] for c in cases],
            'model': 'deepseek-flash', 'max_tokens': 3500,
            'protocol': 'One public development paper; same source evidence; no target answer card; no novelty certification.'},
            ensure_ascii=False, indent=2) + '\n')
        print('Frozen', evidence_hash); return
    frozen = json.loads(frozen_path.read_text())
    if frozen['evidence_hash'] != evidence_hash or frozen['case_hashes'] != [c['card_sha256'] for c in cases]:
        raise RuntimeError('Frozen evidence/exemplars changed')
    system, payload = reading_request(args.arm, evidence, cases, revision=args.revision)
    if args.arm == 'R0':
        system = frozen['system']
        if hashlib.sha256(encode(payload).encode()).hexdigest() != frozen['payload_hash']:
            raise RuntimeError('Frozen baseline input changed')
    digest = request_hash(system, payload)
    previous = [r for r in artifacts(f, 'paper_reading') if r['content']['request_hash'] == digest]
    if previous and (previous[-1]['content']['status'] == 'completed' or not args.retry_failed):
        print('Existing checkpoint; no new call'); export(f); return
    if len(artifacts(f, 'model_call')) >= 40:
        raise RuntimeError('This reading round is limited to seven additional attempts')
    record = {'arm': args.arm, 'revision': args.revision, 'request_hash': digest, 'system': system, 'payload': payload,
              'evidence_hash': evidence_hash, 'model': frozen['model'], 'max_tokens': frozen['max_tokens'],
              'module_sha256': hashlib.sha256(Path('backend/paper_understanding.py').read_bytes()).hexdigest(),
              'status': 'started'}
    # Persist exact request before starting; crashes retain both request and gateway reservation.
    save(f, 'paper_reading_request', record)
    before = len(artifacts(f, 'model_call'))
    try:
        raw = ExperimentModel(f, 'data/topic-advisor/experiment.lock').call(
            system, payload, model=frozen['model'], max_tokens=frozen['max_tokens'])
        record['raw_output'] = raw
        if args.arm == 'R2':
            record['validated_output'] = validate_understanding(raw, evidence)
        else:
            papers = raw.get('papers', [])
            if len(papers) != 1 or papers[0].get('paper_id') != evidence['doi']:
                raise ValueError('Incomplete legacy reading')
            if not all(isinstance(papers[0].get(k), str) and papers[0][k] for k in
                       ('problem', 'method', 'limitations', 'evidence_level')):
                raise ValueError('Invalid legacy reading')
            record['validated_output'] = raw
        record['status'] = 'completed'
    except Exception as exc:
        record.update(status='failed', error=type(exc).__name__, detail=str(exc)[:350])
    if args.arm == 'R2' and 'raw_output' in record:
        try:
            record['citation_audit'] = audit_understanding(record['raw_output'], evidence)
        except ValueError:
            record['citation_audit'] = {'status':'invalid_structure', 'entailment_verified':False}
    record['new_calls'] = len(artifacts(f, 'model_call')) - before
    save(f, 'paper_reading', record)
    export(f)
    print(encode({'arm': args.arm, 'status': record['status'], 'new_calls': record['new_calls'],
                  'error': record.get('detail'), 'output': record.get('raw_output')}), flush=True)


if __name__ == '__main__':
    main()
