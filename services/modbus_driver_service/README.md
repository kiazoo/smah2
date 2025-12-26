# Modbus Driver Service (RS-485 / Modbus RTU)

Modbus Driver Service เป็นบริการที่ทำหน้าที่ “ติดต่อกับฮาร์ดแวร์โดยตรง” ผ่าน RS-485 / Modbus RTU  
และเป็นตัวกลางให้ service อื่น ๆ (เช่น io controller / tb-control) เรียกใช้งานผ่าน broker โดยส่ง **raw modbus payload** (ไม่ decode)

---

## Key Concepts (ตามคอนเซปต์ระบบ)
1) Driver เป็นผู้รู้จัก serial port “คนเดียวเท่านั้น” (ในงานนี้คือ `/dev/ttyS0`)  
2) ฝั่ง application ส่ง “short config” (baudrate/parity/stopbits/timeout ฯลฯ) มาพร้อม request เพื่อรองรับ multi-baudrate  
3) ส่ง/รับเป็น **raw modbus RTU frame (hex)** รวม CRC แล้ว ไม่มีการ decode ใน driver  
4) มี config file (YAML) เก็บค่า port และ default serial config  
5) รับคำสั่งจาก TB / platform อื่น ผ่าน service ชั้นบนที่ส่ง request เข้ามา (driver ทำแค่ raw IO)  
6) มีระบบ log ส่งเข้า `log-service` (ผ่าน LoggerClient) และมี console debug เปิด/ปิดได้

---

## Features (เวอร์ชันปัจจุบัน)
- ✅ Register กับ broker ด้วย schema “Variant A” (พิสูจน์แล้ว broker ACK)
- ✅ `ping` สำหรับ health check ผ่าน broker
- ✅ `modbus.send_raw` รับ/ส่ง hex raw
- ✅ เปิด serial ค้างไว้ + reopen เมื่อ serial config สำคัญเปลี่ยน (baud/parity/stopbits/bytesize/timeout)
- ✅ มี queue รองรับหลาย request (ยิง serial ทีละงานแบบ FIFO ที่พอร์ต)
- ✅ keepalive re-register เป็นระยะ ป้องกัน route หลุด
- ✅ log ผ่าน `log-service` โดยแก้ปัญหา identity ชน: logger ใช้ identity แยก (`<service>.logger`)

---

## Folder
- `services/modbus_driver_service/modbus_driver_service.py` : ตัว service
- `services/modbus_driver_service/config.yaml` : config

---

## Config (`config.yaml`)
ตัวอย่าง key สำคัญ:

```yaml
service:
  name: modbus_driver_service

comm_core:
  endpoint: tcp://127.0.0.1:5555

serial:
  port: /dev/ttyS0
  defaults:
    baudrate: 9600
    parity: N
    stopbits: 1
    bytesize: 8
    timeout: 1.0
    end_silence_ms: 50
    max_rx_bytes: 512

driver:
  queue_max: 200
  keepalive_register_sec: 30

log:
  level: DEBUG
  log_hex: true
  print_debug: true
```

## Broker Register Schema (สำคัญ)
Driver ต้อง register ด้วยรูปแบบนี้ (Variant A):
```
{
  "msg_id": "...",
  "type": "register",
  "src": "modbus_driver_service",
  "dst": "broker",
  "action": "register",
  "service_name": "modbus_driver_service",
  "payload": {},
  "correlation_id": null,
  "timestamp": "..."
}
```
## Message API ผ่าน Broker
1) ping

Request
```
{
  "type": "request",
  "dst": "modbus_driver_service",
  "action": "ping",
  "payload": {}
}
```

Response
```
{
  "type": "response",
  "action": "ping",
  "payload": {"status":"ok"}
}
```
2) modbus.send_raw

ส่ง raw hex (รวม CRC) + short serial config

Request
```
{
  "type": "request",
  "dst": "modbus_driver_service",
  "action": "modbus.send_raw",
  "payload": {
    "serial": {
      "baudrate": 9600,
      "parity": "N",
      "stopbits": 1,
      "bytesize": 8,
      "timeout": 1.0,
      "end_silence_ms": 50,
      "max_rx_bytes": 512
    },
    "hex": "01 02 00 00 00 08 79 CC"
  }
}
```

Response
```
{
  "type": "response",
  "action": "modbus.send_raw",
  "payload": {
    "status":"ok",
    "hex":"01 02 01 20 A0 50",
    "rx_len": 6,
    "rtt_ms": 86
  }
}
```
## Run (Manual)

จาก root repo (/home/dtcaiot/smart-shop-app)
```
PYTHONPATH=. python3 -m services.modbus_driver_service.modbus_driver_service
```

ทดสอบ:
```
python3 test_modbus_send_raw.py
```
## Run (Auto via systemd)
service ที่เกี่ยวข้องในเครื่องนี้

smartshop-broker.service

log-service.service

health-service.service

tb-control-service.service

uplink-service.service

modbus-driver-service.service (ตัวนี้)

## ติดตั้ง/อัปเดต unit

ไฟล์: /etc/systemd/system/modbus-driver-service.service

แนะนำให้ผูก dependency:

After/Wants: smartshop-broker.service, log-service.service

คำสั่ง:
```
sudo systemctl daemon-reload
sudo systemctl enable modbus-driver-service
sudo systemctl restart modbus-driver-service
sudo systemctl status modbus-driver-service --no-pager
```

## ดู log:
```
journalctl -u modbus-driver-service -f
```
## Permissions: /dev/ttyS0

Driver ต้องอ่าน/เขียน /dev/ttyS0 ได้ (โดยทั่วไปต้องอยู่ group dialout)

ตรวจ:
```
ls -l /dev/ttyS0
id dtcaiot
```

เพิ่ม:
```
sudo usermod -aG dialout dtcaiot
# แล้ว logout/login หรือ reboot
```
## Troubleshooting
1) Register timeout แต่ probe ACK ได้

สาเหตุหลักที่เคยเจอ: identity ชนจาก logger/client socket
แนวทางแก้ในเวอร์ชันนี้:

register ให้ผ่านก่อน

logger ใช้ identity แยก: <service>.logger

2) เปิดพอร์ตไม่ได้ / Permission denied

ตรวจ group /dev/ttyS0

ห้ามรัน mbpoll พร้อมกันกับ driver

3) ไม่มี response (rx_len=0)

ตรวจว่า hex request ถูกต้อง (รวม CRC)

ตรวจ serial short config ให้ตรง baud/parity/stopbits

ตรวจ wiring RS-485 / A/B / termination / slave id

# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise