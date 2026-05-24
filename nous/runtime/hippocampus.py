"""Hippocampus — Hopfield-based shared episodic memory.

Stores 2D state arrays (e.g. flat representations of agent contexts) into a
bipolar Hopfield network. Direct mode (M=H*W) gives high recall fidelity;
random projection mode trades capacity for memory.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np


class Hippocampus:
    """Hopfield episodic memory.

    Parameters
    ----------
    H, W : int
        Grid dimensions used for encode/decode.
    M : int, optional
        Hopfield dimension. Defaults to H*W (no compression).
    threshold : float
        Threshold for binarizing continuous states.
    seed : int
        RNG seed for the (optional) random projection matrix.
    """

    def __init__(self, *, H: int, W: int, M: int | None = None,
                 threshold: float = 0.5, seed: int = 0):
        self.H = H
        self.W = W
        self.HW = H * W
        self.M = self.HW if M is None else M
        self.threshold = threshold
        self.use_projection = (self.M != self.HW)
        rng = np.random.default_rng(seed)
        if self.use_projection:
            self.P = rng.choice([-1.0, 1.0],
                                 size=(self.M, self.HW)).astype(np.float64)
        else:
            self.P = None
        self.W_hop = np.zeros((self.M, self.M), dtype=np.float64)
        self.patterns: list[np.ndarray] = []
        self.tags: dict[str, list[int]] = defaultdict(list)

    def encode(self, state2d: np.ndarray) -> np.ndarray:
        if tuple(state2d.shape) != (self.H, self.W):
            raise ValueError(
                f'state shape {state2d.shape} != ({self.H},{self.W})')
        flat = state2d.flatten().astype(np.float64)
        if self.use_projection:
            f = flat - flat.mean()
            return np.where(self.P @ f >= 0, 1.0, -1.0)
        return np.where(flat >= self.threshold, 1.0, -1.0)

    def decode(self, pattern: np.ndarray) -> np.ndarray:
        if tuple(pattern.shape) != (self.M,):
            raise ValueError(
                f'pattern shape {pattern.shape} != ({self.M},)')
        if self.use_projection:
            flat = self.P.T @ pattern
            flat = flat - flat.min()
            if flat.max() > 0:
                flat = flat / flat.max()
            return flat.reshape(self.H, self.W)
        return ((pattern + 1.0) * 0.5).reshape(self.H, self.W)

    def store(self, tag: str, state2d: np.ndarray) -> int:
        pat = self.encode(state2d)
        idx = len(self.patterns)
        self.patterns.append(pat)
        self.tags[tag].append(idx)
        self.W_hop += np.outer(pat, pat)
        np.fill_diagonal(self.W_hop, 0.0)
        return idx

    def recall(self, tag: str | None, cue2d: np.ndarray,
               n_iter: int = 10,
               restrict_to_tag: bool = True) -> np.ndarray:
        cue = self.encode(cue2d)
        if tag is not None and restrict_to_tag:
            ids = self.tags.get(tag, [])
            if not ids:
                return self.decode(cue)
            P_sub = np.stack([self.patterns[i] for i in ids], axis=0)
            W = P_sub.T @ P_sub
            np.fill_diagonal(W, 0.0)
        else:
            W = self.W_hop
        s = cue.copy()
        for _ in range(n_iter):
            new = np.where(W @ s >= 0, 1.0, -1.0)
            if np.array_equal(new, s):
                break
            s = new
        return self.decode(s)

    def cross_search(self, cue2d: np.ndarray,
                     top_k: int = 3) -> list[tuple[str, int, float]]:
        if not self.patterns:
            return []
        cue = self.encode(cue2d)
        all_pats = np.stack(self.patterns, axis=0)
        scores = (all_pats @ cue) / self.M
        idx_to_tag = {}
        for tag, ids in self.tags.items():
            for i in ids:
                idx_to_tag[i] = tag
        order = np.argsort(-scores)[:top_k]
        return [(idx_to_tag.get(int(i), '?'), int(i), float(scores[i]))
                for i in order]

    def reset(self) -> None:
        self.W_hop[:] = 0.0
        self.patterns.clear()
        self.tags.clear()

    @property
    def n_patterns(self) -> int:
        return len(self.patterns)

    @property
    def capacity_estimate(self) -> int:
        return int(0.14 * self.M)
