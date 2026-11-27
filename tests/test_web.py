import importlib.util
import json
import re
import shutil

import pytest

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


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("n", [1, 13, 55, 200])
def test_web_demo_peaks_match_python_engine(tmp_path, n):
    """The demo's JS port must find the same peaks as composition.salience_curve on its grid."""
    import subprocess

    import numpy as np
    from scipy.signal import find_peaks

    from zeta_music.composition import salience_curve

    html = _build_module().build(tmp_path / "demo.html").read_text()
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1).split("// ---------- state ----------")[0]
    js = js.replace('document.documentElement.lang = document.documentElement.lang || "en";', "")
    script = tmp_path / "t.js"
    script.write_text(js + f"\nconsole.log(JSON.stringify(findPeaks(salience({n}), {n}).map(p => p.x)));\n")
    js_x = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)

    x = np.linspace(1.5, 31.5, 1200)
    s = salience_curve(x, np.full(x.size, float(n)), load_zeros(200))
    idx, _ = find_peaks(s, prominence=0.18, height=0.18)
    assert len(js_x) == idx.size
    np.testing.assert_allclose(js_x, x[idx], atol=0.03)  # JS refines peaks sub-grid


def test_standalone_build_is_a_full_document(tmp_path):
    html = _build_module().build(tmp_path / "demo.html", standalone=True).read_text()
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert html.count("<head>") == 1 and html.count("<body>") == 1 and 'lang="en"' in html
