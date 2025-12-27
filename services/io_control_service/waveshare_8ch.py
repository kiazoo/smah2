from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class ModbusFrameError(Exception):
    pass


class ModbusExceptionResponse(Exception):
    def __init__(self, function: int, code: int):
        super().__init__(f"Modbus exception response: func=0x{function:02X}, code=0x{code:02X}")
        self.function = function
        self.code = code


@dataclass(frozen=True)
class Waveshare8CH:
    """
    Waveshare Modbus RTU IO 8CH (8DI/8DO)

    Key commands (per Waveshare wiki):
    - Read DO status (coils):         FC=0x01, addr=0x0000, qty=0x0008
    - Read DI status (discrete in):   FC=0x02, addr=0x0000, qty=0x0008
    - Control single DO channel:      FC=0x05, addr=0x0000..0x0007, value=0xFF00(on)/0x0000(off)/0x5500(toggle)
    - Control ALL DO channels:        FC=0x05, addr=0x00FF,        value=0xFF00/0x0000/0x5500
    - Write DO bitmask (8ch):         FC=0x0F, addr=0x0000, qty=0x0008, bytecount=0x01, data=bitmask
    - Read output control modes:      FC=0x03, reg=0x1000..0x1007 (holding regs), qty=1..8
    - Set single output control mode: FC=0x06, reg=0x1000..0x1007, value=0..3
    - Set multiple output modes:      FC=0x10, reg=0x1000.., qty=N, bytecount=2N, data=regs
    """

    # Output control mode values
    MODE_NORMAL: int = 0x0000
    MODE_LINKAGE: int = 0x0001
    MODE_TOGGLE: int = 0x0002
    MODE_EDGE_TRIGGER: int = 0x0003

    @staticmethod
    def _crc16_modbus(data: bytes) -> int:
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    @classmethod
    def _append_crc(cls, pdu: bytes) -> bytes:
        crc = cls._crc16_modbus(pdu)
        return pdu + bytes((crc & 0xFF, (crc >> 8) & 0xFF))  # little-endian CRC

    @classmethod
    def _check_crc(cls, frame: bytes) -> None:
        if len(frame) < 4:
            raise ModbusFrameError("frame too short for CRC")
        data, got_crc_lo, got_crc_hi = frame[:-2], frame[-2], frame[-1]
        crc = cls._crc16_modbus(data)
        if got_crc_lo != (crc & 0xFF) or got_crc_hi != ((crc >> 8) & 0xFF):
            raise ModbusFrameError("CRC mismatch")

    @staticmethod
    def _u16_hi(x: int) -> int:
        return (x >> 8) & 0xFF

    @staticmethod
    def _u16_lo(x: int) -> int:
        return x & 0xFF

    @classmethod
    def _build_read_bits(cls, slave_id: int, func: int, start_addr: int, qty: int) -> bytes:
        if not (0 <= slave_id <= 255):
            raise ValueError("slave_id must be 0..255")
        if not (0 <= start_addr <= 0xFFFF):
            raise ValueError("start_addr must be 0..65535")
        if not (1 <= qty <= 2000):
            raise ValueError("qty out of range")

        pdu = bytes(
            [
                slave_id,
                func,
                cls._u16_hi(start_addr),
                cls._u16_lo(start_addr),
                cls._u16_hi(qty),
                cls._u16_lo(qty),
            ]
        )
        return cls._append_crc(pdu)

    @classmethod
    def _build_write_single(cls, slave_id: int, func: int, addr: int, value: int) -> bytes:
        if not (0 <= slave_id <= 255):
            raise ValueError("slave_id must be 0..255")
        if not (0 <= addr <= 0xFFFF):
            raise ValueError("addr must be 0..65535")
        if not (0 <= value <= 0xFFFF):
            raise ValueError("value must be 0..65535")

        pdu = bytes(
            [
                slave_id,
                func,
                cls._u16_hi(addr),
                cls._u16_lo(addr),
                cls._u16_hi(value),
                cls._u16_lo(value),
            ]
        )
        return cls._append_crc(pdu)

    @classmethod
    def _build_write_multiple_coils_8ch(cls, slave_id: int, start_addr: int, qty: int, bitmask: int) -> bytes:
        # For this device, we normally use qty=8 and bytecount=1
        if qty < 1 or qty > 8:
            raise ValueError("qty must be 1..8 for this helper")
        bitmask &= 0xFF

        pdu = bytes(
            [
                slave_id,
                0x0F,
                cls._u16_hi(start_addr),
                cls._u16_lo(start_addr),
                cls._u16_hi(qty),
                cls._u16_lo(qty),
                0x01,  # byte count
                bitmask,
            ]
        )
        return cls._append_crc(pdu)

    @classmethod
    def _build_read_holding_registers(cls, slave_id: int, start_reg: int, qty: int) -> bytes:
        if not (1 <= qty <= 0x007D):
            raise ValueError("qty out of range for FC=0x03")
        pdu = bytes(
            [
                slave_id,
                0x03,
                cls._u16_hi(start_reg),
                cls._u16_lo(start_reg),
                cls._u16_hi(qty),
                cls._u16_lo(qty),
            ]
        )
        return cls._append_crc(pdu)

    @classmethod
    def _build_write_multiple_registers(cls, slave_id: int, start_reg: int, values: List[int]) -> bytes:
        qty = len(values)
        if qty < 1 or qty > 123:
            raise ValueError("FC=0x10 qty must be 1..123")
        byte_count = qty * 2
        data = bytearray()
        for v in values:
            v &= 0xFFFF
            data.append(cls._u16_hi(v))
            data.append(cls._u16_lo(v))

        pdu = bytes(
            [
                slave_id,
                0x10,
                cls._u16_hi(start_reg),
                cls._u16_lo(start_reg),
                cls._u16_hi(qty),
                cls._u16_lo(qty),
                byte_count,
            ]
        ) + bytes(data)
        return cls._append_crc(pdu)

    # --------------------------
    # Public builders (IO)
    # --------------------------
    @classmethod
    def read_do(cls, slave_id: int) -> bytes:
        # Wiki: 01 01 00 00 00 08 ...
        return cls._build_read_bits(slave_id, 0x01, 0x0000, 0x0008)

    @classmethod
    def read_di(cls, slave_id: int) -> bytes:
        # Wiki: 01 02 00 00 00 08 ...
        return cls._build_read_bits(slave_id, 0x02, 0x0000, 0x0008)

    @classmethod
    def set_do(cls, slave_id: int, channel_1_based: int, state: str) -> bytes:
        """
        state: 'on' | 'off' | 'toggle'
        channel_1_based: 1..8
        """
        if channel_1_based < 1 or channel_1_based > 8:
            raise ValueError("channel must be 1..8")
        addr = channel_1_based - 1  # 0x0000..0x0007
        value = cls._coil_value(state)
        # Wiki: FC=0x05 addr=0x0000..0x0007, value=FF00/0000/5500
        return cls._build_write_single(slave_id, 0x05, addr, value)

    @classmethod
    def set_all_do(cls, slave_id: int, state: str) -> bytes:
        value = cls._coil_value(state)
        # Wiki: addr fixed 0x00FF
        return cls._build_write_single(slave_id, 0x05, 0x00FF, value)

    @classmethod
    def write_do_mask(cls, slave_id: int, bitmask: int) -> bytes:
        # Wiki: FC=0x0F start=0x0000 qty=0x0008 bytecount=0x01 data=mask
        return cls._build_write_multiple_coils_8ch(slave_id, 0x0000, 0x0008, bitmask)

    # --------------------------
    # Output control mode (0x1000..0x1007)
    # --------------------------
    @classmethod
    def read_output_modes(cls, slave_id: int, start_ch_1_based: int = 1, count: int = 8) -> bytes:
        if start_ch_1_based < 1 or start_ch_1_based > 8:
            raise ValueError("start_ch must be 1..8")
        if count < 1 or (start_ch_1_based + count - 1) > 8:
            raise ValueError("count out of range")
        start_reg = 0x1000 + (start_ch_1_based - 1)
        return cls._build_read_holding_registers(slave_id, start_reg, count)

    @classmethod
    def set_output_mode(cls, slave_id: int, channel_1_based: int, mode: int) -> bytes:
        if channel_1_based < 1 or channel_1_based > 8:
            raise ValueError("channel must be 1..8")
        if mode < 0 or mode > 3:
            raise ValueError("mode must be 0..3")
        reg = 0x1000 + (channel_1_based - 1)
        return cls._build_write_single(slave_id, 0x06, reg, mode)

    @classmethod
    def set_output_modes(cls, slave_id: int, start_ch_1_based: int, modes: List[int]) -> bytes:
        if start_ch_1_based < 1 or start_ch_1_based > 8:
            raise ValueError("start_ch must be 1..8")
        if (start_ch_1_based + len(modes) - 1) > 8:
            raise ValueError("modes length out of range")
        for m in modes:
            if m < 0 or m > 3:
                raise ValueError("mode must be 0..3")
        start_reg = 0x1000 + (start_ch_1_based - 1)
        return cls._build_write_multiple_registers(slave_id, start_reg, modes)

    @staticmethod
    def _coil_value(state: str) -> int:
        s = (state or "").strip().lower()
        if s in ("on", "1", "true", "enable"):
            return 0xFF00
        if s in ("off", "0", "false", "disable"):
            return 0x0000
        if s in ("toggle", "tog"):
            return 0x5500
        raise ValueError("state must be on/off/toggle")

    # --------------------------
    # Parsers
    # --------------------------
    @classmethod
    def parse_bits(cls, response: bytes, expected_func: Optional[int] = None, expected_count: int = 8) -> List[int]:
        """
        Parse responses from FC=0x01 or FC=0x02:
        [addr][func][byte_count][data...][crc_lo][crc_hi]
        For reading 8 bits, byte_count should be 1 and only 1 data byte.
        """
        if not response or len(response) < 5:
            raise ModbusFrameError("response too short")

        cls._check_crc(response)

        addr = response[0]
        func = response[1]

        # Exception response: func | 0x80
        if func & 0x80:
            if len(response) < 5:
                raise ModbusFrameError("exception response too short")
            raise ModbusExceptionResponse(func, response[2])

        if expected_func is not None and func != expected_func:
            raise ModbusFrameError(f"unexpected function 0x{func:02X} (expected 0x{expected_func:02X})")

        byte_count = response[2]
        if byte_count < 1:
            raise ModbusFrameError("byte_count invalid")
        data_start = 3
        data_end = data_start + byte_count
        if len(response) < data_end + 2:
            raise ModbusFrameError("response truncated")

        data = response[data_start:data_end]
        bits: List[int] = []
        for b in data:
            for i in range(8):
                bits.append((b >> i) & 0x01)

        return bits[:expected_count]

    @classmethod
    def parse_holding_registers(cls, response: bytes, expected_count: int) -> List[int]:
        """
        Parse responses from FC=0x03:
        [addr][0x03][byte_count][data(2*count)][crc_lo][crc_hi]
        """
        if not response or len(response) < 5:
            raise ModbusFrameError("response too short")
        cls._check_crc(response)

        func = response[1]
        if func & 0x80:
            raise ModbusExceptionResponse(func, response[2])
        if func != 0x03:
            raise ModbusFrameError(f"unexpected function 0x{func:02X} (expected 0x03)")

        byte_count = response[2]
        if byte_count != expected_count * 2:
            raise ModbusFrameError(f"unexpected byte_count={byte_count} (expected {expected_count*2})")

        data = response[3 : 3 + byte_count]
        regs: List[int] = []
        for i in range(0, len(data), 2):
            regs.append((data[i] << 8) | data[i + 1])
        return regs
