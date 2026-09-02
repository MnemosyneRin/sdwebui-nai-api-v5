"""Checks for the NAI -> A1111 prompt conversion used when importing an image.

Run from the extension folder, no webui needed:

    python test_nai_prompt_convert.py
"""

import sys

sys.path.insert(0, ".")

from nai_api_gen import nai_api  # noqa: E402

CASES = [
    # literal brackets in tags must stay literal, or re-importing an image turns
    # an artist name into an emphasis group
    ("artist:toma (toma50)", r"artist:toma \(toma50\)"),
    ("tharja (fire emblem), 1girl", r"tharja \(fire emblem\), 1girl"),
    # NAI weights become A1111 weights
    ("0.2::artist:shexyo::", "(artist:shexyo:0.2)"),
    ("a, 0.5::b::, c", "a, (b:0.5), c"),
    ("-0.5::x::", "(x:-0.5)"),
    # a weighted phrase ending in a full stop: the '.' is text, not a weight, and
    # the rest of the prompt keeps its own weight
    ("1.1::x.::, plain", "(x.:1.1), plain"),
    ("5.0::a b.::, tail here", "(a b.:5), tail here"),
    # untouched
    ("plain only", "plain only"),
    ("", ""),
]


def main():
    failed = 0
    for source, expected in CASES:
        got = nai_api.nai_v4_to_sd(source)
        if got != expected:
            failed += 1
            print(f"FAIL {source!r}\n  got  {got!r}\n  want {expected!r}")
    print(f"{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
