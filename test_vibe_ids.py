"""Checks that a vibe id can never escape the vibe folders.

Vibe ids become file names, and an id can arrive from a shared .naiv4vibe file
or a PNG chunk. Run from the extension folder, no webui needed:

    python test_vibe_ids.py
"""

import ast
import os
import sys

sys.path.insert(0, ".")

from nai_api_gen import nai_api  # noqa: E402

REAL = "09fb00f2cf44f2701e87f9e16361a564e4e988ede64a7fe36626b17afc202478"

ATTACKS = [
    "../../webui-user",
    "..\\..\\webui-user",
    "C:/Users/someone/Pictures/favourite",
    "C:\\Windows\\win",
    "/etc/passwd",
    "\\\\server\\share\\x",
    "..",
    "a/b",
    "id.with.dots",
    "",
    None,
    "x" * 200,
]


def main():
    failed = 0

    def check(ok, label):
        nonlocal failed
        if not ok:
            failed += 1
            print(f"FAIL {label}")

    check(nai_api.safe_vibe_id(REAL) == REAL, "a real sha256 id must pass")
    check(nai_api.safe_vibe_id("  " + REAL + " ") == REAL, "surrounding whitespace is trimmed")
    for bad in ATTACKS:
        check(nai_api.safe_vibe_id(bad) is None, f"unsafe id accepted: {bad!r}")

    # every id already on disk must still load
    folder = "vibe_encodings"
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith(".naiv4vibe"):
                check(nai_api.safe_vibe_id(f[:-len(".naiv4vibe")]) is not None, f"existing vibe rejected: {f}")

    # no function may build a path from a vibe id without validating it first
    src = open(os.path.join("nai_api_gen", "nai_api_script.py"), encoding="utf-8").read()
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        body = ast.get_source_segment(src, fn) or ""
        uses_id_in_path = any(
            isinstance(n, ast.Call) and ast.unparse(n.func) == "os.path.join"
            and any(isinstance(a, ast.Name) and a.id == "id" for a in ast.walk(n))
            for n in ast.walk(fn))
        minted_locally = "nai_api.create_encoding_file" in body   # sha256 of our own data
        if uses_id_in_path and not minted_locally:
            check("safe_vibe_id" in body, f"{fn.name}() builds a path from an unvalidated id")

    print("ok  vibe ids cannot escape the vibe folders" if not failed else f"{failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
