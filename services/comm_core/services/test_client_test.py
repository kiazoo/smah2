from shared.zmq_helper.client import ZMQClient

client = ZMQClient("test-client")
resp = client.register()
print("[test-client] registered:", resp)

# ส่ง request ไปหา echo-service
client.send_request(
    dst="echo-service",
    action="echo",
    payload={"text": "Hello from test-client!"}
)
print("[test-client] request sent")

# รอ response
msg = client.recv()
print("[test-client] response:", msg)
