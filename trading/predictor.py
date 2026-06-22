"""Adapter from :class:`KronosPredictor` to the backtest ``predict_fn`` API.

Loading the model needs PyTorch and the pretrained weights (Hugging Face hub or
a local path). The factory below returns a closure with the signature expected
by :func:`trading.backtest.run_walk_forward`.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

from .signals import SignalConfig, expected_return

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


def make_kronos_ensemble_predict_fn(
    predictor,
    n_samples: int = 10,
    T: float = 1.0,
    top_p: float = 0.9,
    top_k: int = 0,
    signal: SignalConfig | None = None,
):
    """Ensemble wrapper that also estimates forecast **confidence**.

    Runs the model ``n_samples`` times (each a stochastic single sample), returns
    the mean forecast, and attaches to ``df.attrs``:

    * ``confidence`` — fraction of sample paths whose direction agrees with the
      mean direction (1.0 = unanimous; ~0.5 = a coin toss). Use with
      ``TradeConfig.min_confidence`` to skip low-agreement signals.
    * ``exp_return_std`` — dispersion of the per-sample expected returns.

    Cost is ``n_samples`` × a normal forecast, so keep ``signal_every`` sensible.
    """
    sig = signal or SignalConfig()

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        df_in = ctx[["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
        x = pd.Series(x_ts).reset_index(drop=True)
        y = pd.Series(y_ts).reset_index(drop=True)
        last = float(ctx["close"].iloc[-1])

        paths, ers = [], []
        for _ in range(n_samples):
            p = predictor.predict(df=df_in, x_timestamp=x, y_timestamp=y, pred_len=pred_len,
                                  T=T, top_k=top_k, top_p=top_p, sample_count=1, verbose=False)
            pc = p["close"].to_numpy()
            paths.append(pc)
            ers.append(expected_return(pc, last, sig))

        mean_close = np.mean(paths, axis=0)
        ers = np.asarray(ers)
        mean_dir = np.sign(ers.mean()) if ers.mean() != 0 else 0
        confidence = float((np.sign(ers) == mean_dir).mean()) if mean_dir != 0 else 0.0

        out = pd.DataFrame({"open": mean_close, "high": mean_close, "low": mean_close,
                            "close": mean_close, "volume": 0.0, "amount": 0.0},
                           index=pd.Index(y.values, name="timestamps"))
        out.attrs["confidence"] = confidence
        out.attrs["exp_return_std"] = float(ers.std())
        return out

    return predict_fn
