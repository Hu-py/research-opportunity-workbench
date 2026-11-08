"""Offline regression tests: Radar B GitHub collector must not need credentials to test."""
import unittest
from xml.etree import ElementTree as ET
from unittest.mock import patch

from scripts import radar_b_collector as rb


class RadarBCollectorTest(unittest.TestCase):
    def test_extract_abstract_position_and_excerpt(self):
        self.assertEqual(rb.extract_abstract({"new": [2], "A": [0], "useful": [1]}),
                         "A useful new")
        self.assertIsNone(rb.extract_abstract(None))
        self.assertLessEqual(len(rb.extract_abstract({"word": list(range(500))})), 651)

    def test_non_research_and_retraction_are_excluded(self):
        doc = {
            "id": "https://openalex.org/W123",
            "title": "A 2026 New Method for Scientific Testing",
            "type": "article",
            "publication_date": "2026-11-04",
            "primary_topic": {"id": "https://openalex.org/T123", "display_name": "ML"},
            "authorships": [],
            "abstract_inverted_index": {"A": [0], "test": [1]},
        }
        paper = rb.normalize_openalex(doc, "ICML", "2026-09-01", {"editorial"})
        self.assertEqual(paper["primary_topic_id"], "T123")
        self.assertEqual(paper["evidence_level"], "metadata_with_abstract_excerpt")
        self.assertEqual(paper["abstract_excerpt"], "A test")
        self.assertIsNone(rb.normalize_openalex(dict(doc, type="editorial"),
                                                "ICML", "2026-09-01", {"editorial"}))
        self.assertIsNone(rb.normalize_openalex(dict(doc, is_retracted=True),
                                                "ICML", "2026-09-01", {"editorial"}))
        self.assertIsNone(rb.normalize_openalex(dict(doc, publication_date="2026-01-01"),
                                                "ICML", "2026-09-01", set()))

    def test_cross_source_title_dedup_preserves_provenance(self):
        oa = {
            "title": "A New Structured Scientific Method",
            "doi": None,
            "openalex_id": "https://openalex.org/W123",
            "arxiv_id": None,
            "publication_date": "2026-10-10",
            "abstract_excerpt": None,
            "provenance": ["openalex"],
        }
        ax = {
            "title": "A new structured scientific method",
            "doi": None,
            "openalex_id": None,
            "arxiv_id": "2610.00123",
            "publication_date": "2026-10-09",
            "abstract_excerpt": "Method innovation and validity.",
            "provenance": ["arxiv"],
        }
        merged = rb.merge_papers([oa], [ax], 40)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provenance"], ["arxiv", "openalex"])
        self.assertEqual(merged[0]["arxiv_id"], "2610.00123")
        self.assertTrue(merged[0]["abstract_available"])

    def test_round_robin_prevents_one_venue_from_filling_budget(self):
        self.assertEqual(rb.round_robin([[1, 2, 3], [10, 20], [100]], 5),
                         [1, 10, 100, 2, 20])

    def test_arxiv_atom_extracts_preprint_evidence(self):
        atom = """<feed xmlns="http://www.w3.org/2005/Atom"
                        xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry><id>https://arxiv.org/abs/2610.12345</id>
          <title> A novel method </title><published>2026-10-04T01:00:00Z</published>
          <summary>Method and test. Code https://github.com/example/project</summary>
          <author><name>Researcher One</name></author>
          <link title="pdf" href="https://arxiv.org/pdf/2610.12345"/>
          <arxiv:primary_category term="cs.LG"/>
          <arxiv:doi>10.5555/example</arxiv:doi></entry></feed>"""
        root = ET.fromstring(atom)
        group = {"categories": ["cs.AI", "cs.LG"], "max_results": 10}
        with patch.object(rb, "http_payload", return_value=root):
            works = rb.arxiv_recent(group, "2026-09-01")
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0]["arxiv_id"], "2610.12345")
        self.assertEqual(works[0]["method_category"], "cs.LG")
        self.assertEqual(works[0]["publication_status"],
                         "preprint; not peer review verified")
        self.assertEqual(works[0]["code_url"], "https://github.com/example/project")
        with patch.object(rb, "http_payload", return_value=root):
            self.assertEqual(rb.arxiv_recent(group, "2026-11-01"), [])


if __name__ == "__main__":
    unittest.main()
