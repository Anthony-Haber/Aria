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
import queue
from typing import Iterable, List, Optional, Tuple

try:
    from .midi_buffer import TimestampedMidiMsg
    from .prompt_midi import buffer_to_tempfile_midi
except Exception:  # pragma: no cover - fallback for script execution
    from midi_buffer import TimestampedMidiMsg
    from prompt_midi import buffer_to_tempfile_midi

logger = logging.getLogger(__name__)


class KeyboardToggle:
    """Minimal keyboard listener that works on Windows-first, with fallbacks."""

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
            if cancel_event.is_set():
                return False
            input(f"{message} (press Enter to continue)")
            return True
        except KeyboardInterrupt:
            cancel_event.set()
            return False


def infer_bpm_from_onsets(messages: Iterable[TimestampedMidiMsg]) -> Optional[float]:
    onsets = [m.timestamp for m in messages if m.msg_type == "note_on" and m.velocity and m.velocity > 0]
    if len(onsets) < 2:
        return None
    deltas = [b - a for a, b in zip(onsets[:-1], onsets[1:]) if b > a]
    if not deltas:
        return None
    bpm = 60.0 / statistics.median(deltas)
    return max(30.0, min(bpm, 240.0))


def _play_midi_file(midi_path: str, out_port) -> Tuple[int, float]:
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
        gen_seconds: float = 1.0,
        max_seconds: Optional[float] = None,
        max_bars: Optional[int] = None,
        beats_per_bar: int = 4,
        max_new_tokens: Optional[int] = None,
        play_key: Optional[str] = None,
        sampling_state=None,
        command_queue: Optional[queue.Queue] = None,
        log_queue: Optional[queue.Queue] = None,
        session_state=None,
    ):
        self.in_port_name = in_port_name
        self.out_port_name = out_port_name
        self.aria_engine = aria_engine
        self.manual_key = manual_key
        self.ticks_per_beat = ticks_per_beat
        self.gen_seconds = gen_seconds
        self.max_seconds = max_seconds
        self.max_bars = max_bars
        self.beats_per_bar = beats_per_bar
        self.max_new_tokens = max_new_tokens
        self.play_key = play_key
        self.play_toggle = KeyboardToggle(play_key) if play_key else None
        self.sampling_state = sampling_state
        self.command_queue = command_queue
        self.log_queue = log_queue
        self.session_state = session_state

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
                    data = {"msg_type": msg.type, "timestamp": timestamp, "pulse": None}
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

    def _drain_commands(self, stop_key_event: threading.Event):
        if not self.command_queue:
            return
        try:
            while True:
                cmd, payload = self.command_queue.get_nowait()
                if cmd == "toggle_record":
                    if self.recording_flag.is_set():
                        stop_key_event.set()
                    else:
                        self._start_immediate_record(stop_key_event)
                elif cmd == "play_last":
                    if self.session_state and self.session_state.last_output_path and self.out_port:
                        self._log_ui("Playing last output (UI)")
                        _play_midi_file(self.session_state.last_output_path, self.out_port)
                self.command_queue.task_done()
        except queue.Empty:
            pass

    def _start_immediate_record(self, stop_key_event: threading.Event):
        if self.recording_flag.is_set():
            return
        self.recorded.clear()
        self.recording_flag.set()
        self.start_time = time.monotonic()
        if self.session_state:
            self.session_state.set_status("RECORDING")
        self._log_ui("Recording started (UI)")
        def _wait_stop():
            while not self.cancel_event.is_set():
                try:
                    cmd, _ = self.command_queue.get(timeout=0.1)
                    if cmd == "toggle_record":
                        stop_key_event.set()
                        break
                except queue.Empty:
                    continue
        threading.Thread(target=_wait_stop, daemon=True).start()

    def _log_ui(self, msg: str):
        if self.log_queue:
            ts = time.strftime("%H:%M:%S")
            self.log_queue.put(f"[{ts}] {msg}")

    def run(self) -> int:
        try:
            self._open_ports()
            self._start_midi_thread()

            while not self.cancel_event.is_set():
                stop_key_event = threading.Event()

                # Wait for either keyboard start or UI toggle_record
                start_evt = threading.Event()

                def _wait_keyboard_start():
                    if self.toggle.wait_for_press(
                        f"Manual mode armed. Press '{self.manual_key}' to START recording.",
                        self.cancel_event,
                    ):
                        start_evt.set()

                threading.Thread(target=_wait_keyboard_start, daemon=True).start()

                while not self.cancel_event.is_set() and not start_evt.is_set():
                    self._drain_commands(stop_key_event)
                    if self.recording_flag.is_set():
                        start_evt.set()
                        break
                    time.sleep(0.05)

                armed = start_evt.is_set() or self.recording_flag.is_set()
                if not armed:
                    logger.info("Manual mode canceled before start.")
                    break

                self.recorded.clear()
                self.recording_flag.set()
                self.start_time = time.monotonic()
                logger.info(f"[manual] Recording started at {self.start_time:.3f}")
                self._log_ui("Recording started")
                if self.session_state:
                    self.session_state.set_status("RECORDING")

                stop_key_event = threading.Event()
                threading.Thread(
                    target=lambda: (self.toggle.wait_for_press(
                        f"Recording... Press '{self.manual_key}' again to STOP.", stop_key_event), stop_key_event.set()),
                    daemon=True,
                ).start()

                if self.max_bars:
                    logger.info(f"[manual] max-bars flag set to {self.max_bars}; will apply after tempo inference if possible.")

                while not self.cancel_event.is_set():
                    self._drain_commands(stop_key_event)
                    now = time.monotonic()
                    if stop_key_event.is_set():
                        break
                    if self.max_seconds and self.start_time and (now - self.start_time) >= self.max_seconds:
                        logger.info(f"[manual] Max seconds reached ({self.max_seconds}s); stopping.")
                        stop_key_event.set()
                        break
                    time.sleep(0.02)

                self.recording_flag.clear()
                self.stop_time = time.monotonic()
                duration = (self.stop_time - self.start_time) if self.start_time else 0.0
                logger.info(f"[manual] Recording stopped at {self.stop_time:.3f} (duration={duration:.2f}s)")
                self._log_ui("Recording stopped")
                if self.session_state:
                    self.session_state.set_status("GENERATING")

                if not self.recorded:
                    logger.warning("[manual] No MIDI captured. Nothing to generate.")
                    self._log_ui("No MIDI captured")
                    if self.session_state:
                        self.session_state.set_status("IDLE")
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
                                f"[manual] Trimmed recording to {self.max_bars} bars ({max_duration:.2f}s); kept {len(self.recorded)}/{original_len} events."
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
                    f"[manual] Prompt stats: events={len(self.recorded)}, duration={duration:.2f}s, midi_len={prompt_seconds:.2f}s, ticks={prompt_ticks}"
                )

                gen_start = time.time()
                temp, top_p, min_p = self.sampling_state.get_values() if self.sampling_state else (0.9, 0.95, None)
                self._log_ui(
                    f"Generating with temp={temp:.2f} top_p={top_p:.2f} min_p={min_p if min_p is not None else 0.0:.2f}"
                )
                generated_path = self.aria_engine.generate(
                    prompt_midi_path=prompt_midi_path,
                    prompt_duration_s=max(1, int(duration)),
                    horizon_s=self.gen_seconds,
                    temperature=temp,
                    top_p=top_p,
                    min_p=min_p,
                    max_new_tokens=self.max_new_tokens,
                )
                gen_time = time.time() - gen_start
                logger.info(f"[manual] Generation finished in {gen_time:.2f}s")
                if self.session_state:
                    self.session_state.set_status("PLAYING")

                if not generated_path:
                    logger.warning("[manual] Generation returned None; aborting playback.")
                    self._log_ui("Generation returned None")
                    if self.session_state:
                        self.session_state.set_status("IDLE")
                    continue

                if self.play_toggle:
                    pressed = self.play_toggle.wait_for_press(
                        f"Press '{self.play_key}' to PLAY generated output, or Ctrl+C to quit.",
                        self.cancel_event,
                    )
                    if not pressed:
                        logger.info("[manual] Playback canceled.")
                        self._log_ui("Playback canceled")
                        continue

                sent, total = _play_midi_file(generated_path, self.out_port)
                logger.info(f"[manual] Played generated MIDI ({sent} msgs, {total:.2f}s)")
                self._log_ui(f"Played generated MIDI ({sent} msgs, {total:.2f}s)")
                if self.session_state:
                    self.session_state.set_last_output(generated_path)
                else:
                    try:
                        os.unlink(generated_path)
                    except Exception:
                        pass
                try:
                    os.unlink(prompt_midi_path)
                except Exception:
                    pass

                if self.session_state:
                    self.session_state.set_status("IDLE")

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
        import mido
        mid = mido.MidiFile(path)
        total_ticks = 0
        for track in mid.tracks:
            ticks = 0
            for msg in track:
                ticks += getattr(msg, "time", 0)
            total_ticks = max(total_ticks, ticks)
        return total_ticks, mid.length
