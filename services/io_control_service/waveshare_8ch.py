"""
Helper class for constructing and parsing Modbus RTU frames for the
Waveshare 8‑channel digital input/output module (Modbus RTU IO 8CH).

This module provides static methods to build request frames for
reading the status of the eight discrete inputs and eight discrete
outputs of the module, as well as a parser to extract the bitfield
from responses.  The CRC16 calculation follows the standard Modbus
RTU polynomial (0xA001) and returns the CRC bytes in little‑endian
order as required by the protocol.

References:
  • Waveshare Modbus RTU IO 8CH wiki
    https://www.waveshare.com/wiki/Modbus_RTU_IO_8CH
"""

from __future__ import annotations

from typing import List


class Waveshare8CH:
    """Utilities for constructing and parsing Modbus RTU frames.

    The Waveshare 8‑channel digital I/O module uses standard Modbus RTU
    function codes to access its input and output status.  Reading the
    status of the outputs (coils) uses function code ``0x01`` while
    reading the status of the inputs uses function code ``0x02``.  Both
    commands read 8 bits starting at address ``0x0000``.  Frames are
    formed by appending a CRC16 (polynomial 0xA001) to the request.
    """

    @staticmethod
    def _calc_crc(data: bytes) -> bytes:
        """Compute the Modbus RTU CRC16 for the given data.

        Args:
            data: The bytes over which to compute the CRC.

        Returns:
            A 2‑byte sequence (low byte first, high byte second) representing
            the CRC16 checksum.
        """
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        # Return little‑endian CRC (low byte, high byte)
        return bytes((crc & 0xFF, (crc >> 8) & 0xFF))

    @classmethod
    def _build_read_frame(cls, slave_id: int, function: int, count: int) -> bytes:
        """Construct a read frame for coils or discrete inputs.

        This helper builds a Modbus RTU frame consisting of the slave
        address, function code, start address (0x0000), number of items to
        read, and CRC16 checksum.  The count must not exceed 8 since the
        module only supports eight channels.

        Args:
            slave_id: Modbus address of the target device (1–255).
            function: Modbus function code (0x01 for coils, 0x02 for inputs).
            count: Number of bits to read (should be 8).

        Returns:
            A bytes object containing the complete frame ready to send.
        """
        if not (1 <= slave_id <= 255):
            raise ValueError(f"Invalid slave_id {slave_id}; must be 1..255")
        if not (1 <= count <= 2000):
            raise ValueError(f"Invalid count {count}; must be 1..2000")
        # Assemble base frame without CRC
        frame = bytearray()
        frame.append(slave_id)
        frame.append(function)
        # Start address high and low bytes (0x0000)
        frame.extend((0x00, 0x00))
        # Number of items high and low bytes
        frame.extend(((count >> 8) & 0xFF, count & 0xFF))
        # Compute and append CRC16
        frame.extend(cls._calc_crc(bytes(frame)))
        return bytes(frame)

    @classmethod
    def read_do(cls, slave_id: int) -> bytes:
        """Return a Modbus RTU request frame to read all 8 digital outputs.

        The Waveshare IO 8CH module maps its eight outputs as coils.  To
        query the status of all eight outputs starting at address 0, we
        use function code ``0x01`` with a quantity of 8.

        Args:
            slave_id: Modbus address of the target device (1–255).

        Returns:
            A bytes object containing the read coils request.
        """
        # According to the Waveshare documentation, outputs are accessed via
        # function code 0x01 (Read Coils) with a quantity of 8.
        return cls._build_read_frame(slave_id, 0x01, 8)

    @classmethod
    def read_di(cls, slave_id: int) -> bytes:
        """Return a Modbus RTU request frame to read all 8 digital inputs.

        The Waveshare IO 8CH module maps its eight inputs as discrete
        inputs.  To query the status of all eight inputs starting at
        address 0, we use function code ``0x02`` with a quantity of 8.

        Args:
            slave_id: Modbus address of the target device (1–255).

        Returns:
            A bytes object containing the read discrete inputs request.
        """
        # According to the Waveshare documentation, inputs are accessed via
        # function code 0x02 (Read Discrete Inputs) with a quantity of 8.
        return cls._build_read_frame(slave_id, 0x02, 8)

    @staticmethod
    def parse_bits(response: bytes) -> List[int]:
        """Parse a response frame and return a list of bit values.

        This parser extracts the bitfield contained in a response to a
        ``Read Coils`` (0x01) or ``Read Discrete Inputs`` (0x02) command.
        The function assumes the response has the following format:

        ``<addr><func><byte_count><data...><crc_low><crc_high>``

        Where ``byte_count`` is the number of data bytes (should be 1 for
        reading 8 channels).  It then returns a list of bits (0 or 1)
        extracted from the data bytes, least significant bit first.

        Args:
            response: The raw response bytes from the device.

        Returns:
            A list of integers representing the state of each channel.  If
            the response is malformed or the byte count is zero, an
            empty list is returned.
        """
        # Minimum valid length is 5: addr, func, byte_count, data, crc_low, crc_high
        if not response or len(response) < 5:
            return []
        # Byte count indicates how many bytes of data follow
        byte_count = response[2]
        data_start = 3
        data_end = data_start + byte_count
        if len(response) < data_end + 2:  # Need space for CRC
            return []
        data_bytes = response[data_start:data_end]
        bits: List[int] = []
        for byte in data_bytes:
            for i in range(8):
                bits.append((byte >> i) & 0x01)
        # Truncate to 8 bits (module only has 8 channels)
        return bits[:8]