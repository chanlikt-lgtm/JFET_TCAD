"""Numerically stable Bernoulli functions for Scharfetter-Gummel discretization.

Bernoulli function B(x) = x / (exp(x) - 1).
Essential for semiconductor drift-diffusion stability across high electric fields.
"""
import numpy as np

def bernoulli(x: np.ndarray) -> np.ndarray:
    """Evaluate B(x) = x / (exp(x) - 1) stably for scalar or array inputs."""
    x = np.asarray(x, dtype=np.float64)
    res = np.empty_like(x)

    # Near zero: high-precision Taylor series expansion to avoid 0/0
    small = np.abs(x) < 1e-4
    if np.any(small):
        xs = x[small]
        # B(x) = 1 - x/2 + x^2/12 - x^4/720 + x^6/30240
        x2 = xs * xs
        res[small] = 1.0 - 0.5 * xs + x2 * (1.0 / 12.0 - x2 * (1.0 / 720.0 - x2 / 30240.0))

    # Large negative: x / (exp(x) - 1) ~ -x
    large_neg = x < -80.0
    if np.any(large_neg):
        res[large_neg] = -x[large_neg]

    # Large positive: x / (exp(x) - 1) ~ x * exp(-x) -> 0
    large_pos = x > 80.0
    if np.any(large_pos):
        res[large_pos] = x[large_pos] * np.exp(-x[large_pos])

    # Normal range
    normal = (~small) & (~large_neg) & (~large_pos)
    if np.any(normal):
        xn = x[normal]
        res[normal] = xn / (np.expm1(xn))

    return res

def bernoulli_pair(dpsi_over_vt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute (B(eta), B(-eta)) simultaneously and stably.

    Note that B(-eta) = B(eta) + eta.
    """
    eta = np.asarray(dpsi_over_vt, dtype=np.float64)
    bp = bernoulli(eta)
    bm = bp + eta
    return bp, bm
