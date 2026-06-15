from robot_tyapa.robot.petoi_commands import PETOI_COMMANDS


def test_commands_non_empty():
    assert len(PETOI_COMMANDS) > 0


def test_all_keys_and_values_are_non_empty_strings():
    for key, value in PETOI_COMMANDS.items():
        assert isinstance(key, str) and key, f"empty key: {key!r}"
        assert isinstance(value, str) and value, f"empty description for {key!r}"


def test_no_duplicate_keys():
    keys = list(PETOI_COMMANDS.keys())
    assert len(keys) == len(set(keys))
