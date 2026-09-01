import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "participant_audit.py"


def test_script_compiles():
    subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPT)], check=True)


def test_participant_filter_function():
    import importlib.util
    spec = importlib.util.spec_from_file_location("participant_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    assert mod.is_participant_warning({"constraint":"sh:OrConstraintComponent","result_path":"","message":"No se ha identificado ningún participante del acto."})
    assert not mod.is_participant_warning({"constraint":"sh:MinCountConstraintComponent","result_path":"leco:withinJurisdiction","message":"x"})


def test_flag_after_event_requires_review():
    import importlib.util
    spec = importlib.util.spec_from_file_location("participant_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    m = mod.EntityMention("m1", "person_1", "person", "Persona", "after")
    flag, _ = mod.flag_resolution(["person_1"], [m], [], [])
    assert "REVIEW" in flag
