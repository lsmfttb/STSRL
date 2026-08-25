import pytest

from sts_combat_rl.sim.sharding import contiguous_ranges


def test_contiguous_ranges_balances_records_without_gaps() -> None:
    assert contiguous_ranges(5, shards=3) == ("0:2", "2:4", "4:5")


@pytest.mark.parametrize(
    ("count", "shards"),
    [(True, 3), (-1, 3), (3, 0), (3, True)],
)
def test_contiguous_ranges_rejects_invalid_configuration(count, shards) -> None:
    with pytest.raises(ValueError):
        contiguous_ranges(count, shards)
