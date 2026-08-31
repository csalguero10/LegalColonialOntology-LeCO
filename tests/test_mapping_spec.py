from pathlib import Path
import re
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "mapping" / "tei_to_leco.yaml"
TEI_EXAMPLE = ROOT / "data" / "documents" / "cab-001-002" / "tei.xml"
XML_NS = "{http://www.w3.org/XML/1998/namespace}id"


def test_mapping_yaml_has_unique_rule_ids():
    spec = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
    assert spec["name"] == "LeCO-TEI Mapping Profile"
    ids = [rule["id"] for rule in spec["mapping_rules"]]
    assert len(ids) == len(set(ids))
    assert {"R001", "R040", "R041", "R050"}.issubset(ids)


def test_tei_example_local_pointers_resolve():
    tree = ET.parse(TEI_EXAMPLE)
    root = tree.getroot()
    ids = {el.attrib[XML_NS] for el in root.iter() if XML_NS in el.attrib}
    assert ids

    pointer_attrs = {"ref", "active", "passive", "source", "corresp", "target", "resp"}
    broken = []
    for el in root.iter():
        for attr in pointer_attrs:
            value = el.attrib.get(attr)
            if not value:
                continue
            for token in re.split(r"\s+", value.strip()):
                if token.startswith("#") and token[1:] not in ids:
                    broken.append((el.tag, attr, token))
    assert not broken, f"Broken local TEI pointers: {broken}"


def test_tei_example_has_unique_xml_ids():
    tree = ET.parse(TEI_EXAMPLE)
    root = tree.getroot()
    ids = [el.attrib[XML_NS] for el in root.iter() if XML_NS in el.attrib]
    assert len(ids) == len(set(ids))
