"""Parse a user-authorized PDF locally; never download paywalled content."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from backend.scientific_tools import REGISTRY, ToolSession
from backend.paper_understanding import validate_evidence


def main():
    p = argparse.ArgumentParser()
    p.add_argument('pdf', type=Path)
    p.add_argument('--doi', required=True)
    p.add_argument('--output', type=Path, default=Path('data/paper-understanding/PU-003'))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = REGISTRY.invoke('crossref.lookup_doi', {'doi': args.doi},
                              session=ToolSession(frozenset({'literature:read'}), max_calls=1))
    (args.output/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    # Page-level text, OCR only when the PDF lacks a text layer.
    text_path = args.output/'fulltext.txt'
    subprocess.run(['pdftotext', '-layout', str(args.pdf), str(text_path)], check=True)
    pages = text_path.read_text().split('\f')
    if pages and not pages[-1].strip(): pages.pop()
    ocr = not any(x.strip() for x in pages)
    if ocr:
        subprocess.run(['pdftoppm', '-r', '170', '-png', str(args.pdf), str(args.output/'page')], check=True)
        images = sorted(args.output.glob('page-*.png'))
        def read(image):
            subprocess.run(['tesseract', str(image), str(image.with_suffix('')), '-l', 'eng'],
                           env={**os.environ, 'OMP_THREAD_LIMIT':'1'}, check=True, capture_output=True)
            return image.with_suffix('.txt').read_text()
        with ThreadPoolExecutor(max_workers=2) as pool: pages = list(pool.map(read, images))
    data = metadata['data']
    evidence = {'doi': args.doi, 'title': data['title'], 'authors': data.get('authors', []),
                'reading_status':'fulltext_reviewed',
                'fulltext_access_basis':'User supplied original PDF for this analysis; no redistribution grant.',
                'acquisition':[{'provider':'user_upload', 'sha256':hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                                'pages':len(pages), 'ocr':ocr, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
                                'limitation':'OCR and chart interpretation require visual verification'}, metadata],
                'passages':[{'id':f'p{i}', 'locator':f'PDF page {i} (OCR text)' if ocr else f'PDF page {i}',
                             'source_url':'https://doi.org/'+args.doi, 'text':t.strip()}
                            for i,t in enumerate(pages,1) if t.strip()]}
    (args.output/'evidence.json').write_text(json.dumps(validate_evidence(evidence), ensure_ascii=False, indent=2))
    print('Prepared',len(evidence['passages']),'pages; review OCR before freezing experiments.')


if __name__ == '__main__': main()
