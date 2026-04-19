# Aria Bridge

Aria Bridge connects an AI music model to your DAW in real time. You play a few bars into it, it generates a continuation, and plays it back through a virtual MIDI port — all without leaving your session.

Supported platforms: **Windows 10/11** and **macOS** (Apple Silicon and Intel).

---

## What You Need Before Starting

- Ableton Live, Reaper, or any DAW that supports virtual MIDI ports
- An NVIDIA GPU (Windows) or Apple Silicon Mac is recommended for fast generation — CPU and Intel Mac work but are slower
- About 10–15 minutes for a first-time setup

---

## Step 1 — Download Aria Bridge

Go to the [Releases page](../../releases) and download the latest zip for your platform:

- **Windows:** `AriaBridge-vX.X.X-windows.zip`
- **macOS:** `AriaBridge-vX.X.X-macos.zip`

Unzip it to a permanent folder — for example `C:\Aria Bridge\` on Windows or `~/Aria Bridge/` on Mac.

> Do not run it from your Downloads folder. Keep it somewhere stable.

---

## Step 2 — Download the Python Backend (Windows only)

The Windows backend (`aria_backend.exe`) is too large to include in the release zip. You need to download it separately.

1. Go to the [Aria Bridge releases on HuggingFace](https://huggingface.co/Anthony-Haber/Aria_Bridge_releases/tree/main)
2. Download **`aria_backend.exe`**
3. Place it directly inside your Aria Bridge folder, next to `AriaLauncher.exe`

```
Aria Bridge/
  AriaLauncher.exe
  aria_backend.exe   ← goes here
  models/
  ...
```

> macOS users can skip this step — the backend is already included in the Mac zip.

---

## Step 3 — Download the AI Model

The model file is not included because of its size. You need to download it once.

1. Download: [model-gen.safetensors](https://huggingface.co/loubb/aria-medium-base/resolve/main/model-gen.safetensors)
2. Place it inside the `models` folder in your Aria Bridge folder

```
Aria Bridge/
  models/
    model-gen.safetensors   ← goes here
```

---

## Step 4 — Set Up Virtual MIDI Ports

Aria Bridge talks to your DAW through virtual MIDI cables.

### Windows — loopMIDI

1. Download loopMIDI (free): [tobias-erichsen.de/software/loopmidi.html](https://www.tobias-erichsen.de/software/loopmidi.html)
2. Install and open it
3. Create two ports with these exact names:
   - `ARIA_IN`
   - `ARIA_OUT`

> loopMIDI must be running every time you use Aria Bridge. You can set it to launch on startup in its settings.

### macOS — IAC Driver (built in)

macOS has a virtual MIDI system built in — no extra download needed.

1. Open **Audio MIDI Setup** (search in Spotlight)
2. Go to **Window → Show MIDI Studio**
3. Double-click **IAC Driver**
4. Check **Device is online**
5. Add two ports named exactly:
   - `ARIA_IN`
   - `ARIA_OUT`

---

## Step 5 — Route MIDI in Your DAW

You need two MIDI tracks:

| Track | Purpose | MIDI Output / Input |
|---|---|---|
| Track 1 | Your instrument (what you play) | Output → `ARIA_IN` |
| Track 2 | Aria's output (what it generates) | Input → `ARIA_OUT` |

Put an instrument on Track 2 so you can hear Aria's output.

---

## Step 6 — Launch Aria Bridge

### Windows

Double-click **AriaLauncher.exe**. A small window appears — select your mode:

- **M4L Device** — use this if you are running the included Max for Live device inside Ableton
- **Plugin (VST3 / Standalone)** — use this for the VST3 plugin in any DAW, or the standalone window

When the status dot turns green and says **Ready**, Aria Bridge is connected.

### macOS

Double-click **Aria Bridge.app**. The app opens and the backend starts automatically in the background. When the status shows **IDLE**, it is ready.

---

## Using Aria Bridge

| Control | What it does |
|---|---|
| `record` | Start / stop recording your MIDI input |
| `play` | Play back the generated output |
| `cancel` | Stop whatever is happening — cancels recording, interrupts generation, stops playback, or discards a pending output and returns to record |
| `commit` | Save this generation with your ratings |
| `sync` | Re-send all parameter values to the backend |
| `temp` | Temperature — higher = more surprising, lower = more conservative |
| `top_p` / `min_p` | Sampling filters — leave at defaults to start |
| `tokens` | How many tokens to generate — more = longer output |
| `coherence` / `taste` / `repetition` / `continuity` / `grade` | Rate the generation 1–5 before committing |

**Basic workflow:**
1. Hit `record` and play something on your MIDI track
2. Hit `record` again to stop — generation starts automatically
3. A timer shows while the model is running
4. When ready, hit `play` to hear the result
5. If you like it, rate it and hit `commit`

---

## Troubleshooting

**Status shows DISCONNECTED**
The backend did not start. On Windows, make sure `aria_backend.exe` is downloaded from HuggingFace and placed in the same folder as `AriaLauncher.exe` (see Step 2). On Mac, make sure the backend binary is present inside the app bundle.

**No MIDI is being captured**
Check that your virtual MIDI ports exist and are named exactly `ARIA_IN` and `ARIA_OUT`. On Windows, make sure loopMIDI is running. Check your DAW track routing.

**Generation is very slow**
On Windows, make sure you have an NVIDIA GPU with up-to-date drivers. On Mac, this is expected on Intel — Apple Silicon is significantly faster.

**The model file is not found**
Make sure `model-gen.safetensors` is inside the `models` folder and has not been renamed.

---

## License

MIT
