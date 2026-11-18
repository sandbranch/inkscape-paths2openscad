# Copyright 2026 David
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Run paths2openscad through inkex, like Inkscape does, on one drawing in
three kinds of document (mm, px without viewBox, and scaled with 2 mm
per user unit), then check the model it writes: the polygons it holds
are in mm, and, when OpenSCAD is installed, the STL OpenSCAD renders
from the .scad file has the drawing's size in mm, the requested height,
and holes where the drawing has holes.

Needs inkex 1.4 (pip install --no-deps inkex==1.4.0, plus lxml, numpy,
tinycss2, cssselect, pyparsing, packaging), as in the GitHub workflow.
The STL tests need the openscad program (set OPENSCAD to its path if it
is not on PATH); they are skipped without it.
"""

import io
import math
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import inkex

from paths2openscad import OpenSCAD

OPENSCAD = os.environ.get("OPENSCAD") or shutil.which("openscad")
if os.environ.get("REQUIRE_OPENSCAD") and not OPENSCAD:
    raise RuntimeError("REQUIRE_OPENSCAD is set but openscad was not found")
needs_openscad = pytest.mark.skipif(not OPENSCAD, reason="openscad not installed")

MM = 96 / 25.4  # px per mm

# Document kinds: (svg attributes, user units per mm)
KINDS = {
    "mm": ('width="210mm" height="297mm" viewBox="0 0 210 297"', 1.0),
    "px": ('width="%g" height="%g"' % (210 * MM, 297 * MM), MM),
    "scaled": ('width="210mm" height="297mm" viewBox="0 0 105 148.5"', 0.5),
}

# The glyphs "B" and "O" from DejaVu Sans 30 px, converted to paths by
# Inkscape 1.4.3 (Path > Object to Path), in mm. fill-rule is nonzero
# and the holes wind the other way, as in fonts.
GLYPH_B = (
    "m 15.90332,29.555664 v 8.012695 h 4.746094 q 2.387695,0 3.530273,-0.981445 "
    "1.157227,-0.996094 1.157227,-3.032227 0,-2.050781 -1.157227,-3.017578 "
    "-1.142578,-0.981445 -3.530273,-0.981445 z m 0,-8.994141 v 6.591797 h 4.379883 "
    "q 2.167969,0 3.222656,-0.805664 1.069336,-0.820312 1.069336,-2.490234 "
    "0,-1.655274 -1.069336,-2.475586 -1.054687,-0.820313 -3.222656,-0.820313 z "
    "m -2.958984,-2.43164 h 7.558594 q 3.383789,0 5.214843,1.40625 1.831055,1.40625 "
    "1.831055,3.999023 0,2.006836 -0.9375,3.19336 -0.9375,1.186523 -2.753906,1.479492 "
    "2.182617,0.46875 3.383789,1.96289 1.21582,1.479493 1.21582,3.706055 "
    "0,2.929688 -1.992187,4.526367 Q 24.472656,40 20.795898,40 h -7.851562 z"
)
GLYPH_O = (
    "m 61.821289,20.136719 q -3.222656,0 -5.126953,2.402343 -1.889649,2.402344 "
    "-1.889649,6.547852 0,4.130859 1.889649,6.533203 1.904297,2.402344 5.126953,2.402344 "
    "3.222656,0 5.097656,-2.402344 1.889649,-2.402344 1.889649,-6.533203 "
    "0,-4.145508 -1.889649,-6.547852 -1.875,-2.402343 -5.097656,-2.402343 z "
    "m 0,-2.402344 q 4.599609,0 7.353516,3.09082 2.753906,3.076172 2.753906,8.261719 "
    "0,5.170898 -2.753906,8.261719 -2.753907,3.076172 -7.353516,3.076172 "
    "-4.614258,0 -7.382812,-3.076172 -2.753907,-3.076172 -2.753907,-8.261719 "
    "0,-5.185547 2.753907,-8.261719 2.768554,-3.09082 7.382812,-3.09082 z"
)

# The drawing, in mm. It sits in a group scaled to the document's user
# units, so it has the same size in mm in every kind of document.
# Each object: id -> (bbox in mm [x0, y0, x1, y1], points in holes,
# points in material), all in drawing mm.
DRAWING = """
  <path id="ring" style="fill:#000;fill-rule:evenodd"
     d="M 20,30 A 10,10 0 1 0 40,30 A 10,10 0 1 0 20,30 Z
        M 24,30 A 6,6 0 1 0 36,30 A 6,6 0 1 0 24,30 Z"/>
  <path id="disc_nz" style="fill:#000;fill-rule:nonzero"
     d="M 20,60 A 10,10 0 1 0 40,60 A 10,10 0 1 0 20,60 Z
        M 24,60 A 6,6 0 1 0 36,60 A 6,6 0 1 0 24,60 Z"/>
  <rect id="rrect" x="60" y="20" width="40" height="20" rx="3" style="fill:#000"/>
  <rect id="rect_nox" y="50" width="15" height="10" style="fill:#000"/>
  <circle id="circ" cx="130" cy="30" r="8" style="fill:#000"/>
  <ellipse id="ell" cx="160" cy="30" rx="12" ry="5" style="fill:#000"/>
  <g id="outer" transform="translate(30,100)">
    <g id="inner" transform="rotate(90) scale(2)">
      <rect id="nested" x="0" y="0" width="10" height="5" style="fill:#000"/>
    </g>
  </g>
  <path id="curve" style="fill:#000" d="M 60,100 C 60,130 100,130 100,100 Z"/>
  <g id="glyphs" transform="translate(100,80)">
    <path id="glyphB" d="%s"/>
    <path id="glyphO" d="%s"/>
  </g>
  <path id="line" style="fill:none;stroke:#000;stroke-width:3" d="M 20,150 H 80"/>
""" % (GLYPH_B, GLYPH_O)

OBJECTS = {
    "ring": ([20, 20, 40, 40], [(30, 30)], [(22, 30), (30, 38)]),
    "disc_nz": ([20, 50, 40, 70], [], [(30, 60), (22, 60)]),
    "rrect": ([60, 20, 100, 40], [(60.2, 20.2)], [(80, 30), (61, 30)]),
    "rect_nox": ([0, 50, 15, 60], [], [(7.5, 55)]),
    "circ": ([122, 22, 138, 38], [(123, 23)], [(130, 30)]),
    "ell": ([148, 25, 172, 35], [(150, 26)], [(160, 30)]),
    "nested": ([20, 100, 30, 120], [], [(25, 110)]),
    "curve": ([60, 100, 100, 122.5], [], [(80, 110)]),
    "glyphB": (None, [(119.5, 103.8), (120.5, 113.5)], [(114.4, 110)]),
    "glyphO": (None, [(161.8, 109)], [(153.3, 109)]),
}


def make_svg(kind, body=DRAWING):
    attrs, k = KINDS[kind]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" %s>'
        '<g id="layer" transform="scale(%r)">%s</g></svg>' % (attrs, k, body)
    )


def glyph_bbox(node_id):
    """Bounding box of a glyph in drawing mm, from inkex (not from the
    extension)."""
    svg = inkex.load_svg(io.BytesIO(make_svg("mm").encode())).getroot()
    bb = svg.getElementById(node_id).bounding_box(svg.getElementById(node_id).composed_transform())
    return [bb.left, bb.top, bb.right, bb.bottom]


def run(tmp_path, monkeypatch, svg_text, *args, ids=()):
    """Run the extension; returns (extension, path of the .scad file)."""
    svg_file = tmp_path / "drawing.svg"
    svg_file.write_text(svg_text)
    scad = tmp_path / "out.scad"
    monkeypatch.setenv("DOCUMENT_PATH", str(svg_file))
    ext = OpenSCAD()
    ext.run(
        # Inkscape passes the .inx defaults
        ["--fname=%s" % scad, "--chamfer=0", "--line_width_scale_perc=100", *args, *("--id=%s" % i for i in ids), str(svg_file)],
        output=io.BytesIO(),
    )
    return ext, scad


def objects(ext):
    """The subpaths of each object the extension made, in mm."""
    if isinstance(ext.paths, dict):  # upstream keeps a dict, one entry per node
        return list(ext.paths.values())
    return [subs for _, subs, _ in ext.paths]


def model_points(ext):
    """All polygon vertices the extension made, in mm."""
    return np.array([p for subs in objects(ext) for sub, _ in subs for p in sub], float)


def render_stl(scad):
    stl = scad.with_suffix(".stl")
    res = subprocess.run(
        [OPENSCAD, "--export-format", "asciistl", "-o", str(stl), str(scad)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert res.returncode == 0, res.stderr
    tris = []
    for line in stl.read_text().splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            tris.append([float(v) for v in line.split()[1:]])
    return np.array(tris, float).reshape(-1, 3, 3)


def solid_at(tris, x, y):
    """Whether the extruded model has material above (x, y): some
    triangle covers the point when seen from above."""
    a, b, c = tris[:, 0, :2], tris[:, 1, :2], tris[:, 2, :2]
    p = np.array([x, y])

    def cross(u, v, w):
        return (v[:, 0] - u[:, 0]) * (w[1] - u[:, 1]) - (v[:, 1] - u[:, 1]) * (w[0] - u[:, 0])

    d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
    neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    return bool(np.any(~(neg & pos)))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("obj", OBJECTS)
def test_polygons_in_mm(tmp_path, monkeypatch, kind, obj):
    """The polygons the extension builds span the object's size in mm."""
    bbox = OBJECTS[obj][0] or glyph_bbox(obj)
    ext, _ = run(tmp_path, monkeypatch, make_svg(kind), ids=[obj])
    pts = model_points(ext)
    size = pts.max(axis=0) - pts.min(axis=0)
    assert size == pytest.approx([bbox[2] - bbox[0], bbox[3] - bbox[1]], abs=0.05)


@needs_openscad
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("obj", OBJECTS)
def test_stl_size_height_and_holes(tmp_path, monkeypatch, kind, obj):
    """OpenSCAD renders the object at its size in mm, the requested
    height, with holes where the drawing has holes."""
    bbox, holes, solids = OBJECTS[obj]
    bbox = bbox or glyph_bbox(obj)
    _, scad = run(tmp_path, monkeypatch, make_svg(kind), "--zsize=7", ids=[obj])
    tris = render_stl(scad)
    lo = tris.reshape(-1, 3).min(axis=0)
    hi = tris.reshape(-1, 3).max(axis=0)
    assert hi - lo == pytest.approx([bbox[2] - bbox[0], bbox[3] - bbox[1], 7], abs=0.05)
    # The model is centred on the selection's bounding box, y up.
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    for x, y in holes:
        assert not solid_at(tris, x - cx, cy - y), ("hole", x, y)
    for x, y in solids:
        assert solid_at(tris, x - cx, cy - y), ("material", x, y)


@needs_openscad
@pytest.mark.parametrize("kind", KINDS)
def test_outline_width_in_mm(tmp_path, monkeypatch, kind):
    """A stroked line without fill comes out as wide as its stroke, in mm,
    in every kind of document."""
    _, scad = run(tmp_path, monkeypatch, make_svg(kind), "--zsize=2", ids=["line"])
    tris = render_stl(scad)
    size = tris.reshape(-1, 3).max(axis=0) - tris.reshape(-1, 3).min(axis=0)
    # line_fn=4: the cylinders at the ends are squares with corners on the axes
    assert size == pytest.approx([63, 3, 2], abs=0.05)


@needs_openscad
def test_whole_drawing(tmp_path, monkeypatch):
    """With nothing selected, everything is output and the model spans
    the whole drawing."""
    _, scad = run(tmp_path, monkeypatch, make_svg("scaled"), "--zsize=4")
    tris = render_stl(scad)
    size = tris.reshape(-1, 3).max(axis=0) - tris.reshape(-1, 3).min(axis=0)
    # x: rect_nox at 0 to the ellipse at 172; y: 20 to the line at 151.5
    assert size == pytest.approx([172, 131.5, 4], abs=0.05)


@needs_openscad
def test_depth_from_description(tmp_path, monkeypatch):
    body = (
        '<rect id="a" x="0" y="0" width="10" height="10"><desc>Depth: 3 mm\nOffset: 2 mm</desc></rect>'
        '<rect id="b_12mm" x="20" y="0" width="10" height="10"/>'
    )
    _, scad = run(tmp_path, monkeypatch, make_svg("scaled", body), "--zsize=5")
    tris = render_stl(scad)
    a = tris[tris[:, :, 0].max(axis=1) < 0]
    b = tris[tris[:, :, 0].min(axis=1) > 0]
    assert a[:, :, 2].min() == pytest.approx(2) and a[:, :, 2].max() == pytest.approx(5)
    assert b[:, :, 2].min() == pytest.approx(0) and b[:, :, 2].max() == pytest.approx(12)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("smoothness", [0.2, 0.02])
def test_flattening_tolerance_in_mm(tmp_path, monkeypatch, kind, smoothness):
    """Curves are flattened to within the smoothness, in mm, whatever the
    document's units: every point of the true curve is that close to the
    polygon, and the polygon has the same number of points in every
    kind of document."""
    ext, _ = run(
        tmp_path, monkeypatch, make_svg(kind), "--smoothness=%g" % smoothness, ids=["curve"]
    )
    poly = np.array(objects(ext)[0][0][0], float)
    # the true curve in mm, translated like the polygon (start point)
    t = np.linspace(0, 1, 2001)[:, None]
    p0, p1, p2, p3 = (np.array(v, float) for v in [(60, 100), (60, 130), (100, 130), (100, 100)])
    curve = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3
    curve = curve - p0 + poly[0]
    a, b = poly[:-1], poly[1:]
    ab = b - a
    worst = 0.0
    for q in curve:
        u = np.clip(((q - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
        d = np.sqrt((((a + u[:, None] * ab) - q) ** 2).sum(1)).min()
        worst = max(worst, d)
    assert worst <= smoothness
    # same flattening in mm, px and scaled documents
    ext_mm, _ = run(tmp_path, monkeypatch, make_svg("mm"), "--smoothness=%g" % smoothness, ids=["curve"])
    assert len(objects(ext)[0][0][0]) == len(objects(ext_mm)[0][0][0])


def test_comment_in_drawing(tmp_path, monkeypatch):
    """An XML comment in the drawing used to crash it (AttributeError)."""
    body = '<!-- a comment --><rect id="r" x="0" y="0" width="10" height="5"/>'
    ext, _ = run(tmp_path, monkeypatch, make_svg("mm", body))
    assert len(ext.paths) == 1


def test_line_touching_zero(tmp_path, monkeypatch):
    """A <line> with a coordinate of 0 was dropped."""
    body = '<line id="l" x1="0" y1="10" x2="30" y2="10" style="stroke:#000;stroke-width:2"/>'
    ext, _ = run(tmp_path, monkeypatch, make_svg("mm", body))
    assert len(ext.paths) == 1


def test_clones_are_output(tmp_path, monkeypatch):
    """Each clone (<use>) is output, not only the last one (upstream
    issue #9)."""
    body = (
        '<rect id="r" x="0" y="0" width="10" height="5"/>'
        '<use id="c1" xlink:href="#r" x="20"/>'
        '<use id="c2" xlink:href="#r" transform="translate(40,0)"/>'
    )
    ext, scad = run(tmp_path, monkeypatch, make_svg("mm", body))
    assert len(ext.paths) == 3
    pts = model_points(ext)
    assert pts[:, 0].max() - pts[:, 0].min() == pytest.approx(50)
    assert scad.read_text().count("module poly_") == 3


def test_hidden_layer_skipped(tmp_path, monkeypatch):
    body = (
        '<rect id="r" x="0" y="0" width="10" height="5"/>'
        '<g style="display:none;opacity:1"><rect id="h" x="50" y="0" width="10" height="5"/></g>'
    )
    ext, _ = run(tmp_path, monkeypatch, make_svg("mm", body))
    assert len(objects(ext)) == 1


def test_relative_name_next_to_drawing(tmp_path, monkeypatch):
    """{NAME}.scad goes next to the saved drawing, not into the folder
    Inkscape runs the extension in (upstream issue #24)."""
    elsewhere = tmp_path / "extensions"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("PWD", str(elsewhere))
    svg_file = tmp_path / "my drawing.svg"
    svg_file.write_text(make_svg("mm", '<rect id="r" x="0" y="0" width="10" height="5"/>'))
    monkeypatch.setenv("DOCUMENT_PATH", str(svg_file))
    OpenSCAD().run(["--fname={NAME}.scad", str(svg_file)], output=io.BytesIO())
    assert (tmp_path / "my drawing.scad").exists()
    assert not list(elsewhere.iterdir())


def test_name_inkscape_made_absolute(tmp_path, monkeypatch):
    """Inkscape turns the relative '{NAME}.scad' of the path parameter into
    a name in the extension's folder before the extension sees it; that
    must still go next to the drawing (upstream issue #24)."""
    svg_file = tmp_path / "drawing.svg"
    svg_file.write_text(make_svg("mm", '<rect id="r" x="0" y="0" width="10" height="5"/>'))
    monkeypatch.setenv("DOCUMENT_PATH", str(svg_file))
    ext_dir = os.path.dirname(os.path.abspath(sys.modules[OpenSCAD.__module__].__file__))
    before = set(os.listdir(ext_dir))
    OpenSCAD().run(["--fname=%s" % os.path.join(ext_dir, "{NAME}.scad"), str(svg_file)], output=io.BytesIO())
    assert (tmp_path / "drawing.scad").exists()
    assert set(os.listdir(ext_dir)) == before


def test_cli_defaults_match_inx():
    """Defaults used without the .inx (command line) are those of the .inx."""
    ext = OpenSCAD()
    opts = ext.arg_parser.parse_args([])
    assert opts.chamfer == 0
    assert opts.line_width_scale_perc == 100
