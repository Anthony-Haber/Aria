# Real-Time Ableton Bridge (Aria)

Live MIDI bridge between Ableton/loopMIDI and the Aria model.

## Quick start
```powershell
cd real-time
python ableton_bridge.py --mode manual --in ARIA_IN --out ARIA_OUT
```

Optional UI panel:
```powershell
python ableton_bridge.py --mode manual --ui --manual-key r --play-key p --in ARIA_IN --out ARIA_OUT
```

## Common CLI flags
- `--mode {clock,manual}`: Bridge mode (`clock` default).
- `--in`, `--out`: MIDI input/output port names.
- `--clock_in`: MIDI clock port (default `ARIA_CLOCK`) for clock mode.
- `--checkpoint`: Path to model checkpoint (`.safetensors`).
- `--listen_seconds`: Human listen window (clock mode buffer).
- `--gen_seconds`: Generation horizon (seconds).
- `--cooldown_seconds`: Cooldown after generation.
- `--measures`, `--beats_per_bar`, `--gen_measures`, `--human_measures`: Bar-based settings (clock mode).
- `--quantize`: Quantize generated output to 1/16 grid.
- `--ticks_per_beat`: MIDI PPQ (default 480).
- `--temperature`, `--top_p`, `--min_p`: Sampling params (live adjustable via hotkeys 1–6).
- `--max-new-tokens`: Override token budget.
- `--manual-key`: Keyboard toggle for record start/stop (manual mode).
- `--play-key`: Keyboard to trigger playback of last generation.
- `--max-seconds`, `--max-bars`: Safety caps for recording (manual).
- `--ui`: Launch optional Tkinter panel.
- `--list-ports`: List available MIDI ports and exit.
- `--device {cuda,cpu}`: Inference device (default cuda).

## Keyboard & hotkeys
- Record toggle: `r` (manual mode)
- Play last: `p` (when `--play-key` or UI enabled)
- Sampling tweaks (terminal & UI):  
  `1/2` temp -/+ , `3/4` top_p -/+ , `5/6` min_p -/+

## File layout (real-time/)
- `ableton_bridge.py` – CLI entrypoint & wiring
- `bridge_engine.py` – clock-mode orchestration
- `manual_mode.py` – manual record/generate/play loop
- `sampling_state.py` – shared sampling + session state
- `sampling_hotkeys.py` – non-blocking hotkeys
- `ui_panel.py` – optional Tkinter control panel (main-thread)
- Helpers: `midi_buffer.py`, `prompt_midi.py`, `clock_grid.py`, `tempo_tracker.py`, `aria_engine.py`

## Requirements
- Windows, Python 3.11+, loopMIDI, Ableton Live
- Optional: NVIDIA GPU with CUDA

## Ableton routing
- Create loopMIDI ports: `ARIA_IN`, `ARIA_OUT`, `ARIA_CLOCK`
- In Ableton MIDI prefs, enable **Sync** for `ARIA_CLOCK`
- Route keyboard/track -> `ARIA_IN`; route `ARIA_OUT` to your instrument track

## Troubleshooting
- Ports missing: `python ableton_bridge.py --list-ports`
- CUDA missing: use `--device cpu`
- Checkpoint missing: pass full path with `--checkpoint`
