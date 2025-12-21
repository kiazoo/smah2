# 📦 README: Smartshop Shared Libraries

ชุด shared library กลางสำหรับทุก service ในระบบ Smartshop App
ออกแบบมาเพื่อให้ทุก service:

ใช้ pattern เดียวกัน ไม่เขียนโค้ดซ้ำ แยก concern ชัดเจน scale ได้ในระยะยาว

📁 Overview
```
shared/
├── zmq_helper        # inter-service communication
├── config_loader     # centralized configuration
├── db_helper         # database access layer
├── logger_client     # logging SDK (client-side)
├── health_client     # service health / heartbeat
└── buffer_client     # buffering / retry / offline queue
```
## 1️⃣ zmq_helper

### บทบาท:
shared lib สำหรับสื่อสารกับ Smartshop Communication Core (ZeroMQ)

ใช้เมื่อ:
* service ต้องคุยกับ broker
* ส่ง request / response
* register service

ตัวอย่าง:
```
from shared.zmq_helper.client import ZMQClient

client = ZMQClient(service_name="my-service")
client.register()

client.send_request(
    dst="echo-service",
    action="echo",
    payload={"msg": "hello"}
)
```

สถานะ: ✅ Production Ready (v1)

## 2️⃣ config_loader

บทบาท:
ศูนย์กลาง config ของทุก service

Priority:

ENV > config.db > config.json


ตัวอย่าง:
```
from shared.config_loader import config

broker = config.get("BROKER_CONNECT_ADDRESS")
```

สถานะ: ✅ Production Ready (v1)

## 3️⃣ db_helper

บทบาท:
ชั้นกลางสำหรับเข้าถึง SQLite database

รองรับ:
* config.db
* log.db
* buffer.db

ตัวอย่าง:
```
from shared.db_helper import db_log

rows = db_log.fetch_all("SELECT * FROM log")
```

สถานะ: ✅ Production Ready (v1)

## 4️⃣ logger_client

บทบาท:
SDK สำหรับเขียน log จากฝั่ง service

ทำพร้อมกัน 2 อย่าง:
* เขียน log ลง local DB (log.db)
* ส่ง log ไปยัง log_service แบบ real-time

ตัวอย่าง:
```
from shared.logger_client import logger

logger.info("service started")
logger.error("something failed", extra={"code": 500})
```

สถานะ: ✅ Production Ready (v1)

## 5️⃣ health_client

บทบาท:
shared lib สำหรับรายงานสุขภาพของ service (heartbeat / status)

ใช้เพื่อ:
* บอกว่า service ยังทำงานอยู่หรือไม่
* รายงานสถานะ RUNNING / DEGRADED / ERROR
* ใช้ร่วมกับ health_service

แนวคิดการใช้งาน:
```
from shared.health_client import health, HealthStatus

health.start()
health.set_status(HealthStatus.RUNNING)

```

ข้อมูลที่ส่งออก:

* service_name

* status

* uptime

* Dependency:

* zmq_helper

* config_loader

* logger_client

สถานะ: ✅ Usable / v1

## 6️⃣ buffer_client

บทบาท:
shared lib สำหรับ buffer / queue / retry

ใช้เมื่อ:

network ไม่เสถียร

broker ล่ม

service ปลายทางไม่พร้อม

offline-first

แนวคิดการใช้งาน:
```
from shared.buffer_client import buffer

buffer.push(event)
buffer.flush()
```

รูปแบบที่รองรับ (design):

FIFO

local DB (buffer.db)

flush เมื่อระบบพร้อม

สถานะ: 🟡 Scaffold Ready (v1.5)

เหมาะกับ ingestion / gateway / AI worker

🔗 Dependency Graph
```
config_loader
      ↓
zmq_helper ─── logger_client ─── db_helper
                         ↑
                   health_client
                         ↑
                   buffer_client
```


## ✅ Shared Lib Status Summary

| Library  | Status |
| ------------- | ------------- |
|zmq_helper|✅ v1|
|config_loader|✅ v1|
|db_helper|✅ v1|
|logger_client|✅ v1|
|health_client|🟡 v1.5|
|buffer_client|🟡 v1.5|

🧩 Design Principles
Shared lib = ไม่มี business logic
Service = ใช้ shared lib เป็น dependency
เปลี่ยน protocol / DB / transport → แก้ที่ shared lib จุดเดียว
Version shared lib ชัดเจน (v1, v2)

## 📌 Recommendation
ใช้ shared lib ชุดนี้เป็น canonical foundation
Service ใหม่ทุกตัว ต้อง import จาก shared
ถ้าจะเพิ่ม feature → เพิ่มใน shared ก่อนเสมอ


# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise
