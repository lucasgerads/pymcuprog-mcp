"""Tests for server.py tools, using a mocked _session so no hardware is needed."""
import json
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

import pymcuprog_mcp.server as server_module


# ---------------------------------------------------------------------------
# Shared mock backend fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_device_env(monkeypatch):
    monkeypatch.setenv("PYMCUPROG_DEVICE", "atmega4808")


@pytest.fixture()
def mock_session(monkeypatch):
    """Replace the module-level _session with a mock."""
    session = MagicMock()
    session.run.side_effect = lambda cfg, fn: fn(session._backend)
    session._backend = MagicMock()
    monkeypatch.setattr(server_module, "_session", session)
    return session


@pytest.fixture()
def backend(mock_session):
    return mock_session._backend


@pytest.fixture()
def mock_tool_session(monkeypatch):
    """Replace tool_session context manager with a mock."""
    tool_backend = MagicMock()

    @contextmanager
    def _fake_tool_session(cfg):
        yield tool_backend

    monkeypatch.setattr(server_module, "tool_session", _fake_tool_session)
    return tool_backend


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

def test_ping_returns_hex_device_id(mock_session, backend):
    backend.read_device_id.return_value = bytes([0x1E, 0x96, 0x51])
    result = server_module.ping()
    assert result == "0x1e 0x96 0x51"
    backend.read_device_id.assert_called_once()


# ---------------------------------------------------------------------------
# erase
# ---------------------------------------------------------------------------

def test_erase_chip_erase_by_default(mock_session, backend):
    result = server_module.erase()
    assert result == "OK"
    backend.erase.assert_called_once_with(memory_name=None)


def test_erase_specific_memory(mock_session, backend):
    result = server_module.erase(memory="eeprom")
    assert result == "OK"
    backend.erase.assert_called_once_with(memory_name="eeprom")


# ---------------------------------------------------------------------------
# write_hex
# ---------------------------------------------------------------------------

def test_write_hex_default_no_erase_with_verify(mock_session, backend):
    server_module.write_hex("/fw.hex")
    backend.erase.assert_not_called()
    backend.write_hex_to_target.assert_called_once_with("/fw.hex")
    backend.verify_hex.assert_called_once_with("/fw.hex")
    backend.release_from_reset.assert_called_once()


def test_write_hex_erase_first(mock_session, backend):
    server_module.write_hex("/fw.hex", erase_first=True)
    backend.erase.assert_called_once()
    backend.write_hex_to_target.assert_called_once_with("/fw.hex")


def test_write_hex_no_verify(mock_session, backend):
    server_module.write_hex("/fw.hex", verify_after=False)
    backend.verify_hex.assert_not_called()


# ---------------------------------------------------------------------------
# flash
# ---------------------------------------------------------------------------

def test_flash_erases_writes_verifies_releases(mock_session, backend):
    result = server_module.flash("/fw.hex")
    assert result == "OK"
    backend.erase.assert_called_once()
    backend.write_hex_to_target.assert_called_once_with("/fw.hex")
    backend.verify_hex.assert_called_once_with("/fw.hex")
    backend.release_from_reset.assert_called_once()


# ---------------------------------------------------------------------------
# verify_hex
# ---------------------------------------------------------------------------

def test_verify_hex_returns_pass(mock_session, backend):
    result = server_module.verify_hex("/fw.hex")
    assert result == "PASS"
    backend.verify_hex.assert_called_once_with("/fw.hex")


# ---------------------------------------------------------------------------
# read_memory
# ---------------------------------------------------------------------------

def test_read_memory_returns_json(mock_session, backend):
    mock_result = MagicMock()
    mock_result.data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    backend.read_memory.return_value = mock_result

    result = server_module.read_memory(memory="flash", offset=0, length=4)
    parsed = json.loads(result)

    assert parsed["memory"] == "flash"
    assert parsed["offset"] == 0
    assert parsed["length"] == 4
    assert parsed["hex"] == "de ad be ef"


# ---------------------------------------------------------------------------
# write_memory
# ---------------------------------------------------------------------------

def test_write_memory_parses_0x_hex_string(mock_session, backend):
    result = server_module.write_memory(memory="fuses", data_hex="0xff 0x00 0xc8")
    assert result == "OK"
    backend.write_memory.assert_called_once_with(bytes([0xFF, 0x00, 0xC8]), "fuses", 0)


def test_write_memory_parses_plain_hex(mock_session, backend):
    server_module.write_memory(memory="eeprom", data_hex="ff 00 c8", offset=4)
    backend.write_memory.assert_called_once_with(bytes([0xFF, 0x00, 0xC8]), "eeprom", 4)


# ---------------------------------------------------------------------------
# hold_in_reset / release_from_reset
# ---------------------------------------------------------------------------

def test_hold_in_reset(mock_session, backend):
    assert server_module.hold_in_reset() == "OK"
    backend.hold_in_reset.assert_called_once()


def test_release_from_reset(mock_session, backend):
    assert server_module.release_from_reset() == "OK"
    backend.release_from_reset.assert_called_once()


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------

def test_disconnect(mock_session):
    result = server_module.disconnect()
    assert result == "OK"
    mock_session.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Voltage / tool-level tools (use tool_session)
# ---------------------------------------------------------------------------

def test_read_target_voltage(mock_tool_session):
    mock_tool_session.read_target_voltage.return_value = 3.298
    assert server_module.read_target_voltage() == "3.298"


def test_read_supply_voltage(mock_tool_session):
    mock_tool_session.read_supply_voltage_setpoint.return_value = 3.3
    assert server_module.read_supply_voltage() == "3.3"


def test_set_supply_voltage(mock_tool_session):
    result = server_module.set_supply_voltage(voltage=3.3)
    assert result == "OK"
    mock_tool_session.set_supply_voltage_setpoint.assert_called_once_with(3.3)


def test_list_connected_tools_no_tools(mock_tool_session, monkeypatch):
    import pymcuprog_mcp.server as srv
    with patch.object(srv, "list_connected_tools", wraps=srv.list_connected_tools):
        from pymcuprog.backend import Backend
        with patch.object(Backend, "get_available_hid_tools", return_value=[]):
            result = server_module.list_connected_tools()
    assert "No USB HID debuggers found" in result


def test_list_connected_tools_returns_json(monkeypatch):
    from pymcuprog.backend import Backend
    with patch.object(Backend, "get_available_hid_tools", return_value=["tool-A"]):
        result = server_module.list_connected_tools()
    parsed = json.loads(result)
    assert "tool-A" in parsed


# ---------------------------------------------------------------------------
# build_and_flash
# ---------------------------------------------------------------------------

def test_build_and_flash_raises_without_project_dir(mock_session, monkeypatch):
    monkeypatch.delenv("PYMCUPROG_PROJECT_DIR", raising=False)
    with pytest.raises(RuntimeError, match="project_dir is required"):
        server_module.build_and_flash()


def test_build_and_flash_raises_on_build_failure(mock_session, monkeypatch, tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="error\n", stderr="")
        with pytest.raises(RuntimeError, match="Build failed"):
            server_module.build_and_flash(project_dir=str(tmp_path))


def test_build_and_flash_raises_when_no_hex_found(mock_session, monkeypatch, tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with pytest.raises(RuntimeError, match="no .hex file found"):
            server_module.build_and_flash(project_dir=str(tmp_path))


def test_build_and_flash_programs_device(mock_session, backend, tmp_path):
    hexfile = tmp_path / "firmware.hex"
    hexfile.write_text(":00000001FF\n")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = server_module.build_and_flash(project_dir=str(tmp_path))

    assert result == "OK"
    backend.erase.assert_called_once()
    backend.write_hex_to_target.assert_called_once_with(str(hexfile))
    backend.verify_hex.assert_called_once_with(str(hexfile))
    backend.release_from_reset.assert_called_once()
