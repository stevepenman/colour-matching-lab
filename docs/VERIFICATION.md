# Verification record

Prepared and checked on **25 October 2026**, on Windows x64 with Python **3.14.2**. No hardware capture or production deployment is claimed.

| Check | Observed result |
| --- | --- |
| Isolated virtual environment and `pip install -r requirements.txt` | Passed after allowing public dependency downloads; the first sandboxed attempt could not access the package index |
| `python -m pip check` | Passed; no broken requirements |
| `python -m unittest discover -s tests -v` | Passed: 11 tests in the newly installed environment |
| `python demo.py --rgb 128 128 128` | Passed; `Demo neutral 05`, RGB 128/128/128, Delta E approximately 0 |
| Invalid CLI input `--rgb -1 0 0` | Rejected with a clear message and exit code 1, as intended |
| `python ui.py --help` | Passed; camera selection is explicit |
| GUI startup/event loop/shutdown | Passed offscreen through the real entry point with an automatic close timer, temporary storage and camera access blocked |
| GUI preview and interaction | Passed tests for default synthetic preview, click matching, centre sampling, local history, visible history-write failure and orderly worker shutdown |
| Synthetic library regeneration | Passed; 56 generated rows agree with the bundled library within numerical tolerance |
| `python scripts/render_demo.py` | Passed; generated screenshot was visually inspected; an initial missing-font render was replaced after registering the installed system font |
| `python -m compileall -q color_matching.py demo.py generate_demo_library.py ui.py tests scripts` | Passed after retrying outside a sandbox restriction on bytecode-cache writes |
| Publication inventory and heuristic audit | Passed; 21 reviewed publication files, zero findings |
| Private deny-term scan of paths and contents | Passed; zero findings; removed terms are not included in the public report |
| Original source/data preservation | SHA-256 hashes of all 10 original top-level and data files matched the pre-preparation baseline |
| Git publication boundary | Fresh local repository on `main`; no commits, no remotes, no copied history; environment, runtime data, caches and credential examples are ignored |

The numerical/GUI tests first passed using the existing local environment, then passed again after a fresh installation using the portfolio requirements. The direct versions were NumPy 2.4.1, pandas 2.3.3, colour-science 0.4.7, OpenCV 4.11.0.86 and PyQt5 5.15.11. Transitive versions are not fully locked.

The environment emits colour-science notices that optional SciPy and Matplotlib features are unavailable. Neither package is needed by the demonstrated conversions, matching, GUI or tests; these checks passed without them. They have not been silently added as required dependencies.

The GitHub Actions file is configured for Windows/Python 3.14. It has **not run on GitHub** because nothing was pushed. Real webcam behaviour, device colour accuracy, controlled illumination, physical reference matching, other operating systems, Raspberry Pi hardware and production use remain unverified. Offscreen GUI checks and a rendered screenshot are not hardware validation.

The audit uses a fixed inventory and heuristic patterns, supplemented by direct content review. It cannot establish ownership, publication permission or absence of every possible confidential detail. Review those matters before uploading; no licence or copyright claim was added.
