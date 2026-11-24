from tyapa_protocol.commands import GAITS, PETOI_COMMANDS


def test_commands_non_empty():
    assert len(PETOI_COMMANDS) > 0


def test_all_keys_and_values_are_non_empty_strings():
    for key, value in PETOI_COMMANDS.items():
        assert isinstance(key, str), f"bad key: {key!r}"
        assert key, "empty key"
        assert isinstance(value, str), f"bad description for {key!r}"
        assert value, f"empty description for {key!r}"


def test_no_duplicate_keys():
    keys = list(PETOI_COMMANDS.keys())
    assert len(keys) == len(set(keys))


def test_gaits_are_a_subset_of_commands():
    assert GAITS
    assert set(PETOI_COMMANDS.keys()) >= GAITS
