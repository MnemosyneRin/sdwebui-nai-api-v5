"""
No checkpoint in VRAM until something actually generates with it.

Built into the NAI extension from the standalone sd-webui-no-local-model.
Toggle it in Settings > NAI API Generator; it needs a restart either way.

Nothing is loaded at startup, and nothing is loaded for a generation that never
touches the local model - generating through a remote API (NovelAI, or any
extension that produces the image itself) costs no VRAM at all. The moment a
generation really needs weights, the checkpoint loads normally and everything
carries on.

No settings, no flags, no per-extension special cases: `shared.sd_model` hands
out a stand-in that answers the handful of cheap questions processing.py asks
(which checkpoint, its hash) and loads the real model on the first question only
real weights can answer.

Works on A1111, Forge, reForge and Forge Neo.
"""

import os
import traceback

# Answered without loading anything. Everything else materialises the model.
_ABSENT = ("fix_dimensions",)  # asked about with hasattr(); saying no is free

_orig = {}
_loading = False
_pending_tiling = None
_generating = False  # only a generation may pull a checkpoint into VRAM
_refused = set()


def _sd_models():
    import modules.sd_models

    return modules.sd_models


def _real_model():
    """The loaded checkpoint, or None if all we have is a placeholder."""
    model = _sd_models().model_data.sd_model
    if model is None or model is STUB:
        return None
    if type(model).__name__ == "FakeInitialModel":  # Forge Neo's own placeholder
        return None
    return model


# Which model family a checkpoint belongs to, told by the tensor names in its
# header. Extensions ask this constantly ("is_sdxl") to decide how to behave,
# and answering costs a few KB of file read instead of the whole checkpoint.
_FAMILY_KEYS = (
    ("is_flux", "double_blocks."),
    ("is_sd3", "joint_blocks."),
    ("is_sdxl", "conditioner.embedders.1"),
    ("is_sd2", "cond_stage_model.model."),
    ("is_sd1", "cond_stage_model.transformer."),
)
_family_cache = {}


def _family():
    """{is_sdxl: True, is_sd1: False, ...} for the selected checkpoint, or None."""
    filename = getattr(_checkpoint_info(), "filename", None)
    if not filename or not filename.endswith(".safetensors"):
        return None  # can't read it cheaply; let the caller load the model
    if filename not in _family_cache:
        _family_cache[filename] = _read_family(filename)
    return _family_cache[filename]


def _read_family(filename):
    import json
    import struct

    try:
        with open(filename, "rb") as f:
            (length,) = struct.unpack("<Q", f.read(8))
            names = json.loads(f.read(length)).keys()
    except Exception:
        return None

    for flag, marker in _FAMILY_KEYS:
        if any(marker in name for name in names):
            return {other: other == flag for other, _ in _FAMILY_KEYS}
    return None  # unrecognised: better to load than to answer wrongly


def _checkpoint_info():
    try:
        return _sd_models().select_checkpoint()  # reads the list, loads nothing
    except Exception:
        return None


def _materialise(wanted="weights"):
    """Load the checkpoint for real - called the moment weights are needed."""
    global _loading

    model = _real_model()
    if model is not None:
        return model

    print(f"[no-local-model] .{wanted} needs the checkpoint, loading it")
    if os.environ.get("NLM_DEBUG"):
        traceback.print_stack()
    _loading = True
    try:
        if _orig.get("forge_model_reload") is not None:  # Forge Neo
            model = _orig["forge_model_reload"]()[0]
        else:  # A1111 / Forge / reForge
            model = _orig["get_sd_model"]()
    finally:
        _loading = False

    # replay the two setup steps that were skipped while we were pretending
    if _pending_tiling is not None and _orig.get("apply_circular_forge"):
        try:
            _orig["apply_circular_forge"](model, _pending_tiling)
        except Exception:
            pass
    if _orig.get("load_embeddings"):
        try:
            _orig["load_embeddings"]()
        except Exception:
            pass

    return model


class _StubModel:
    """Stands in for shared.sd_model until real weights are asked for."""

    def __bool__(self):
        # `if shared.sd_model:` is how the webui asks "is a model loaded?" -
        # answering False short-circuits those checks instead of erroring.
        return _real_model() is not None

    def __getattr__(self, name):
        if name.startswith("_") or name in _ABSENT:
            raise AttributeError(name)  # probes and optional features: just say no
        if name == "sd_checkpoint_info":
            return _checkpoint_info()
        if name == "sd_model_hash":
            return getattr(_checkpoint_info(), "shorthash", "") or ""
        if name in ("is_wan", "tiling_enabled"):
            return False
        if name in ("comments", "extra_generation_params"):
            return [] if name == "comments" else {}
        if name.startswith("is_"):
            family = _family()
            if family is not None and name in family:
                return family[name]
        if not _generating:
            # Nobody is generating, so nothing needs weights - answer the way a
            # webui with no checkpoint loaded yet does, instead of loading one
            # because an extension got curious while building its UI.
            if name not in _refused:
                _refused.add(name)
                print(f"[no-local-model] no checkpoint loaded, so no .{name} (nothing is generating)")
            raise AttributeError(name)
        return getattr(_materialise(name), name)

    def __setattr__(self, name, value):
        # processing.py resets these before deciding anything - keep them local
        if name in ("comments", "extra_generation_params", "tiling_enabled"):
            object.__setattr__(self, name, value)
        else:
            setattr(_materialise(name), name, value)


STUB = _StubModel()


def _standalone_installed():
    """The standalone sd-webui-no-local-model extension does the same job. Two
    copies must never both patch: the second would wrap the first, and loading
    the model would hand back the other copy's stand-in instead of weights."""
    try:
        from modules import extensions
        return any(os.path.exists(os.path.join(ext.path, "scripts", "no_local_model.py"))
                   for ext in extensions.active())
    except Exception:
        return False


def script_setup():
    from modules import shared

    if not shared.opts.data.get("nai_api_lazy_model", True):
        return
    if _standalone_installed():
        print("[no-local-model] the standalone extension is installed and handles this; remove it to use the built-in one")
        return
    _patch()


def _patch():
    import modules.processing as processing
    import modules.sd_models as sd_models

    if getattr(sd_models.model_data.get_sd_model, "_no_local_model", False):
        return  # already patched in this process (Reload UI re-runs scripts)

    _orig["get_sd_model"] = sd_models.model_data.get_sd_model

    def get_sd_model():
        if _loading:
            return sd_models.model_data.sd_model
        return _real_model() or STUB

    get_sd_model._no_local_model = True
    sd_models.model_data.get_sd_model = get_sd_model

    if hasattr(sd_models, "reload_model_weights"):  # A1111 / Forge / reForge
        original = sd_models.reload_model_weights

        def reload_model_weights(*args, **kwargs):
            # only meaningful once something is loaded; otherwise stay lazy
            return original(*args, **kwargs) if _real_model() else STUB

        sd_models.reload_model_weights = reload_model_weights
        if hasattr(processing, "reload_model_weights"):
            processing.reload_model_weights = reload_model_weights

    if hasattr(processing, "forge_model_reload"):  # Forge Neo
        _orig["forge_model_reload"] = processing.forge_model_reload

        def forge_model_reload():
            if _real_model():
                return _orig["forge_model_reload"]()
            return STUB, False

        processing.forge_model_reload = forge_model_reload

    if hasattr(processing, "apply_circular_forge"):  # needs the real unet
        _orig["apply_circular_forge"] = processing.apply_circular_forge

        def apply_circular_forge(model, tiling_enabled=False, *args, **kwargs):
            global _pending_tiling
            if model is STUB:
                _pending_tiling = tiling_enabled  # replayed after the real load
                return None
            return _orig["apply_circular_forge"](model, tiling_enabled, *args, **kwargs)

        processing.apply_circular_forge = apply_circular_forge

    # A generation is in flight between these two - every path (UI, API, XYZ
    # plot) goes through the ScriptRunner instance, so wrapping the class works
    # where wrapping process_images does not (api.py imports it by name).
    import modules.scripts as scripts_module

    original_before_process = scripts_module.ScriptRunner.before_process

    def before_process(self, *args, **kwargs):
        global _generating
        _generating = True
        return original_before_process(self, *args, **kwargs)

    scripts_module.ScriptRunner.before_process = before_process

    if hasattr(scripts_module.ScriptRunner, "postprocess"):
        original_postprocess = scripts_module.ScriptRunner.postprocess

        def postprocess(self, *args, **kwargs):
            global _generating
            try:
                return original_postprocess(self, *args, **kwargs)
            finally:
                _generating = False

        scripts_module.ScriptRunner.postprocess = postprocess

    try:  # embeddings need a real text encoder
        from modules.sd_hijack import model_hijack

        db = model_hijack.embedding_db
        _orig["load_embeddings"] = db.load_textual_inversion_embeddings

        def load_textual_inversion_embeddings(*args, **kwargs):
            if _real_model():
                return _orig["load_embeddings"](*args, **kwargs)
            return None

        db.load_textual_inversion_embeddings = load_textual_inversion_embeddings
    except ImportError:
        pass

    print("[no-local-model] checkpoint loads on demand only")


if __name__ == "__main__":

    class Real:
        latent_channels = 4
        forge_objects = "unet"

    loaded = []
    _real_model = lambda: loaded[0] if loaded else None  # noqa: E731 - no webui here
    _orig["get_sd_model"] = lambda: (loaded.append(Real()), loaded[0])[1]

    # model family is read from the checkpoint header, not by loading it
    import json as _json
    import struct as _struct
    import tempfile as _tempfile

    _header = _json.dumps({"conditioner.embedders.1.model.x": {}}).encode()
    _fake = _tempfile.mktemp(suffix=".safetensors")
    with open(_fake, "wb") as _f:
        _f.write(_struct.pack("<Q", len(_header)) + _header)
    _fam = _read_family(_fake)
    assert _fam["is_sdxl"] and not _fam["is_sd1"] and not _fam["is_flux"]
    assert _read_family(__file__) is None  # not a safetensors file: don't guess
    os.remove(_fake)

    # the cheap questions processing.py asks before any script runs
    assert STUB.sd_checkpoint_info is None  # no webui here, so no checkpoint list
    assert STUB.sd_model_hash == ""
    assert STUB.is_wan is False
    assert not hasattr(STUB, "fix_dimensions")
    assert not hasattr(STUB, "_ipython_canary")
    STUB.comments = []
    STUB.extra_generation_params = {}
    assert loaded == []  # nothing loaded so far: a remote generation is free

    # outside a generation, nothing may pull weights in
    try:
        STUB.latent_channels
        raise SystemExit("should have refused")
    except AttributeError:
        pass
    assert loaded == []

    # the first question only real weights can answer, mid-generation
    _generating = True
    assert STUB.latent_channels == 4
    assert len(loaded) == 1
    print("ok")
