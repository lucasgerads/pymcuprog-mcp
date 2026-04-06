# pymcuprog-mcp

MCP server wrapping [pymcuprog](https://github.com/microchip-pic-avr-tools/pymcuprog) so AI tools (Claude Code, Claude Desktop, etc.) can program Microchip AVR microcontrollers via natural language.

Supports USB HID debuggers (nEDBG, PICkit 4, Atmel-ICE, MPLAB Snap, …) and serial UART UPDI adapters.

## Installation

```bash
pip install pymcuprog-mcp
```

Or from source:

```bash
git clone https://github.com/youruser/pymcuprog-mcp
cd pymcuprog-mcp
pip install -e .
```

## Configuration

The server is configured via environment variables. The two most important ones are `PYMCUPROG_DEVICE` (target MCU name, e.g. `atmega4808`) and `PYMCUPROG_TOOL` (debugger type, e.g. `nedbg`).

| Variable | Description | Default |
|---|---|---|
| `PYMCUPROG_DEVICE` | Target device name (e.g. `atmega4808`, `attiny416`) | — |
| `PYMCUPROG_TOOL` | Debugger type (`nedbg`, `pickit4`, `atmelice`, `snap`, …) | any connected |
| `PYMCUPROG_SERIALNUMBER` | USB serial number substring (to pick a specific tool) | — |
| `PYMCUPROG_SERIALPORT` | Serial port for UART UPDI mode (e.g. `/dev/ttyUSB0`, `COM3`) | — |
| `PYMCUPROG_BAUDRATE` | Baud rate for serial UPDI mode | `115200` |
| `PYMCUPROG_PROJECT_DIR` | Default project directory for the `build_and_flash` tool | — |

Setting `PYMCUPROG_SERIALPORT` switches the server into serial UPDI mode (uses a plain USB-serial adapter instead of a Microchip debugger).

## `.mcp.json` examples

### USB HID debugger (nEDBG / Curiosity Nano)

```json
{
  "mcpServers": {
    "pymcuprog": {
      "command": "pymcuprog-mcp",
      "env": {
        "PYMCUPROG_DEVICE": "atmega4808",
        "PYMCUPROG_TOOL": "nedbg"
      }
    }
  }
}
```

### PICkit 4 or MPLAB Snap

```json
{
  "mcpServers": {
    "pymcuprog": {
      "command": "pymcuprog-mcp",
      "env": {
        "PYMCUPROG_DEVICE": "attiny416",
        "PYMCUPROG_TOOL": "pickit4"
      }
    }
  }
}
```

### Serial UART UPDI (cheap USB-serial adapter)

```json
{
  "mcpServers": {
    "pymcuprog": {
      "command": "pymcuprog-mcp",
      "env": {
        "PYMCUPROG_DEVICE": "avr128da48",
        "PYMCUPROG_SERIALPORT": "/dev/ttyUSB0",
        "PYMCUPROG_BAUDRATE": "115200"
      }
    }
  }
}
```

### Multiple tools on the same machine (select by serial number)

```json
{
  "mcpServers": {
    "pymcuprog-board-a": {
      "command": "pymcuprog-mcp",
      "env": {
        "PYMCUPROG_DEVICE": "atmega4808",
        "PYMCUPROG_TOOL": "nedbg",
        "PYMCUPROG_SERIALNUMBER": "MCHP0001"
      }
    },
    "pymcuprog-board-b": {
      "command": "pymcuprog-mcp",
      "env": {
        "PYMCUPROG_DEVICE": "atmega4808",
        "PYMCUPROG_TOOL": "nedbg",
        "PYMCUPROG_SERIALNUMBER": "MCHP0002"
      }
    }
  }
}
```

### Claude Code (via CLI)

```bash
claude mcp add pymcuprog -e PYMCUPROG_DEVICE=atmega4808 -e PYMCUPROG_TOOL=nedbg -- pymcuprog-mcp
```

## Available tools

| Tool | Description |
|---|---|
| `list_supported_devices` | All device names pymcuprog knows (no hardware needed) |
| `list_connected_tools` | USB HID debuggers currently attached |
| `ping` | Read device ID bytes to verify connectivity |
| `erase` | Chip erase or erase a specific memory area |
| `flash` | Erase + write + verify + release in one call (recommended) |
| `build_and_flash` | Run `make` in a project directory, then flash the resulting `.hex` |
| `write_hex` | Program a `.hex` file with manual control over erase/verify steps |
| `verify_hex` | Compare target memory to a `.hex` file |
| `read_memory` | Read raw bytes from flash, EEPROM, fuses, etc. |
| `write_memory` | Write raw hex bytes to fuses, EEPROM, user_row, etc. |
| `hold_in_reset` | Hold target in reset |
| `release_from_reset` | Release target from reset |
| `disconnect` | Close the persistent debugger session |
| `read_target_voltage` | Measure target VCC |
| `read_supply_voltage` | Read debugger supply setpoint |
| `set_supply_voltage` | Set debugger supply voltage output |
| `read_tool_info` | Read debugger firmware/hardware info |

Typical workflow: **`ping` → `flash`** or **`ping` → `build_and_flash`**

All programming tools accept optional `device`, `tool`, `serialport`, etc. parameters to override the environment variables on a per-call basis.
