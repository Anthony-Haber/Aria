"""Optional OSC control plane for Max for Live integration."""

import threading
import time
import logging

logger = logging.getLogger(__name__)


class OscController:
    def __init__(
        self,
        host: str,
        in_port: int,
        out_port: int,
        sampling_state,
        session_state,
        command_queue,
    ):
        self.host = host
        self.in_port = in_port
        self.out_port = out_port
        self.sampling_state = sampling_state
        self.session_state = session_state
        self.command_queue = command_queue
        self.server = None
        self.client = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        try:
            from pythonosc import dispatcher, osc_server, udp_client
        except Exception as e:  # pragma: no cover - optional dep
            logger.error(f"python-osc not available: {e}")
            return

        disp = dispatcher.Dispatcher()
        disp.map("/aria/record", self._handle_record)
        disp.map("/aria/temp", self._handle_temp)
        disp.map("/aria/top_p", self._handle_top_p)
        disp.map("/aria/min_p", self._handle_min_p)
        disp.map("/aria/tokens", self._handle_tokens)
        disp.map("/aria/cancel", self._handle_cancel)
        disp.map("/aria/ping", self._handle_ping)
        disp.map("/aria/play", self._handle_play)

        try:
            self.client = udp_client.SimpleUDPClient(self.host, self.out_port)
            self.server = osc_server.ThreadingOSCUDPServer((self.host, self.in_port), disp)
        except Exception as e:
            logger.error(f"Failed to start OSC server: {e}")
            return

        def _serve():
            logger.info(f"OSC server listening on {self.host}:{self.in_port}")
            while not self.stop_event.is_set():
                self.server.handle_request()
            logger.info("OSC server stopped")

        self.thread = threading.Thread(target=_serve, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.server:
            try:
                self.server.server_close()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

    # Outgoing helpers
    def send_status(self, status: str):
        if not self.client:
            return
        try:
            self.client.send_message("/aria/status", status)
        except Exception:
            logger.debug("Failed to send OSC status")

    def send_params(self):
        if not self.client:
            return
        try:
            t, tp, mp = self.sampling_state.get_values()
            self.client.send_message("/aria/params", [t, tp, mp])
        except Exception:
            logger.debug("Failed to send OSC params")

    def send_log(self, msg: str):
        if not self.client:
            return
        try:
            self.client.send_message("/aria/log", msg)
        except Exception:
            logger.debug("Failed to send OSC log")

    @staticmethod
    def _coerce_flag(val):
        try:
            # Numeric path
            f = float(val)
            return 1 if f >= 0.5 else 0
        except Exception:
            pass
        if isinstance(val, str):
            if val.strip() in ("1", "true", "True", "on"):
                return 1
            if val.strip() in ("0", "false", "False", "off"):
                return 0
        if isinstance(val, bool):
            return 1 if val else 0
        return None

    # Handlers
    def _handle_record(self, addr, *args):
        # Debug: show raw payload
        logger.info(f"[OSC] {addr} {args} {type(args[0]) if args else None}")
        if not args:
            return

        flag = self._coerce_flag(args[0])
        if flag is None:
            self.send_log("Invalid /aria/record payload (ignored)")
            return

        snap = self.session_state.get_snapshot()
        last_level = snap.get("last_record_level")
        if last_level == flag:
            self.send_log("Record level unchanged (ignored)")
            return
        is_recording = snap.get("is_recording")
        if flag == 1 and is_recording:
            self.send_log("Already recording; record=1 ignored")
            logger.info("[OSC] record=1 ignored (already recording)")
            return
        if flag == 0 and not is_recording:
            self.send_log("Not recording; record=0 ignored")
            logger.info("[OSC] record=0 ignored (not recording)")
            self.session_state.set_record_level(flag)
            return
        self.session_state.set_record_level(flag)
        if flag == 1:
            logger.info("[OSC] record=1 -> START")
            self.command_queue.put(("record_start", None))
            self.send_log("Record start requested (OSC)")
        else:
            logger.info("[OSC] record=0 -> STOP+GENERATE")
            self.command_queue.put(("record_stop", None))
            self.send_log("Record stop requested (OSC)")

    def _handle_cancel(self, addr, *args):
        self.command_queue.put(("cancel", 1))
        self.send_log("Cancel requested (OSC)")

    def _handle_play(self, addr, *args):
        logger.info("[OSC] play -> SEND OUTPUT")
        self.command_queue.put(("play", None))
        self.send_log("Play requested (OSC)")

    def _handle_temp(self, addr, *args):
        logger.info(f"[OSC] {addr} {args}")
        if not args:
            return
        try:
            v = float(args[0])
        except Exception:
            return
        self.sampling_state.set_temperature(v)
        self.send_params()
        self.send_log(f"Temp -> {self.sampling_state.get_values()[0]:.2f}")

    def _handle_top_p(self, addr, *args):
        logger.info(f"[OSC] {addr} {args}")
        if not args:
            return
        try:
            v = float(args[0])
        except Exception:
            return
        self.sampling_state.set_top_p(v)
        self.send_params()
        self.send_log(f"Top_p -> {self.sampling_state.get_values()[1]:.2f}")

    def _handle_min_p(self, addr, *args):
        logger.info(f"[OSC] {addr} {args}")
        if not args:
            return
        try:
            v = float(args[0])
        except Exception:
            return
        self.sampling_state.set_min_p(v)
        self.send_params()
        self.send_log(f"Min_p -> {self.sampling_state.get_values()[2]:.2f}")

    def _handle_tokens(self, addr, *args):
        logger.info(f"[OSC] {addr} {args}")
        if not args:
            return
        try:
            v = float(args[0])
        except Exception:
            self.send_log("Invalid /aria/tokens payload (ignored)")
            return
        # Clamp to integer range 0-2048
        clamped = int(max(0, min(2048, round(v))))
        self.session_state.set_max_tokens(clamped)
        self.send_log(f"Max tokens -> {clamped}")

    def _handle_ping(self, addr, *args):
        self.send_status(self.session_state.get_snapshot().get("status", "UNKNOWN"))
        self.send_params()
