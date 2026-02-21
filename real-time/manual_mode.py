"""Manual, keyboard-driven recording mode for the Aria real-time bridge.

This mode bypasses Ableton's MIDI clock and instead starts/stops recording
based on a user-selected computer keyboard key. The recorded MIDI is converted
into a prompt for Aria with timing preserved from the captured deltas.
"""

from __future__ import annotations

import logging
import os
import statistics
import threading
import time
from typing import Iterable, List, Optional, Tuple

try:
    from .midi_buffer import TimestampedMidiMsg
    from .prompt_midi import buffer_to_tempfile_midi
except Exception:  # pragma: no cover - fallback for script execution
    from midi_buffer import TimestampedMidiMsg
    from prompt_midi import buffer_to_tempfile_midi

logger = logging.getLogger(__name__)


class KeyboardToggle:
    """Minimal keyboard listener that works on Windows-first, with fallbacks.

    Preference order:
      1) `keyboard` package if installed (best for global hotkeys on Windows)
      2) `msvcrt` polling on Windows
      3) stdin blocking prompt as a last-resort
    """

    def __init__(self, key: str = "r"):
        self.key = key
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        try:
            import keyboard  # type: ignore  # noqa: F401
            return "keyboard"
        except Exception:
            if os.name == "nt":
                try:
                    import msvcrt  # type: ignore  # noqa: F401
                    return "msvcrt"
                except Exception:
                    return "stdin"
            return "stdin"

    def wait_for_press(self, message: str, cancel_event: threading.Event) -> bool:
        """Block until the configured key is pressed or cancel_event is set."""
        print(message)
        try:
            if self.backend == "keyboard":
                import keyboard  # type: ignore

                pressed = threading.Event()

                def _on_key(_):
                    pressed.set()

                hook = keyboard.on_press_key(self.key, _on_key, suppress=False)
                try:
                    while not cancel_event.is_set() and not pressed.is_set():
                        time.sleep(0.05)
                finally:
                    keyboard.unhook(hook)
                return pressed.is_set()

            if self.backend == "msvcrt":
                import msvcrt  # type: ignore
                while not cancel_event.is_set():
                    if msvcrt.kbhit():
                        ch = msvcrt.getwch()
                        if ch.lower() == self.key.lower():
                            return True
                    time.sleep(0.05)
                return False

            # Fallback: stdin prompt
            if cancel_event.is_set():
                return False
            input(f"{message} (press Enter to continue)")
            return True
        except KeyboardInterrupt:
            cancel_event.set()
            return False


def infer_bpm_from_onsets(messages: Iterable[TimestampedMidiMsg]) -> Optional[float]:
    """Estimate BPM from successive note_on timestamps (best-effort)."""
    onsets = [
        msg.timestamp
        for msg in messages
        if msg.msg_type == "note_on" and msg.velocity and msg.velocity > 0
    ]
    if len(onsets) < 2:
        return None

    deltas = [b - a for a, b in zip(onsets[:-1], onsets[1:]) if b > a]
    if not deltas:
        return None

    median_delta = statistics.median(deltas)
    if median_delta <= 0:
        return None

    bpm = 60.0 / median_delta
    return max(30.0, min(bpm, 240.0))


def _play_midi_file(midi_path: str, out_port) -> Tuple[int, float]:
    """Send a MIDI file to the output port preserving timing."""
    import mido

    mid = mido.MidiFile(midi_path)
    total_time = mid.length
    sent = 0

    for msg in mid.play():
        if hasattr(msg, "type") and msg.type in ("note_on", "note_off", "control_change"):
            out_port.send(msg)
            sent += 1

    return sent, total_time


class ManualModeSession:
    """Keyboard-driven record -> prompt -> generate -> play pipeline."""

    def __init__(
        self,
        in_port_name: str,
        out_port_name: str,
        aria_engine,
        manual_key: str = "r",
        ticks_per_beat: int = 480,
        temperature: float = 0.9,
        top_p: float = 0.95,
        min_p: Optional[float] = None,
        gen_seconds: float = 1.0,
        max_seconds: Optional[float] = None,
        max_bars: Optional[int] = None,
        beats_per_bar: int = 4,
        max_new_tokens: Optional[int] = None,
        play_key: Optional[str] = None,
    ):
        self.in_port_name = in_port_name
        self.out_port_name = out_port_name
        self.aria_engine = aria_engine
        self.manual_key = manual_key
        self.ticks_per_beat = ticks_per_beat
        self.temperature = temperature
        self.top_p = top_p
        self.min_p = min_p
        self.gen_seconds = gen_seconds
        self.max_seconds = max_seconds
        self.max_bars = max_bars
        self.beats_per_bar = beats_per_bar
        self.max_new_tokens = max_new_tokens
        self.play_key = play_key
        self.play_toggle = KeyboardToggle(play_key) if play_key else None

        self.cancel_event = threading.Event()
        self.recording_flag = threading.Event()
        self.recorded: List[TimestampedMidiMsg] = []
        self.start_time: Optional[float] = None
        self.stop_time: Optional[float] = None

        self.toggle = KeyboardToggle(manual_key)
        self.in_port = None
        self.out_port = None
        self.midi_thread = None

    def _open_ports(self) -> None:
        import mido
        self.in_port = mido.open_input(self.in_port_name)
        self.out_port = mido.open_output(self.out_port_name)
        logger.info(f"Manual mode ports opened: IN={self.in_port_name}, OUT={self.out_port_name}")

    def _close_ports(self) -> None:
        try:
            if self.in_port:
                self.in_port.close()
        finally:
            self.in_port = None
        try:
            if self.out_port:
                self.out_port.close()
        finally:
            self.out_port = None

    def _midi_loop(self) -> None:
        """Continuously poll input and buffer messages while recording_flag is set."""
        try:
            while not self.cancel_event.is_set():
                if self.in_port is None:
                    break
                for msg in self.in_port.iter_pending():
                    if not self.recording_flag.is_set():
                        continue
                    if msg.type not in ("note_on", "note_off", "control_change"):
                        continue
                    timestamp = time.monotonic()
                    data = {
                        "msg_type": msg.type,
                        "timestamp": timestamp,
                        "pulse": None,
                    }
                    if hasattr(msg, "note"):
                        data["note"] = msg.note
                    if hasattr(msg, "velocity"):
                        data["velocity"] = msg.velocity
                    if msg.type == "control_change":
                        data["control"] = msg.control
                        data["value"] = msg.value
                    self.recorded.append(TimestampedMidiMsg(**data))
                time.sleep(0.001)
        except Exception as e:
            logger.exception(f"Manual MIDI loop error: {e}")
            self.cancel_event.set()

    def _start_midi_thread(self) -> None:
        self.midi_thread = threading.Thread(target=self._midi_loop, daemon=True)
        self.midi_thread.start()

    def _await_stop_key(self) -> threading.Event:
        stop_evt = threading.Event()
        def _runner():
            self.toggle.wait_for_press(
                f"Recording... Press '{self.manual_key}' to STOP", stop_evt
            )
            stop_evt.set()
        threading.Thread(target=_runner, daemon=True).start()
        return stop_evt

    def run(self) -> int:
        """Run repeated record->generate cycles in manual mode until Ctrl+C."""
        try:
            self._open_ports()
            self._start_midi_thread()

            while not self.cancel_event.is_set():
                armed = self.toggle.wait_for_press(
                    f"Manual mode armed. Press '{self.manual_key}' to START recording.",
                    self.cancel_event,
                )
                if not armed:
                    logger.info("Manual mode canceled before start.")
                    break

                self.recorded.clear()
                self.recording_flag.set()
                self.start_time = time.monotonic()
                logger.info(f"[manual] Recording started at {self.start_time:.3f}")

                stop_key_event = threading.Event()
                def _watch_key():
                    self.toggle.wait_for_press(
                        f"Recording... Press '{self.manual_key}' again to STOP.", stop_key_event
                    )
                    stop_key_event.set()
                threading.Thread(target=_watch_key, daemon=True).start()

                if self.max_bars:
                    logger.info(
                        f"[manual] max-bars flag set to {self.max_bars}; will apply after tempo inference if possible."
                    )

                while not self.cancel_event.is_set():
                    now = time.monotonic()
                    if stop_key_event.is_set():
                        break
                    if self.max_seconds and self.start_time and (now - self.start_time) >= self.max_seconds:
                        logger.info(f"[manual] Max seconds reached ({self.max_seconds}s); stopping.")
                        break
                    time.sleep(0.02)

                self.recording_flag.clear()
                self.stop_time = time.monotonic()
                duration = (self.stop_time - self.start_time) if self.start_time else 0.0
                logger.info(f"[manual] Recording stopped at {self.stop_time:.3f} (duration={duration:.2f}s)")

                if not self.recorded:
                    logger.warning("[manual] No MIDI captured. Nothing to generate.")
                    logger.info(f"[manual] Ready for next take. Press '{self.manual_key}' to record, Ctrl+C to exit.")
                    continue

                bpm = infer_bpm_from_onsets(self.recorded)
                if bpm:
                    logger.info(f"[manual] Estimated BPM from onsets: {bpm:.2f}")
                    if self.max_bars:
                        max_duration = (60.0 / bpm) * self.beats_per_bar * self.max_bars
                        if duration > max_duration:
                            cutoff = (self.start_time or 0) + max_duration
                            original_len = len(self.recorded)
                            self.recorded = [m for m in self.recorded if m.timestamp <= cutoff]
                            duration = max_duration
                            logger.info(
                                f"[manual] Trimmed recording to {self.max_bars} bars "
                                f"({max_duration:.2f}s); kept {len(self.recorded)}/{original_len} events."
                            )
                else:
                    logger.info("[manual] Could not infer BPM; using default 120 BPM conversion.")

                prompt_midi_path = buffer_to_tempfile_midi(
                    messages=self.recorded,
                    window_seconds=duration,
                    current_bpm=bpm,
                    ticks_per_beat=self.ticks_per_beat,
                )

                prompt_ticks, prompt_seconds = self._midi_stats(prompt_midi_path)
                logger.info(
                    f"[manual] Prompt stats: events={len(self.recorded)}, "
                    f"duration={duration:.2f}s, midi_len={prompt_seconds:.2f}s, ticks={prompt_ticks}"
                )

                gen_start = time.time()
                generated_path = self.aria_engine.generate(
                    prompt_midi_path=prompt_midi_path,
                    prompt_duration_s=max(1, int(duration)),
                    horizon_s=self.gen_seconds,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    min_p=self.min_p,
                    max_new_tokens=self.max_new_tokens,
                )
                gen_time = time.time() - gen_start
                logger.info(f"[manual] Generation finished in {gen_time:.2f}s")

                if not generated_path:
                    logger.warning("[manual] Generation returned None; aborting playback.")
                    logger.info(f"[manual] Ready for next take. Press '{self.manual_key}' to record, Ctrl+C to exit.")
                    continue

                # Optional gated playback
                if self.play_toggle:
                    pressed = self.play_toggle.wait_for_press(
                        f"Press '{self.play_key}' to PLAY generated output, or Ctrl+C to quit.",
                        self.cancel_event,
                    )
                    if not pressed:
                        logger.info("[manual] Playback canceled.")
                        continue
                sent, total = _play_midi_file(generated_path, self.out_port)
                logger.info(f"[manual] Played generated MIDI ({sent} msgs, {total:.2f}s)")

                for tmp in (prompt_midi_path, generated_path):
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass

                logger.info(f"[manual] Ready for next take. Press '{self.manual_key}' to record, Ctrl+C to exit.")

            return 0

        except KeyboardInterrupt:
            logger.info("Manual mode interrupted by user.")
            return 0
        except Exception as e:
            logger.exception(f"Manual mode fatal error: {e}")
            return 1
        finally:
            self.cancel_event.set()
            if self.midi_thread and self.midi_thread.is_alive():
                self.midi_thread.join(timeout=1.0)
            self._close_ports()

    @staticmethod
    def _midi_stats(path: str) -> Tuple[int, float]:
        """Return total ticks and length (seconds) for a MIDI file."""
        import mido
        mid = mido.MidiFile(path)
        total_ticks = 0
        for track in mid.tracks:
            ticks = 0
            for msg in track:
                ticks += getattr(msg, "time", 0)
            total_ticks = max(total_ticks, ticks)
        return total_ticks, mid.length
