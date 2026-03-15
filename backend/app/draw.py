"""
Rarity-weighted card draw. Uses RNG and configurable rarity weights so that
each draw first picks a rarity bucket by probability, then picks a random card
of that rarity from the set (with replacement across draws).
"""
import random
from collections import defaultdict

# Default weights: higher = more likely. Probabilities are normalized.
# Tuning: classic TCG-like distribution (commons dominate, legendaries rare).
DEFAULT_RARITY_WEIGHTS = {
    "common": 70,
    "uncommon": 20,
    "rare": 7,
    "ultra-rare": 2,
    "legendary": 1,
}


def _normalize_rarity(r: str) -> str:
    """Map DB rarity to canonical key for weighting."""
    if not (r or "").strip():
        return "common"
    s = (r or "").strip().lower().replace("_", "-").replace(" ", "-")
    if s in ("common", "uncommon", "rare", "legendary"):
        return s
    if s in ("ultrarare", "ultra-rare"):
        return "ultra-rare"
    # Unknown rarity: treat as common so it's still drawable
    return "common" if s not in DEFAULT_RARITY_WEIGHTS else s


def _group_cards_by_rarity(cards: list[dict]) -> dict[str, list[dict]]:
    """Group card dicts by normalized rarity. Each card must have 'rarity' and 'id'."""
    by_rarity: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        key = _normalize_rarity(c.get("rarity") or "common")
        by_rarity[key].append(c)
    return dict(by_rarity)


def _build_rarity_cumulative(weights: dict[str, float]) -> list[tuple[str, float]]:
    """Return [(rarity, cumulative_weight), ...] for binary-search style roll."""
    total = sum(weights.get(r, 0) for r in DEFAULT_RARITY_WEIGHTS)
    if total <= 0:
        total = 1
    cum = 0.0
    out = []
    for r in DEFAULT_RARITY_WEIGHTS:
        w = weights.get(r, DEFAULT_RARITY_WEIGHTS[r])
        cum += w
        out.append((r, cum / total))
    return out


def draw_cards(
    cards: list[dict],
    count: int,
    *,
    rng: random.Random | None = None,
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """
    Draw `count` cards from the set with rarity-weighted probability.

    - cards: list of card dicts (each with 'id', 'rarity', and any other fields).
    - count: number of draws (with replacement: same card can appear multiple times).
    - rng: optional Random instance (default: random.SystemRandom() for crypto-safe).
    - weights: optional rarity -> weight override; keys same as DEFAULT_RARITY_WEIGHTS.

    Algorithm:
    1. Group cards by normalized rarity.
    2. Build cumulative probability for each rarity from weights.
    3. For each of `count` draws:
       a. Roll U(0,1) and select rarity bucket.
       b. If that rarity has no cards in the set, fallback: pick uniformly from all cards.
       c. Otherwise pick one card uniformly at random from that rarity.
    4. Return the list of drawn card dicts (order = draw order).
    """
    if not cards or count <= 0:
        return []

    rng = rng or random.SystemRandom()
    w = dict(weights) if weights else {}
    for k, v in DEFAULT_RARITY_WEIGHTS.items():
        w.setdefault(k, v)

    by_rarity = _group_cards_by_rarity(cards)
    cumulative = _build_rarity_cumulative(w)
    all_cards = cards
    drawn: list[dict] = []

    for _ in range(count):
        roll = rng.random()
        chosen_rarity = cumulative[-1][0]
        for r, cum in cumulative:
            if roll <= cum:
                chosen_rarity = r
                break

        pool = by_rarity.get(chosen_rarity)
        if not pool:
            pool = all_cards
        card = rng.choice(pool)
        drawn.append(card)

    return drawn
