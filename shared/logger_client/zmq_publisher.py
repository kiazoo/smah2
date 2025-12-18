from shared.zmq_helper.zmq_helper import create_pub, send_json

# singleton socket
_socket = None

def publish_log(record):
    global _socket
    if _socket is None:
        _socket = create_pub("tcp://*:6000")  # หรืออ่านจาก config
    send_json(_socket, record)
