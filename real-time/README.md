# Aria Real-Time Bridge

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Real-time MIDI generation with the Aria music model—featuring **3 operational modes** to fit your workflow: **Clock-Synchronized**, **Manual Keyboard**, or **Max for Live**.

## Overview

The Aria Real-Time Bridge creates a live MIDI pipeline between Ableton Live (via loopMIDI) and the Aria deep learning model. Record a musical prompt, and the model instantly generates a continuation, which you can play back in sync with your track.

> **Aria Model**: A state-of-the-art music language model trained on symbolic MIDI data. For details, see [Aria GitHub](https://github.com/EleutherAI/aria).

---

## Table of Contents

1. [Installation](#installation)
2. [Three Operating Modes](#three-operating-modes)
   - [Option 1: Clock Mode](#option-1-clock-mode-ableton-synchronized)
   - [Option 2: Manual Mode](#option-2-manual-mode-keyboard-driven)
   - [Option 3: Manual + OSC / Max for Live](#option-3-manual-with-osc--max-for-live)
3. [CLI Reference](#cli-reference)
4. [Project Structure](#project-structure)
5. [Troubleshooting](#troubleshooting)
6. [Development](#development)

---

## Installation

### Prerequisites

- **Python 3.9+**
- **PyTorch 2.0+** (CUDA-enabled recommended for real-time performance)
- **mido** for MIDI I/O
- **loopMIDI** or equivalent virtual MIDI port software
- **Aria model checkpoint** (`.safetensors` format)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd aria/real-time

# Install dependencies
pip install -r requirements.txt

# Verify MIDI ports are available
python ableton_bridge.py --list-ports
```

---

## Three Operating Modes

### Option 1: Clock Mode (Ableton-Synchronized)

**Best for**: Live improvisation in Ableton with automatic, beat-locked generation.

In this mode, the bridge listens to **Ableton's MIDI clock** and synchronizes generation to measure boundaries. When you play a specified number of human measures, the model automatically generates a continuation and plays it back in perfect sync.

#### How It Works

1. Set up **two loopMIDI ports**: `ARIA_IN` (receives human input) and `ARIA_OUT` (sends generated MIDI).
2. Configure Ableton to send MIDI clock to `ARIA_CLOCK`.
3. Play your human pattern into `ARIA_IN` for the specified number of measures (default: 1).
4. Bridge detects the boundary and triggers generation.
5. Generated output plays automatically back to `ARIA_OUT`.

#### Script to Run

```bash
python ableton_bridge.py --mode clock --in ARIA_IN --out ARIA_OUT --clock_in ARIA_CLOCK
```

#### Clock Mode CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode` | `clock` / `manual` | `clock` | Operating mode |
| `--in` | `str` | `ARIA_IN` | Input MIDI port (human performance) |
| `--out` | `str` | `ARIA_OUT` | Output MIDI port (generated MIDI) |
| `--clock_in` | `str` | `ARIA_CLOCK` | MIDI clock input port (synchronized to Ableton tempo) |
| `--measures` | `int` | `2` | Number of measures per block (human + AI cycle) |
| `--beats_per_bar` | `int` | `4` | Time signature numerator (e.g., 4 for 4/4) |
| `--human_measures` | `int` | `1` | Number of human-played measures before generation triggers |
| `--gen_measures` | `int` | (same as `--measures`) | Number of measures for AI to generate |
| `--checkpoint` | `str` | `models/model-gen.safetensors` | Path to Aria `.safetensors` checkpoint |
| `--temperature` | `float` | `0.9` | Sampling temperature (0.1–2.0, higher = more random) |
| `--top_p` | `float` | `0.95` | Top-p (nucleus) sampling threshold (0.1–1.0) |
| `--min_p` | `float` | `None` | Minimum-p sampling (alternative threshold) |
| `--quantize` | flag | off | Quantize output to 1/16 note grid |
| `--device` | `cuda` / `cpu` | `cuda` | Inference device |
| `--list-ports` | flag | — | List available MIDI ports and exit |

#### Example: 4/4 Time, 2-Bar Blocks

```bash
python ableton_bridge.py \
  --mode clock \
  --in ARIA_IN \
  --out ARIA_OUT \
  --clock_in ARIA_CLOCK \
  --measures 2 \
  --beats_per_bar 4 \
  --human_measures 1 \
  --gen_measures 2 \
  --temperature 0.8 \
  --top_p 0.95
```

#### Live Keyboard Tweaks (Clock Mode)

While running, press these keys in the terminal for real-time sampling adjustments:

| Key | Action |
|-----|--------|
| `1` | Decrease temperature |
| `2` | Increase temperature |
| `3` | Decrease top-p |
| `4` | Increase top-p |
| `5` | Decrease min-p |
| `6` | Increase min-p |

---

### Option 2: Manual Mode (Keyboard-Driven)

**Best for**: Offline, step-by-step recording and generation without Ableton clock.

In this mode, you use your **keyboard** to start/stop recording. No MIDI clock is needed; the bridge timestamps each MIDI message and infers BPM from note onsets.

#### How It Works

1. Press the **record key** (default: `r`) to start capturing MIDI.
2. Play your musical idea into `ARIA_IN`.
3. Press the record key again to stop.
4. Bridge infers BPM, generates a continuation.
5. Press the **play key** (default: `p`) to hear the generated output.

#### Script to Run

```bash
python ableton_bridge.py --mode manual --in ARIA_IN --out ARIA_OUT
```

#### Manual Mode CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode` | `clock` / `manual` | — | **Must be** `manual` |
| `--in` | `str` | `ARIA_IN` | Input MIDI port |
| `--out` | `str` | `ARIA_OUT` | Output MIDI port |
| `--manual-key` | `str` | `r` | Keyboard key to toggle recording (start/stop) |
| `--play-key` | `str` | `p` | Keyboard key to trigger playback (optional) |
| `--max-seconds` | `float` | `None` | Maximum recording duration in seconds (safety limit) |
| `--max-bars` | `int` | `None` | Maximum recording duration in bars (requires BPM inference) |
| `--beats_per_bar` | `int` | `4` | Time signature numerator for max-bars calculation |
| `--checkpoint` | `str` | `models/model-gen.safetensors` | Aria checkpoint path |
| `--gen_seconds` | `float` | `1.0` | Duration of generated continuation (seconds) |
| `--temperature` | `float` | `0.9` | Sampling temperature |
| `--top_p` | `float` | `0.95` | Top-p sampling threshold |
| `--min_p` | `float` | `None` | Minimum-p sampling |
| `--max-new-tokens` | `int` | `None` | Token budget override (auto-computed if omitted) |
| `--device` | `cuda` / `cpu` | `cuda` | Inference device |
| `--list-ports` | flag | — | List available MIDI ports and exit |

#### Example: Custom Keys & Time Limit

```bash
python ableton_bridge.py \
  --mode manual \
  --in ARIA_IN \
  --out ARIA_OUT \
  --manual-key r \
  --play-key p \
  --max-seconds 10 \
  --gen_seconds 2.0 \
  --temperature 0.85
```

#### Terminal Keyboard Tweaks (Manual Mode)

Same hotkeys as Clock Mode:

| Key | Action |
|-----|--------|
| `1/2` | Decrease/Increase temperature |
| `3/4` | Decrease/Increase top-p |
| `5/6` | Decrease/Increase min-p |

---

### Option 3: Manual with OSC / Max for Live

**Best for**: Integration with Max for Live for hardware control or sophisticated UI workflows.

This mode combines **manual keyboard control with OSC (Open Sound Control)** for remote parameter adjustment via Max for Live devices or any OSC client.

#### How It Works

1. Run the bridge in **manual mode with OSC enabled**.
2. Load the included **Max for Live device** (`Live Max knobs.amxd`) into Ableton.
3. The device sends OSC messages to control:
   - `record` start/stop
   - `temperature`, `top_p`, `min_p` parameters
   - `play` output triggering
4. Receive real-time status and log messages back to Max.

#### Script to Run

```bash
python ableton_bridge.py \
  --mode manual \
  --m4l \
  --osc-host 127.0.0.1 \
  --osc-in-port 9000 \
  --osc-out-port 9001 \
  --in ARIA_IN \
  --out ARIA_OUT
```

#### Manual + OSC CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode` | `clock` / `manual` | — | **Must be** `manual` |
| `--m4l` | flag | off | Enable OSC server for Max for Live |
| `--osc-host` | `str` | `127.0.0.1` | OSC server host (localhost for local use) |
| `--osc-in-port` | `int` | `9000` | UDP port to listen for incoming OSC commands |
| `--osc-out-port` | `int` | `9001` | UDP port to send status/parameter updates |
| `--in` | `str` | `ARIA_IN` | Input MIDI port |
| `--out` | `str` | `ARIA_OUT` | Output MIDI port |
| `--manual-key` | `str` | `r` | Keyboard key (still available as backup) |
| `--play-key` | `str` | `p` | Keyboard play key (still available) |
| `--max-seconds`, `--max-bars`, `--gen_seconds`, `--temperature`, `--top_p`, `--min_p`, `--device` | — | — | Same as Manual Mode |

#### OSC Message Reference

**Incoming (from Max/Client → Bridge)**:

| Address | Payload | Purpose |
|---------|---------|---------|
| `/aria/record` | `1` or `0` | Start (`1`) or stop (`0`) recording + generate |
| `/aria/temp` | `float` 0.1–2.0 | Set sampling temperature |
| `/aria/top_p` | `float` 0.1–1.0 | Set top-p threshold |
| `/aria/min_p` | `float` 0.0–0.2 | Set min-p threshold |
| `/aria/play` | — | Trigger playback of last generation |
| `/aria/cancel` | — | Cancel current recording |
| `/aria/ping` | — | Request status snapshot |

**Outgoing (from Bridge → Max/Client)**:

| Address | Payload | Purpose |
|---------|---------|---------|
| `/aria/status` | `string` | Current status (e.g., "RECORDING", "GENERATING", "IDLE") |
| `/aria/params` | `[temp, top_p, min_p]` | Current sampling parameters |
| `/aria/log` | `string` | Event log message (e.g., "Recording started") |

#### Example: Max for Live Integration

1. **Open Ableton** and load the included `aria.als` (Ableton Live Set).
2. **Load the device**: Drag `Live Max knobs.amxd` into an empty MIDI track.
3. **Run the bridge**:
   ```bash
   python ableton_bridge.py --mode manual --m4l --in ARIA_IN --out ARIA_OUT
   ```
4. **Interact**: Use the Max device sliders and buttons to control generation.

#### Optional: Tkinter UI Panel

You can also enable a simple Tkinter control panel alongside any mode:

```bash
python ableton_bridge.py --mode manual --ui --in ARIA_IN --out ARIA_OUT
```

---

## CLI Reference

### Global Options

```
--checkpoint <path>   Path to Aria model checkpoint (default: models/model-gen.safetensors)
--device {cuda,cpu}   Inference device (default: cuda)
--list-ports          List available MIDI ports and exit
--help, -h            Show help message
```

### Mode Selection

```
--mode {clock,manual}  Operating mode (default: clock)
```

---

## Project Structure

```
real-time/
├── ableton_bridge.py       # Main entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── core/
│   ├── __init__.py
│   ├── aria_engine.py      # Aria model inference wrapper
│   ├── bridge_engine.py    # Core orchestration (MIDI I/O + generation)
│   ├── midi_buffer.py      # Rolling MIDI message buffer
│   ├── prompt_midi.py      # Buffer-to-MIDI conversion
│   ├── sampling_state.py   # Thread-safe parameter state
│   └── tempo_tracker.py    # MIDI clock tempo tracking
├── modes/
│   ├── __init__.py
│   ├── clock_mode.py       # Clock grid synchronization (from clock_grid.py)
│   ├── manual_mode.py      # Keyboard-driven manual mode
│   ├── osc_controller.py   # OSC server for Max for Live
│   └── sampling_hotkeys.py # Live keyboard parameter tweaks
├── ui/
│   ├── __init__.py
│   └── ui_panel.py         # Optional Tkinter UI
├── tools/
│   ├── __init__.py
│   ├── calibrate.py        # MIDI latency calibration
│   ├── sanity.py           # Testing & validation
│   └── osc_sanity.py       # OSC debugging
├── ableton/
│   ├── aria.als            # Ableton Live set with Max device
│   └── Live Max knobs.amxd # Max for Live device
└── tests/                  # Unit tests
```

---

## Troubleshooting

### MIDI Port Not Found

**Problem**: "Failed to open input port 'ARIA_IN'"

**Solution**:
1. Install **loopMIDI** (Windows) or equivalent.
2. Create virtual ports matching the names in your CLI.
3. Check available ports:
   ```bash
   python ableton_bridge.py --list-ports
   ```

### Generation is Slow

**Problem**: Generation takes > 2 seconds per bar.

**Solution**:
- Use `--device cuda` (requires CUDA-capable GPU).
- Reduce `--gen_seconds` or `--max-new-tokens` to lower generation budget.
- Check GPU availability:
  ```bash
  python -c "import torch; print(torch.cuda.is_available())"
  ```

### No MIDI Being Captured

**Problem**: Human MIDI on `ARIA_IN` is not appearing in the buffer.

**Solution**:
- In Ableton, verify the MIDI track's input is routed to `ARIA_IN`.
- Enable **Monitor** so input is heard (optional).
- Check that no other application is reading from `ARIA_IN` (can cause exclusive lock).

### OSC Not Working

**Problem**: Max device doesn't see OSC messages from the bridge.

**Solution**:
1. Verify the Max device is configured for ports 9000/9001 (or adjust with `--osc-in-port`/`--osc-out-port`).
2. Check firewall allows UDP on those ports.
3. Debug with:
   ```bash
   python tools/osc_sanity.py --in-port 9000 --out-port 9001
   ```

---

## Development

### Running Tests

```bash
pytest tests/
```

### Code Organization

- **Core**: Model inference, MIDI I/O, buffering, synchronization.
- **Modes**: Independent operation modes (clock, manual, OSC).
- **UI**: Optional interfaces (Tkinter, Max for Live).
- **Tools**: Debugging and calibration utilities.

### Adding a New Mode

1. Create a new file in `modes/` (e.g., `my_mode.py`).
2. Implement a class or function that accepts `aria_engine`, `midi_buffer`, and other shared state.
3. Import and instantiate in `ableton_bridge.py`.
4. Add CLI arguments for the new mode.

---

## Disclaimer

This project uses the **Aria model**, a pre-trained music language model. Generated MIDI is provided as-is. Always verify copyright and licensing for any generated content in commercial use.

---

## License

[See LICENSE file](LICENSE)

---

## Contact & Support

For issues, feature requests, or contributions:
- Open an **Issue** on GitHub.
- Check the **Troubleshooting** section above.
- Review logs for detailed error messages.

---