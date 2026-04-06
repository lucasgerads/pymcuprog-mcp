from pymcuprog_mcp.config import ConnectionConfig, load_config


def test_defaults_when_no_env_vars(monkeypatch):
    for var in [
        "PYMCUPROG_DEVICE", "PYMCUPROG_TOOL", "PYMCUPROG_SERIALNUMBER",
        "PYMCUPROG_SERIALPORT", "PYMCUPROG_BAUDRATE", "PYMCUPROG_PROJECT_DIR",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = load_config()

    assert cfg.device == ""
    assert cfg.tool == ""
    assert cfg.serialnumber == ""
    assert cfg.serialport == ""
    assert cfg.baudrate == 115200
    assert cfg.project_dir == ""


def test_reads_env_vars(monkeypatch):
    monkeypatch.setenv("PYMCUPROG_DEVICE", "atmega4808")
    monkeypatch.setenv("PYMCUPROG_TOOL", "nedbg")
    monkeypatch.setenv("PYMCUPROG_SERIALNUMBER", "ABC123")
    monkeypatch.setenv("PYMCUPROG_SERIALPORT", "/dev/ttyUSB0")
    monkeypatch.setenv("PYMCUPROG_BAUDRATE", "9600")
    monkeypatch.setenv("PYMCUPROG_PROJECT_DIR", "/home/user/myproject")

    cfg = load_config()

    assert cfg.device == "atmega4808"
    assert cfg.tool == "nedbg"
    assert cfg.serialnumber == "ABC123"
    assert cfg.serialport == "/dev/ttyUSB0"
    assert cfg.baudrate == 9600
    assert cfg.project_dir == "/home/user/myproject"


def test_overrides_take_precedence_over_env(monkeypatch):
    monkeypatch.setenv("PYMCUPROG_DEVICE", "atmega4808")
    monkeypatch.setenv("PYMCUPROG_TOOL", "nedbg")

    cfg = load_config(device="attiny416", tool="pickit4")

    assert cfg.device == "attiny416"
    assert cfg.tool == "pickit4"


def test_empty_string_override_does_not_clear_env_value(monkeypatch):
    monkeypatch.setenv("PYMCUPROG_DEVICE", "atmega4808")

    cfg = load_config(device="")

    assert cfg.device == "atmega4808"


def test_project_dir_override(monkeypatch):
    monkeypatch.setenv("PYMCUPROG_PROJECT_DIR", "/env/project")

    cfg = load_config(project_dir="/override/project")

    assert cfg.project_dir == "/override/project"
