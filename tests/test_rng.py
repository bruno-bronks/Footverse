"""PCG32: determinismo e reprodutibilidade por chave (invariante das SPECs)."""

from footverse.engine.rng import Pcg32


def _sequence(rng, n=10):
    return [rng.next_u32() for _ in range(n)]


def test_same_key_same_sequence():
    a = Pcg32.from_key("SEASON_X", "club_123", "rod_05", "gol")
    b = Pcg32.from_key("SEASON_X", "club_123", "rod_05", "gol")
    assert _sequence(a) == _sequence(b)


def test_different_key_different_sequence():
    a = Pcg32.from_key("SEASON_X", "club_123", "rod_05", "gol")
    b = Pcg32.from_key("SEASON_X", "club_123", "rod_05", "assist")
    assert _sequence(a) != _sequence(b)


def test_outputs_are_u32():
    rng = Pcg32.from_key("seed")
    for v in _sequence(rng, 1000):
        assert 0 <= v <= 0xFFFFFFFF


def test_random_in_unit_interval():
    rng = Pcg32.from_key("seed")
    for _ in range(1000):
        u = rng.random()
        assert 0.0 <= u < 1.0


def test_random_open_excludes_endpoints():
    rng = Pcg32.from_key("seed")
    for _ in range(1000):
        u = rng.random_open()
        assert 0.0 < u < 1.0


def test_golden_snapshot():
    # snapshot congelado — falha se o algoritmo mudar (regressão cross-version)
    rng = Pcg32.from_key("SEASON_SECRET", "club_123", "rod_2026_05")
    assert _sequence(rng, 5) == GOLDEN


GOLDEN = [952784842, 2110119189, 1225227068, 1724039027, 763524499]
