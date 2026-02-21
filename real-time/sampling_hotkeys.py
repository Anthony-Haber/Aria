"""Non-blocking keyboard listener to tweak sampling parameters on the fly."""

import logging
import threading
import time

logger = logging.getLogger(__name__)


def start_sampling_hotkeys(sampling_state, stop_event: threading.Event):
    """
    Start a daemon thread listening for sampling hotkeys.
    Keys: 1/2 temp -/+ , 3/4 top_p -/+ , 5/6 min_p -/+
    """
    t = threading.Thread(
        target=_listener_loop, args=(sampling_state, stop_event), daemon=True
    )
    t.start()
    return t


def _listener_loop(sampling_state, stop_event: threading.Event):
    try:
        import keyboard  # type: ignore

        def on_key(event):
            if stop_event.is_set():
                return
            name = event.name.upper()
            _maybe_handle(name, sampling_state)

        hook = keyboard.on_press(on_key)
        logger.info("Sampling hotkeys active (1/2 temp, 3/4 top_p, 5/6 min_p)")
        while not stop_event.is_set():
            time.sleep(0.1)
        keyboard.unhook(hook)
        return
    except Exception:
        pass  # fall back to msvcrt / polling

    # Fallback for Windows without keyboard lib
    try:
        import msvcrt  # type: ignore

        logger.info("Sampling hotkeys (msvcrt): 1/2 temp, 3/4 top_p, 5/6 min_p")
        while not stop_event.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                _maybe_handle(ch.upper(), sampling_state)
            time.sleep(0.05)
        return
    except Exception:
        logger.warning("Sampling hotkeys disabled (no keyboard backend available)")
        return


def _maybe_handle(key: str, sampling_state):
    if key == "2":
        val = sampling_state.increase_temperature()
    elif key == "1":
        val = sampling_state.decrease_temperature()
    elif key == "4":
        val = sampling_state.increase_top_p()
    elif key == "3":
        val = sampling_state.decrease_top_p()
    elif key == "6":
        val = sampling_state.increase_min_p()
    elif key == "5":
        val = sampling_state.decrease_min_p()
    else:
        return
    t, tp, mp = sampling_state.get_values()
    logger.info(f"[SAMPLING] temp={t:.2f} top_p={tp:.2f} min_p={mp:.2f}")
