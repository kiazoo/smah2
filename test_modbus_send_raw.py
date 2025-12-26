import time
import zmq
from shared.zmq_helper.message import build, loads, dumps

BROKER = "tcp://127.0.0.1:5555"
CLIENT = "modbus_test_client"
DRIVER = "modbus_driver_service"

def recv_any(sock, poller, timeout_ms=200):
    socks = dict(poller.poll(timeout_ms))
    if sock in socks and socks[sock] == zmq.POLLIN:
        frames = sock.recv_multipart()
        return loads(frames[-1])
    return None

def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    sock.identity = CLIENT.encode()
    sock.connect(BROKER)
    sock.setsockopt(zmq.LINGER, 0)

    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)

    # 1) register
    reg = build("register", CLIENT, "broker", "register")
    sock.send(dumps(reg))

    # 2) wait register ack (debug print everything)
    deadline = time.time() + 5
    reg_ack = None
    while time.time() < deadline:
        msg = recv_any(sock, poller, timeout_ms=200)
        if not msg:
            continue
        print("IN =", msg)
        if msg.get("type") == "response" and msg.get("correlation_id") == reg["msg_id"]:
            reg_ack = msg
            break

    if not reg_ack:
        raise SystemExit("No REGISTER_ACK from broker")

    print("REGISTER_ACK OK\n")

    # 3) send modbus.send_raw
    tx_hex = "01 02 00 00 00 08 79 CC"  # Read Discrete Inputs 8 points, slave=1

    req = build(
        "request",
        CLIENT,
        DRIVER,
        "modbus.send_raw",
        {
            "serial": {
                "baudrate": 9600,
                "parity": "N",
                "stopbits": 1,
                "bytesize": 8,
                "timeout": 1.0,
                "end_silence_ms": 50,
                "max_rx_bytes": 512,
            },
            "hex": tx_hex
        }
    )
    print("SEND REQ =", req)
    sock.send(dumps(req))

    # 4) wait response (print all incoming)
    deadline = time.time() + 5
    while time.time() < deadline:
        msg = recv_any(sock, poller, timeout_ms=200)
        if not msg:
            continue
        print("IN =", msg)

        if msg.get("type") == "response" and msg.get("correlation_id") == req["msg_id"]:
            print("\n✅ MODBUS_RESP =", msg)
            return

    raise SystemExit("❌ TIMEOUT waiting modbus.send_raw response (routing/driver issue)")

if __name__ == "__main__":
    main()
