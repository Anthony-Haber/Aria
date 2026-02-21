"""Optional Tkinter UI panel for live control and status."""

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk


def run_ui(sampling_state, session_state, cmd_queue: queue.Queue, log_queue: queue.Queue, stop_event: threading.Event):
    root = tk.Tk()
    root.title("Aria Bridge")
    root.geometry("360x420")

    mode_var = tk.StringVar()
    status_var = tk.StringVar()
    temp_var = tk.StringVar()
    top_p_var = tk.StringVar()
    min_p_var = tk.StringVar()

    def refresh_labels():
        snap = session_state.get_snapshot()
        mode_var.set(f"Mode: {snap['mode']}")
        status_var.set(f"Status: {snap['status']}")
        t, tp, mp = sampling_state.get_values()
        temp_var.set(f"Temp: {t:.2f}")
        top_p_var.set(f"Top-p: {tp:.2f}")
        min_p_var.set(f"Min-p: {mp:.2f}")

    # Layout
    ttk.Label(root, textvariable=mode_var, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
    ttk.Label(root, textvariable=status_var, font=("Segoe UI", 11)).pack(anchor="w", padx=8, pady=(0, 8))

    params = ttk.Frame(root)
    params.pack(fill="x", padx=8, pady=4)
    ttk.Label(params, textvariable=temp_var).grid(row=0, column=0, sticky="w")
    ttk.Label(params, textvariable=top_p_var).grid(row=1, column=0, sticky="w")
    ttk.Label(params, textvariable=min_p_var).grid(row=2, column=0, sticky="w")

    btns = ttk.Frame(root)
    btns.pack(fill="x", padx=8, pady=8)

    def log(msg):
        log_queue.put(msg)
        import logging
        logging.getLogger(__name__).info(msg)

    def wrap(cmd, payload=None):
        cmd_queue.put((cmd, payload))

    ttk.Button(btns, text="Record (r)", command=lambda: wrap("toggle_record")).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Play Last (p)", command=lambda: wrap("play_last")).grid(row=0, column=1, sticky="ew", padx=2, pady=2)

    ttk.Button(btns, text="Temp +", command=lambda: (sampling_state.increase_temperature(), log_change())).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Temp -", command=lambda: (sampling_state.decrease_temperature(), log_change())).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Top-p +", command=lambda: (sampling_state.increase_top_p(), log_change())).grid(row=2, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Top-p -", command=lambda: (sampling_state.decrease_top_p(), log_change())).grid(row=2, column=1, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Min-p +", command=lambda: (sampling_state.increase_min_p(), log_change())).grid(row=3, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(btns, text="Min-p -", command=lambda: (sampling_state.decrease_min_p(), log_change())).grid(row=3, column=1, sticky="ew", padx=2, pady=2)

    for c in range(2):
        btns.grid_columnconfigure(c, weight=1)

    log_box = tk.Text(root, height=12, state="disabled", wrap="word")
    log_box.pack(fill="both", expand=True, padx=8, pady=8)

    def append_log(msg):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def log_change():
        t, tp, mp = sampling_state.get_values()
        log(f"[SAMPLING] temp={t:.2f} top_p={tp:.2f} min_p={mp:.2f}")

    def poll():
        if stop_event.is_set():
            root.quit()
            return
        refresh_labels()
        try:
            while True:
                msg = log_queue.get_nowait()
                append_log(msg)
        except queue.Empty:
            pass
        root.after(100, poll)

    refresh_labels()
    root.after(100, poll)

    def on_key(event):
        ks = event.keysym.lower()
        if ks == "r":
            wrap("toggle_record")
        elif ks == "p":
            wrap("play_last")

    root.bind_all("<Key>", on_key)
    root.protocol("WM_DELETE_WINDOW", lambda: (stop_event.set(), root.quit()))
    root.mainloop()
