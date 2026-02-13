"""Pytest checks for ClockGrid math."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clock_grid import ClockGrid


def test_pulse_counts_4_4():
    grid = ClockGrid(clock_port_name="ARIA_CLOCK", measures=2, beats_per_bar=4)
    assert grid.get_pulses_per_bar() == 96
    assert grid.get_pulses_per_block() == 192


def test_pulse_counts_3_4():
    grid = ClockGrid(clock_port_name="ARIA_CLOCK", measures=3, beats_per_bar=3)
    assert grid.get_pulses_per_bar() == 72
    assert grid.get_pulses_per_block() == 216