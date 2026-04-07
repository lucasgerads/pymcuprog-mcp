import glob
import json
import subprocess

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .session import _session, tool_session

mcp = FastMCP(
    "pymcuprog",
    instructions=(
        "Tools for programming Microchip/AVR microcontrollers via pymcuprog. "
        "Always call get_config first to see what device and tool are configured. "
        "Typical workflow: get_config -> ping -> build_and_flash or flash. "
        "Memory areas: flash, eeprom, fuses, user_row, signatures, lockbits, boot_row."
    ),
)


# ---------------------------------------------------------------------------
# Discovery tools — no hardware required
# ---------------------------------------------------------------------------


@mcp.tool()
def get_config() -> str:
    """Return the current server configuration read from environment variables.

    Call this first to confirm what device and tool are configured before
    running any programming operations. No hardware connection is required.
    """
    cfg = load_config()
    return json.dumps(
        {
            "device": cfg.device or "(not set)",
            "tool": cfg.tool or "(not set — any connected tool will be used)",
            "serialnumber": cfg.serialnumber or "(not set)",
            "serialport": cfg.serialport or "(not set — USB HID mode)",
            "baudrate": cfg.baudrate,
            "project_dir": cfg.project_dir or "(not set)",
        },
        indent=2,
    )


@mcp.tool()
def list_supported_devices() -> str:
    """Return a sorted list of all device names supported by pymcuprog.

    No hardware connection is required. Use this to find the correct device
    name before calling any programming tool.
    """
    from pymcuprog.backend import Backend

    devices = Backend.get_supported_devices()
    return "\n".join(sorted(devices))


@mcp.tool()
def list_connected_tools(tool_name: str = "") -> str:
    """Return a list of Microchip USB HID debuggers currently attached to the host.

    Optionally filter by tool_name (e.g. 'nedbg', 'pickit4').
    No device or session configuration is required.
    """
    from pymcuprog.backend import Backend

    tools = Backend.get_available_hid_tools(tool_name=tool_name or None)
    if not tools:
        return "No USB HID debuggers found."
    return json.dumps([str(t) for t in tools], indent=2)


# ---------------------------------------------------------------------------
# Tool-level operations — debugger connection only, no programming session
# ---------------------------------------------------------------------------


@mcp.tool()
def read_tool_info(tool: str = "", serialnumber: str = "") -> str:
    """Read hardware and firmware information from the connected debugger.

    Returns a JSON object with fields such as fw_major, fw_minor, hw_rev,
    serial_number, and device_name.
    Requires a USB HID debugger; does not require a target device.
    """
    cfg = load_config(tool=tool, serialnumber=serialnumber)
    with tool_session(cfg) as backend:
        info = backend.read_tool_info()
    return json.dumps(info, indent=2)


@mcp.tool()
def read_target_voltage(tool: str = "", serialnumber: str = "") -> str:
    """Read the voltage on the target VCC pin as measured by the debugger.

    Returns the measured voltage as a float string (e.g. '3.298').
    Requires a USB HID debugger with voltage measurement capability.
    Does not require a target device or programming session.
    """
    cfg = load_config(tool=tool, serialnumber=serialnumber)
    with tool_session(cfg) as backend:
        voltage = backend.read_target_voltage()
    return str(voltage)


@mcp.tool()
def read_supply_voltage(tool: str = "", serialnumber: str = "") -> str:
    """Read the debugger's onboard supply voltage setpoint.

    Returns the current setpoint as a float string.
    Requires a USB HID debugger with onboard supply capability (e.g. Curiosity Nano).
    """
    cfg = load_config(tool=tool, serialnumber=serialnumber)
    with tool_session(cfg) as backend:
        voltage = backend.read_supply_voltage_setpoint()
    return str(voltage)


@mcp.tool()
def set_supply_voltage(
    voltage: float,
    tool: str = "",
    serialnumber: str = "",
) -> str:
    """Set the debugger's onboard supply voltage output (e.g. 3.3 or 5.0).

    Returns 'OK' on success.
    Requires a USB HID debugger with onboard supply capability.
    WARNING: Ensure the target device supports the requested voltage before calling.
    """
    cfg = load_config(tool=tool, serialnumber=serialnumber)
    with tool_session(cfg) as backend:
        backend.set_supply_voltage_setpoint(voltage)
    return "OK"


# ---------------------------------------------------------------------------
# Programming tools — require a full session (tool + device)
# ---------------------------------------------------------------------------


@mcp.tool()
def ping(
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Read the device signature bytes to confirm communication with the target.

    Returns the device ID as a space-separated hex string (e.g. '0x1e 0x96 0x51').
    Use this to verify the target is connected and responding before programming.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    device_id = _session.run(cfg, lambda b: b.read_device_id())
    return " ".join(f"0x{b:02x}" for b in device_id)


@mcp.tool()
def erase(
    memory: str = "all",
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Erase target device memory.

    memory='all' performs a chip erase (default). For AVR, chip erase does not
    erase EEPROM if the EESAVE fuse is set.
    Other valid memory values: 'flash', 'eeprom', 'user_row'.
    Returns 'OK' on success.
    Use erase before write_hex when the target is not blank.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    memory_name = None if memory == "all" else memory
    _session.run(cfg, lambda b: b.erase(memory_name=memory_name))
    return "OK"


@mcp.tool()
def write_hex(
    hexfile: str,
    erase_first: bool = False,
    verify_after: bool = True,
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Write an Intel HEX file to the target device.

    hexfile: absolute path to the .hex file on disk.
    erase_first: if True, performs a chip erase before writing. Default: False.
    verify_after: if True, reads back and verifies all written memory. Default: True.
    Returns 'OK' on success, raises an error if programming or verification fails.
    For the common case of a full firmware update, prefer the flash tool instead.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    def _do(b):
        if erase_first:
            b.erase()
        b.write_hex_to_target(hexfile)
        if verify_after:
            b.verify_hex(hexfile)
        b.release_from_reset()
    _session.run(cfg, _do)
    return "OK"


@mcp.tool()
def verify_hex(
    hexfile: str,
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Verify that target device memory matches an Intel HEX file.

    hexfile: absolute path to the .hex file on disk.
    Returns 'PASS' if memory matches, raises an error if it does not.
    Use after write_hex or to audit an already-programmed device.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    _session.run(cfg, lambda b: b.verify_hex(hexfile))
    return "PASS"


@mcp.tool()
def read_memory(
    memory: str = "flash",
    offset: int = 0,
    length: int = 0,
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Read raw bytes from a target device memory area.

    memory: one of 'flash', 'eeprom', 'fuses', 'user_row', 'signatures',
            'lockbits', 'boot_row'.
    offset: byte offset within the memory to start reading (default: 0).
    length: number of bytes to read; 0 means read to end of memory (default: 0).
    Returns a JSON object with keys 'memory', 'offset', 'length', and 'hex'
    where 'hex' is a space-separated hex byte string.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    result = _session.run(cfg, lambda b: b.read_memory(memory, offset, length or 0))
    data: bytes = result.data
    return json.dumps(
        {
            "memory": memory,
            "offset": offset,
            "length": len(data),
            "hex": " ".join(f"{b:02x}" for b in data),
        }
    )


@mcp.tool()
def write_memory(
    memory: str,
    data_hex: str,
    offset: int = 0,
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Write raw bytes to a target device memory area.

    memory: memory area name (e.g. 'fuses', 'eeprom', 'user_row').
    data_hex: bytes to write as a space-separated or 0x-prefixed hex string
              (e.g. '0xff 0x00 0xc8' or 'ff 00 c8').
    offset: byte offset within the memory to start writing (default: 0).
    Returns 'OK' on success.
    Use for writing fuse bytes, EEPROM, or small memory regions.
    For full firmware images, prefer flash which handles address mapping.
    """
    tokens = data_hex.replace(",", " ").split()
    data = bytes(int(t, 16) for t in tokens)
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    _session.run(cfg, lambda b: b.write_memory(data, memory, offset))
    return "OK"


@mcp.tool()
def hold_in_reset(
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Hold the target device in reset.

    The device remains in reset until release_from_reset is called or the
    debugger is disconnected.
    Returns 'OK' on success.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    _session.run(cfg, lambda b: b.hold_in_reset())
    return "OK"


@mcp.tool()
def release_from_reset(
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Release the target device from reset, allowing it to start executing.

    Returns 'OK' on success.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    _session.run(cfg, lambda b: b.release_from_reset())
    return "OK"


@mcp.tool()
def build_and_flash(
    project_dir: str = "",
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Build a project with make and flash the result to the target device.

    project_dir: path to the directory containing the Makefile.
    Falls back to the PYMCUPROG_PROJECT_DIR environment variable if not provided.
    Runs 'make -C project_dir', finds the generated .hex file, then erases,
    writes, verifies, and releases the target.
    Returns 'OK' on success; raises with build output on compile failure.
    """
    cfg = load_config(
        project_dir=project_dir,
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )
    if not cfg.project_dir:
        raise RuntimeError(
            "project_dir is required. Pass it as a parameter or set PYMCUPROG_PROJECT_DIR."
        )
    result = subprocess.run(
        ["make", "-C", cfg.project_dir],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Build failed:\n{result.stdout}{result.stderr}".strip()
        )

    hexfiles = glob.glob(f"{cfg.project_dir}/*.hex")
    if len(hexfiles) == 0:
        raise RuntimeError(f"Build succeeded but no .hex file found in {cfg.project_dir}")
    if len(hexfiles) > 1:
        raise RuntimeError(
            f"Multiple .hex files found in {cfg.project_dir}: {hexfiles}. "
            "Use the flash tool with an explicit hexfile path."
        )
    hexfile = hexfiles[0]

    def _do(b):
        b.erase()
        b.write_hex_to_target(hexfile)
        b.verify_hex(hexfile)
        b.release_from_reset()

    _session.run(cfg, _do)
    return "OK"


@mcp.tool()
def flash(
    hexfile: str,
    device: str = "",
    tool: str = "",
    serialnumber: str = "",
    serialport: str = "",
    baudrate: int = 0,
) -> str:
    """Erase, write, and verify a hex file in one operation.

    This is the recommended way to program a device. It erases the target,
    writes the hex file, and verifies the result.
    hexfile: absolute path to the .hex file on disk.
    Returns 'OK' on success.
    """
    cfg = load_config(
        device=device,
        tool=tool,
        serialnumber=serialnumber,
        serialport=serialport,
        baudrate=baudrate,
    )

    def _do(b):
        b.erase()
        b.write_hex_to_target(hexfile)
        b.verify_hex(hexfile)
        b.release_from_reset()

    _session.run(cfg, _do)
    return "OK"


@mcp.tool()
def disconnect() -> str:
    """Close the persistent programming session.

    Call this to cleanly release the debugger connection, for example before
    unplugging the programmer or switching to a different target.
    Returns 'OK' on success.
    """
    _session.disconnect()
    return "OK"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
