import pytest

from src.utils.actions import cycle_action


def test_cycle_action_normal():
    assert cycle_action("A", ["A", "B", "C"]) == "B"
    assert cycle_action("B", ["A", "B", "C"]) == "C"
    assert cycle_action("C", ["A", "B", "C"]) == "A"


def test_cycle_action_case_insensitivity():
    # current_action has different case
    assert cycle_action("MuTe", ["delete", "warn", "mute", "ban"]) == "ban"
    # list elements have different case
    assert cycle_action("warn", ["DeLEte", "wArN", "mUTe", "bAn"]) == "mUTe"


def test_cycle_action_not_in_list():
    assert cycle_action("Z", ["A", "B", "C"]) == "A"
    assert cycle_action("Z", ["A", "B", "C"], default_action="B") == "B"


def test_cycle_action_none_current():
    assert cycle_action(None, ["A", "B", "C"]) == "A"
    assert cycle_action(None, ["A", "B", "C"], default_action="C") == "C"
    assert cycle_action("", ["A", "B", "C"]) == "A"


def test_cycle_action_empty_list():
    with pytest.raises(ValueError, match="allowed_actions cannot be empty"):
        cycle_action("A", [])


def test_cycle_action_singleton_list():
    assert cycle_action("A", ["A"]) == "A"
    assert cycle_action("B", ["A"]) == "A"
    assert cycle_action("B", ["A"], default_action="C") == "C"


def test_cycle_action_preserves_case_of_next_element():
    # We should return the next action exactly as it appears in the original list
    assert cycle_action("lower", ["lower", "UPPER", "MiXeD"]) == "UPPER"
    assert cycle_action("upper", ["lower", "UPPER", "MiXeD"]) == "MiXeD"
    assert cycle_action("mixed", ["lower", "UPPER", "MiXeD"]) == "lower"
