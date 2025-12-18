# Health Service (Smartshop)

Health Service เป็น Supervisor Service สำหรับระบบ Smartshop
ทำหน้าที่ตรวจสอบสถานะ service อื่น ๆ ผ่าน heartbeat, ตรวจ timeout, restart อัตโนมัติ และรายงานสถานะไปยัง service กลาง

## ✨ Features

* รับ heartbeat จาก service อื่น (health.heartbeat)

* ตรวจ timeout และเปลี่ยนสถานะ RUNNING → TIMEOUT

* Restart service อัตโนมัติตาม policy

* Retry + cooldown

* Escalate เมื่อ retry ครบ (FAILED)

* ให้ endpoint ภายในผ่าน ZMQ:

        health.snapshot.get

        health.hw.get

        health.service.get

* เก็บ HW snapshot (CPU, Memory, Disk, Thermal, NPU)

## 📂 โครงสร้างไฟล์
```
health-service/
├── health_service.py
├── hw_collect.py
├── config.yaml
├── requirements.txt
├── README.md
└── venv/
```
## ⚙️ config.yaml (ตัวอย่าง)
```
service:
  name: health-service

comm_core:
  endpoint: tcp://127.0.0.1:5555

health:
  heartbeat_timeout_sec: 10

services:
  - name: mock-log-service
    service_id: mock-01
    enabled: true
    exec:
      restart: "systemctl restart mock-log-service"
    policy:
      max_retry: 3
      cooldown_sec: 10

auto_publish:
  enabled: true
  interval_sec: 5
  targets:
    - service: monitor-service
      action: health.snapshot
```

## ▶️ วิธีรัน (manual)
```
cd services/health-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 health_service.py
```

## 🔁 ZMQ Actions ที่รองรับ
| Action  | Description |
| ------------- | ------------- |
|health.heartbeat|	รับ heartbeat จาก service|
|health.snapshot.get|	snapshot service ทั้งหมด|
|health.hw.get|	snapshot hardware|
|health.service.get|	ดู service รายตัว|

# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise