from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "mapping" / "tei_to_leco.yaml"

# Import the converter exactly as it is used from scripts/.
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from tei_to_rdf import (  # noqa: E402
    TEILeCOConverter, convert_one
)


def test_real_corpus_path_if_present_is_accepted(tmp_path):
    real_doc = ROOT / "data" / "documents" / "cab-001-002"
    if not (real_doc / "tei.xml").exists():
        pytest.skip("Local corpus is not bundled with this update package")
    converter = TEILeCOConverter(MAPPING)
    report = convert_one(
        converter, real_doc,
        tmp_path / "cab-001-002.ttl", False,
        ROOT / "ontology" / "LeCO.ttl",
        ROOT / "shapes" / "LeCO_shapes.ttl",
        tmp_path / "report.ttl",
        ROOT,
    )
    assert report.triples > 0
    assert report.mode in {"mapping-profile", "legacy-inline"}
