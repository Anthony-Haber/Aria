# Real-Time Ableton Bridge (Aria)

A compact real-time MIDI bridge between Ableton Live and Aria.
It reads live input from a loopMIDI port, generates continuations with Aria,
and sends the output back to Ableton in sync with MIDI clock.

## Requirements
- Windows
- Python 3.11+
- Ableton Live
- loopMIDI
- Optional: NVIDIA GPU with CUDA (recommended)

## Installation
```powershell
cd real-time
.\.venv\Scripts\Activate.ps1
pip install -e "..[real-time]"
```

## Ableton Routing
- Create loopMIDI ports: `ARIA_IN`, `ARIA_OUT`, `ARIA_CLOCK`
- In Ableton MIDI preferences, enable **Sync** for `ARIA_CLOCK`
- Route your keyboard/track output to `ARIA_IN`
- Route the generated output from `ARIA_OUT` to your instrument track

## Run
```powershell
python ableton_bridge.py --device cuda --checkpoint "C:\path\to\model.safetensors"
```

To confirm GPU availability, run `python sanity.py` and verify CUDA is reported as available.

## CLI Options
- `--in`: Input MIDI port name (default: `ARIA_IN`)
- `--out`: Output MIDI port name (default: `ARIA_OUT`)
- `--checkpoint`: Path to the `.safetensors` checkpoint (default: `aria-medium-gen`)
- `--listen_seconds`: Human listening window in seconds (default: 4.0)
- `--gen_seconds`: Continuation duration in seconds (default: 1.0)
- `--cooldown_seconds`: Cooldown after generation in seconds (default: 0.2)
- `--clock_in`: MIDI clock input port (default: `ARIA_CLOCK`)
- `--measures`: Measures per human/model block (default: 2)
- `--beats_per_bar`: Time signature numerator (default: 4)
- `--gen_measures`: Measures to generate (default: same as `--measures`)
- `--human_measures`: Human measures to collect before generating (default: 1)
- `--quantize`: Quantize generated output to 1/16 grid (default: off)
- `--ticks_per_beat`: MIDI ticks per quarter note (default: 480)
- `--temperature`: Sampling temperature (default: 0.9)
- `--top_p`: Top-p sampling (default: 0.95)
- `--device`: `cuda` or `cpu` for inference (default: `cuda`)
- `--list-ports`: List available MIDI ports and exit

## Troubleshooting
- **Ports not found**: Run `python ableton_bridge.py --list-ports` and verify loopMIDI ports exist.
- **CUDA unavailable**: Install a CUDA-enabled PyTorch build or run with `--device cpu`.
- **Checkpoint missing**: Provide an absolute path to the checkpoint file.
- **No output in Ableton**: Verify `ARIA_OUT` is selected as the input and monitoring is enabled.
