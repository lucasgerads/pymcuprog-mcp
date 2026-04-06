import os
from dataclasses import dataclass


@dataclass
class ConnectionConfig:
    device: str = ""
    tool: str = ""
    serialnumber: str = ""
    serialport: str = ""
    baudrate: int = 115200
    project_dir: str = ""


def load_config(**overrides) -> ConnectionConfig:
    """Read connection config from environment variables, then apply non-empty overrides."""
    cfg = ConnectionConfig(
        device=os.environ.get("PYMCUPROG_DEVICE", ""),
        tool=os.environ.get("PYMCUPROG_TOOL", ""),
        serialnumber=os.environ.get("PYMCUPROG_SERIALNUMBER", ""),
        serialport=os.environ.get("PYMCUPROG_SERIALPORT", ""),
        baudrate=int(os.environ.get("PYMCUPROG_BAUDRATE", 115200)),
        project_dir=os.environ.get("PYMCUPROG_PROJECT_DIR", ""),
    )
    for key, value in overrides.items():
        if value:
            setattr(cfg, key, value)
    return cfg
