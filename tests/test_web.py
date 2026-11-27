import importlib.util
import json
import re

from zeta_music.zeros import load_zeros

from .conftest import ROOT


def _build_module():
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_web_demo_build_injects_first_200_zeros(tmp_path):
    out = _build_module().build(tmp_path / "demo.html")
    html = out.read_text()
    assert "/*__ZEROS__*/" not in html
    arr = json.loads(re.search(r"const GAMMAS = (\[.*?\]);", html).group(1))
    assert len(arr) == 200
    assert abs(arr[0] - load_zeros(1)[0]) < 1e-8
    assert "<title>Hear the Primes</title>" in html
