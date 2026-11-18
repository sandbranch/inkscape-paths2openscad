paths2openscad
==============

> **This fork (branch `inkscape-1.4`) works in Inkscape 1.4.** The last
> upstream release (v0.27, 2020) predates Inkscape 1.0 and crashes in
> 1.4 (upstream issue #25); master was ported to 1.0 but never released,
> and still had these bugs, all fixed here:
>
> * crashed at start with Python 3.14 (a bare `%` in a help text), and
>   on any XML comment in the drawing;
> * documents without a viewBox (px documents) came out 3.78 times too
>   big; line widths in outline mode were wrong in px and scaled
>   documents. Sizes now come from inkex, so mm, px and scaled
>   documents all give the drawing's size in mm;
> * rects ignored rounded corners and crashed without an `x`; lines
>   touching 0 were dropped (shapes now go through inkex);
> * with `fill-rule:nonzero`, a subpath inside another one winding the
>   same way became a hole; it is filled now, as Inkscape shows it;
> * clones (`<use>`) of one object: only the last one was output
>   (upstream issue #9); hidden groups with more than `display:none` in
>   their style were output;
> * `{NAME}.scad` was written into the extension folder (Inkscape makes
>   the path parameter absolute there), now next to the drawing
>   (upstream issue #24);
> * command line defaults now match the .inx (chamfer 0, line width
>   scale 100 %).
>
> Tests: `python3 -m pytest tests/` (needs inkex 1.4; the STL checks
> also need `openscad`). Install: `dev/install.sh` symlinks
> `paths2openscad.inx` and `paths2openscad.py` into
> `~/.config/inkscape/extensions/paths2openscad/`; on Windows or macOS
> copy those two files into the folder shown under Edit > Preferences >
> System > User extensions. Menu: Extensions > Generate from Path >
> Paths to OpenSCAD.

[![Downloads](https://img.shields.io/github/downloads/fablabnbg/inkscape-paths2openscad/total.svg?maxAge=2592000?style=flat-square)](https://github.com/fablabnbg/inkscape-paths2openscad/releases/latest)
[![GitHub release](https://img.shields.io/github/release/fablabnbg/inkscape-paths2openscad.svg)](https://github.com/fablabnbg/paths2openscad/releases)
[![Build Status](https://travis-ci.org/fablabnbg/inkscape-paths2openscad.svg?branch=master)](https://travis-ci.org/fablabnbg/inkscape-paths2openscad)

<img align="right" src="https://cloud.githubusercontent.com/assets/3838734/3856761/e55ecdf2-1efb-11e4-97f8-7c3195fc361d.png" width="200" />

Download and install for Debian and Ubuntu Linux: https://github.com/fablabnbg/inkscape-paths2openscad/releases


SVG paths to OpenSCAD converter. Copied from Thingiverse things [24808](http://www.thingiverse.com/thing:24808) and [25036](http://www.thingiverse.com/thing:25036), both copyright user [dnewman](http://www.thingiverse.com/dnewman) and released under GPL v2 or later.

See also: Thingiverse things [1065500](http://www.thingiverse.com/thing:1065500)  Inkscape to OpenSCAD converter v7 by Neon22.

Examples published on thingiverse: https://www.thingiverse.com/tag:inkscape-3D

Example for a scriptable call (untested)
```
inkscape --verb=EditSelectAll --verb=SelectionCombine --verb=EditDeselect --verb=command.extrude.openscad_auto.noprefs --verb=EditUndo --verb=EditUndo --verb=FileQuit /full/path/to/file.svg
```

Windows
-------

1. install openscad

2. Add OpenSCAD to the path:

- Create a new Environment Variable:

    Name: SCAD_PATH

    Value: path to openscad.exe (e.g., C:\Program Files\OpenSCAD)

- Add or extend the PATH environment variable:

    Name: PATH

    Value: %SCAD_PATH%

3. open the paths to OpenSCAD extension in inkscape, got to the Commands tab. 

   Replace all occurrences of 'openscad' with the full path to openscad.exe -- also include the quotes. E.g.:
   
   ```
   "C:\Program Files\OpenSCAD\openscad.exe" "{NAME}.scad"
   "C:\Program Files\OpenSCAD\openscad.exe" "{NAME}.scad" -o "{NAME}.stl"
   ```
   
   
