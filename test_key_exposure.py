"""Checks when the extension warns that others can read the saved API key.

Run from the extension folder, no webui needed:

    python test_key_exposure.py
"""

import ast
import os
import sys
import types

SRC = open(os.path.join("nai_api_gen", "nai_api_settings.py"), encoding="utf-8").read()
FN = next(n for n in ast.parse(SRC).body if isinstance(n, ast.FunctionDef) and n.name == "key_exposed_to")
ns = {}
exec(compile(ast.Module(body=[FN], type_ignores=[]), "nai_api_settings", "exec"), ns)
key_exposed_to = ns["key_exposed_to"]

CASES = [
    # (label, launch flags, on colab, should warn)
    ("plain local run", {}, False, False),
    ("--api on its own binds to 127.0.0.1", {"api": True}, False, False),
    ("--share", {"share": True}, False, True),
    ("--listen", {"listen": True}, False, True),
    ("--ngrok", {"ngrok": "tok"}, False, True),
    ("--share + --gradio-auth", {"share": True, "gradio_auth": "u:p"}, False, False),
    ("--share + auth, but the API is open", {"share": True, "gradio_auth": "u:p", "api": True}, False, True),
    ("--listen + both auths", {"listen": True, "gradio_auth": "u:p", "api": True, "api_auth": "u:p"}, False, False),
    ("Colab, no flags - its tunnels are invisible to the webui", {}, True, True),
    ("Colab + --gradio-auth", {"gradio_auth": "u:p"}, True, False),
]


def main():
    failed = 0
    for label, flags, colab, want in CASES:
        env = {"COLAB_RELEASE_TAG": "release"} if colab else {}
        got = bool(key_exposed_to(types.SimpleNamespace(**flags), environ=env, modules={}))
        if got != want:
            failed += 1
            print(f"FAIL {label}: warns={got}, expected {want}")
    print(f"{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
