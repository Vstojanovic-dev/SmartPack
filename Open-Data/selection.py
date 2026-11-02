"""Izbira druge občine za primerjavo na grafu."""

from collections.abc import Sequence


def second_municipality_selection(
    municipalities: Sequence[str],
    first: str,
    selected_second: str | None,
    previous_first: str | None,
    ranking: Sequence[str],
) -> str:
    """Ohrani drugo občino, če je še veljavna in različna od prve.

    Če prvo občino spremenimo v trenutno drugo, uporabimo prejšnjo prvo
    (zamenjava vlog). Ob začetnem izboru predlagamo občino z lestvice.
    """
    if selected_second in municipalities and selected_second != first:
        return selected_second
    if (selected_second == first and previous_first in municipalities
            and previous_first != first):
        return previous_first
    return next(
        name for name in (*ranking, *municipalities) if name in municipalities and name != first
    )
