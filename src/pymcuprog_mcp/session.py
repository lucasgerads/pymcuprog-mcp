import threading
from contextlib import contextmanager

from pymcuprog.backend import Backend, SessionConfig
from pymcuprog.pymcuprog_errors import PymcuprogError
from pymcuprog.toolconnection import ToolSerialConnection, ToolUsbHidConnection

from .config import ConnectionConfig


def _make_transport(cfg: ConnectionConfig):
    if cfg.serialport:
        return ToolSerialConnection(
            serialport=cfg.serialport,
            baudrate=cfg.baudrate or 115200,
        )
    return ToolUsbHidConnection(
        serialnumber=cfg.serialnumber or None,
        tool_name=cfg.tool or None,
    )


@contextmanager
def tool_session(cfg: ConnectionConfig):
    """Connect to the debugger without starting a programming session.

    Suitable for voltage measurement, tool info, and discovery operations
    that do not require a target device to be present.
    """
    transport = _make_transport(cfg)
    backend = Backend()
    try:
        backend.connect_to_tool(transport)
        yield backend
    except PymcuprogError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        try:
            backend.disconnect_from_tool()
        except Exception:
            pass


class PersistentSession:
    """Long-lived programming session that reconnects automatically on failure.

    A single session is kept open across tool calls. If an operation fails,
    the session is torn down and re-established once before the error is raised.
    The session is also re-established if the connection config changes.
    """

    def __init__(self):
        self._backend: Backend | None = None
        self._cfg: ConnectionConfig | None = None
        self._lock = threading.Lock()

    def _connect(self, cfg: ConnectionConfig) -> Backend:
        transport = _make_transport(cfg)
        backend = Backend()
        backend.connect_to_tool(transport)
        backend.start_session(SessionConfig(cfg.device))
        return backend

    def _disconnect(self):
        if self._backend is not None:
            try:
                self._backend.end_session()
            except Exception:
                pass
            try:
                self._backend.disconnect_from_tool()
            except Exception:
                pass
            self._backend = None

    def run(self, cfg: ConnectionConfig, fn):
        """Run fn(backend), reconnecting once on any failure.

        Raises RuntimeError on failure after retry.
        """
        if not cfg.device:
            raise RuntimeError(
                "Device name is required. "
                "Set PYMCUPROG_DEVICE or pass device= to the tool."
            )
        with self._lock:
            if self._cfg != cfg:
                self._disconnect()
                self._cfg = cfg

            for attempt in range(2):
                try:
                    if self._backend is None:
                        self._backend = self._connect(cfg)
                    return fn(self._backend)
                except Exception as exc:
                    self._disconnect()
                    if attempt == 1:
                        raise RuntimeError(str(exc)) from exc

    def disconnect(self):
        """Explicitly close the session."""
        with self._lock:
            self._disconnect()
            self._cfg = None


_session = PersistentSession()
