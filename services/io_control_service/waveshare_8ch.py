from .modbus_crc import append_crc


class Waveshare8CH:
    DI_START = 0
    DI_COUNT = 8
    DO_START = 0
    DO_COUNT = 8

    @staticmethod
    def read_di(slave_id: int) -> bytes:
        frame = bytes([
            slave_id,
            0x02,          # Read Discrete Inputs
            0x00, 0x00,    # start
            0x00, 0x08     # count
        ])
        return append_crc(frame)

    @staticmethod
    def read_do(slave_id: int) -> bytes:
        frame = bytes([
            slave_id,
            0x01,          # Read Coils
            0x00, 0x00,
            0x00, 0x08
        ])
        return append_crc(frame)

    @staticmethod
    def set_do(slave_id: int, channel: int, value: int) -> bytes:
        addr = channel - 1
        val = 0xFF00 if value else 0x0000
        frame = bytes([
            slave_id,
            0x05,                  # Write Single Coil
            0x00, addr,
            (val >> 8) & 0xFF,
            val & 0xFF
        ])
        return append_crc(frame)

    @staticmethod
    def parse_bits(resp: bytes) -> list[int]:
        if len(resp) < 4:
            return []
        byte = resp[3]
        return [(byte >> i) & 1 for i in range(8)]
