from __future__ import annotations

import logging
import os
import warnings
import inspect

_RUNTIME_CONFIGURED = False


def _patch_websockets_connect_compat() -> None:
    """
    Deepgram 3.2.x still passes `extra_headers=` to websockets.connect(),
    while websockets 16 renamed that argument to `additional_headers=`.
    Patch the runtime once so live STT keeps working without downgrading
    packages manually on the user machine.
    """
    try:
        import websockets

        connect = getattr(websockets, "connect", None)
        if connect is None:
            return

        signature = inspect.signature(connect)
        parameters = signature.parameters
        if "additional_headers" not in parameters or "extra_headers" in parameters:
            return
        if getattr(connect, "__codex_compat_patch__", False):
            return

        def connect_compat(*args, extra_headers=None, **kwargs):
            if extra_headers is not None and "additional_headers" not in kwargs:
                kwargs["additional_headers"] = extra_headers
            kwargs.setdefault("open_timeout", 30)
            kwargs.setdefault("close_timeout", 10)
            return connect(*args, **kwargs)

        connect_compat.__codex_compat_patch__ = True
        websockets.connect = connect_compat
    except Exception:
        pass


def configure_runtime_verbosity() -> None:
    global _RUNTIME_CONFIGURED
    if _RUNTIME_CONFIGURED:
        return

    # TensorFlow reads these at import time, so they must be set early.
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

    _patch_websockets_connect_compat()

    warnings.filterwarnings(
        "ignore",
        message=r".*tf\.losses\.sparse_softmax_cross_entropy is deprecated.*",
    )

    for logger_name in ("tensorflow", "absl", "transformers", "huggingface_hub"):
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    try:
        from absl import logging as absl_logging

        absl_logging.set_verbosity(absl_logging.ERROR)
        absl_logging.set_stderrthreshold("error")
    except Exception:
        pass

    _RUNTIME_CONFIGURED = True
