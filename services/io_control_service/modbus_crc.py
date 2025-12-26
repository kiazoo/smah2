def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def append_crc(data: bytes) -> bytes:
    crc = crc16(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
