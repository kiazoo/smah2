# Smartshop Communication Core – ZeroMQ
Smartshop Communication Core คือ Message Bus กลางของระบบ Smartshop ที่ใช้ ZeroMQ ทำหน้าที่เป็นตัวกลางให้ microservices ทั้งหมดสื่อสารถึงกันแบบเร็ว เบา และไม่ต้องใช้ message broker ภายนอก เช่น Kafka หรือ RabbitMQ

ระบบนี้ประกอบด้วย 3 ส่วนหลัก:
1. **Broker (ROUTER socket)** – ตัวกลางรับ/ส่งข้อความ
2. **Service / Client (DEALER socket)** – Microservices ที่คุยผ่าน Core
3. **Message Format** – รูปแบบข้อมูลมาตรฐานที่ใช้สื่อสารกัน

---

## ✨ Features
- ใช้ ZeroMQ ROUTER/DEALER pattern
- รองรับการ register service เพื่อให้ broker จดจำปลายทาง
- ส่งข้อความแบบ request/response ระหว่าง services ได้
- รองรับ broadcast (ส่งหา service ทั้งหมด)
- ออกแบบแยกเป็น service-based structure
- มี systemd service สำหรับรัน broker แบบ background

---

# 🏗 Architecture Overview
```
     +---------------------+
     |     test-client     |
     |     (DEALER)        |
     +----------+----------+
                |
                v
+------------------- ROUTER ------------+
| Broker                                |
| - Service Registry                    |
| - Routing Logic                       |
+-------------------+-------------------+
                |
                v
    +----------+------------+
    | echo-service          |
    | (DEALER)              |
    +-----------------------+

```

# 📦 Message Format (Data Package)

ทุก service ต้องส่งข้อมูลในรูปแบบ JSON ดังนี้:

```json
{
  "msg_id": "uuid-xxxx",
  "type": "register | request | response | event",
  "src": "service-a",
  "dst": "service-b", 
  "action": "get_info",
  "payload": { "key": "value" },
  "correlation_id": "msg-id-of-request",
  "timestamp": "ISO8601"
}
```
Field อธิบาย|Field	ความหมาย 
-----|-----
msg_id	| UUID ของข้อความ
type	| ประเภทข้อความ (register, request, response, event)
src	| ชื่อ service ต้นทาง
dst	| ชื่อ service ปลายทาง หรือ "broadcast"
action	| คำสั่งที่ต้องการทำ
payload	| ข้อมูลที่ส่งไปด้วย
correlation_id	| ผูก request → response
timestamp	| เวลา ISO-8601



# 📁 Directory Structure
smartshop-comm-core/
  * core/
    * __init__.py
    * config.py
    * message.py
    * broker.py
  * services/
    * __init__.py
    * echo_service.py
    * test_client.py
  * install_broker.sh
  * README.md


# ⚙ การติดตั้ง
1) Clone หรือ copy โปรเจกต์
```
git clone <repo>
cd smartshop-comm-core
```
2) สร้างและติดตั้ง Virtual Environment
```
python3 -m venv venv
source venv/bin/activate
pip install pyzmq
```

3) ติดตั้ง Broker แบบ Auto-Service (systemd)
```
# รัน installer:

chmod +x install_broker.sh
./install_broker.sh
```

หลังติดตั้งเรียบร้อย systemd จะสร้าง service:

smartshop-broker.service

# 🚀 การใช้งาน
# ▶️ Start broker

(หลังติดตั้ง systemd)
```
sudo systemctl start smartshop-broker
```

ตรวจสอบ:
```
sudo systemctl status smartshop-broker
```

ดู log:

journalctl -u smartshop-broker -f

🧩 เขียน Service ใหม่ (DEALER)
โครงสร้างขั้นต่ำ
```python
import zmq
from core.message import build_message, loads, dumps

context = zmq.Context.instance()
socket = context.socket(zmq.DEALER)
socket.identity = b"your-service-name"
socket.connect("tcp://127.0.0.1:5555")

# Register
reg = build_message("register", "your-service-name", "broker", "register")
socket.send(dumps(reg))

# Loop
while True:
    frames = socket.recv_multipart()
    data = frames[-1]
    msg = loads(data)
    print("Got:", msg)
```

# 🧪 ทดสอบการทำงาน
ใน Services จะมีโปรแกรมสำหรับทดสอบการทำงานของ Broker
เปิด 3 terminal:

1) Broker (ถ้าไม่ใช้ systemd)
python3 -m core.broker

2) echo-service
python3 services/echo_service.py

3) test-client
python3 services/test_client.py


ผลที่ต้องได้:

test-client → ส่ง request

echo-service → ตอบกลับ

broker ทำ routing ถูกต้อง


# ! Troubleshooting
1) Broker crash: "expected 3 frames"

สาเหตุ: ROUTER ได้ frame 2 ชุด → ต้องรองรับทั้ง 2 และ 3 frames
(แก้แล้วในโค้ด broker เวอร์ชันล่าสุด)

2) JSONDecodeError ใน service

สาเหตุ: ใช้ .recv() แทน .recv_multipart().
วิธีแก้: ต้องใช้ .recv_multipart() เสมอ

3) Service ไม่ register

ให้เช็คว่าตั้งค่า identity เป็น byte string เช่น:

socket.identity = b"inventory-service"

4) พอร์ต 5555 ถูกจับอยู่
```
# ดู process:
sudo lsof -i :5555

# สั่ง kill
kill -9 <PID>
```



# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise