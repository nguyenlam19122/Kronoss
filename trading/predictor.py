"""Adapter from :class:`KronosPredictor` to the backtest ``predict_fn`` API.

Loading the model needs PyTorch and the pretrained weights (Hugging Face hub or
a local path). The factory below returns a closure with the signature expected
by :func:`trading.backtest.run_walk_forward`.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

import pandas as pd

# Make the repo-root `model` package importable when run from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def load_kronos_predictor(
    model_name: str = "NeoQuasar/Kronos-small",
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-base",
    device: str | None = None,
    max_context: int = 512,
):
    """Load a :class:`KronosPredictor` from Hugging Face or local checkpoints.

    Args:
        model_name: HF id or local dir of the Kronos model.
        tokenizer_name: HF id or local dir of the matching tokenizer.
        device: ``"cuda:0"``, ``"cpu"``, ``"mps"`` or None (auto-detect).
        max_context: Maximum context length (512 for small/base).
    """
    from model import Kronos, KronosTokenizer, KronosPredictor  # heavy import

    tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
    model = Kronos.from_pretrained(model_name)
    return KronosPredictor(model, tokenizer, device=device, max_context=max_context)


def _predict(ctx, x_ts, y_ts, pred_len, predictor, T, top_p, top_k, sample_count):
    """Inner predict_fn bound to a configured KronosPredictor."""
    return predictor.predict(
        df=ctx[["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True),
        x_timestamp=pd.Series(x_ts).reset_index(drop=True),
        y_timestamp=pd.Series(y_ts).reset_index(drop=True),
        pred_len=pred_len,
        T=T,
        top_k=top_k,
        top_p=top_p,
        sample_count=sample_count,
        verbose=False,
    )


def make_kronos_predict_fn(
    predictor,
    T: float = 1.0,
    top_p: float = 0.9,
    top_k: int = 0,
    sample_count: int = 1,
):
    """Wrap a loaded ``KronosPredictor`` into a backtest-compatible ``predict_fn``.

    ``sample_count`` > 1 averages several sampled forecast paths, which markedly
    stabilises the directional signal at the cost of more inference time.
    """
    return partial(
        _predict,
        predictor=predictor,
        T=T,
        top_p=top_p,
        top_k=top_k,
        sample_count=sample_count,
    )
