"""Pytest checks for measure math and event windowing."""


def test_measures_timing():
    ppqn = 24
    test_cases = [
        (4, 1, 96),
        (4, 2, 192),
        (4, 3, 288),
        (4, 4, 384),
        (3, 1, 72),
        (3, 4, 288),
        (4, 8, 768),
    ]

    for beats_per_bar, measures, expected_pulses in test_cases:
        pulses_per_bar = beats_per_bar * ppqn
        actual_pulses = measures * pulses_per_bar
        assert actual_pulses == expected_pulses


def test_event_filtering_window():
    beats_per_bar = 4
    ppqn = 24
    pulses_per_bar = beats_per_bar * ppqn
    gen_measures = 4
    max_offset_pulses = gen_measures * pulses_per_bar

    test_events = [0, 50, 96, 192, 288, 350, 383, 384, 385, 500]
    expected_keep = [True, True, True, True, True, True, True, False, False, False]

    for offset_pulses, keep in zip(test_events, expected_keep):
        assert (offset_pulses < max_offset_pulses) is keep