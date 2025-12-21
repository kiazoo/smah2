# Log Service
## Overview
Log Service เป็น service กลางสำหรับรับ log event จากทุก service ในระบบ Smart-Shop
ผ่าน ZeroMQ Broker แล้วจัดเก็บลงฐานข้อมูลแบบ FIFO เพื่อใช้สำหรับ monitoring, debugging และส่งต่อให้ platform

## Architecture:
```
[ Any Service ]
     |
     | logger_client
     v
[ ZeroMQ Broker ]
     |
     v
[ log_service ]
     |
     v
[ SQLite (log.db) ]
```
## Features
* รองรับ log level: DEBUG, INFO, WARN, ERROR
* รับ log event ผ่าน broker (ZeroMQ)
* จัดเก็บ log แบบ FIFO สูงสุด 1000 records
* รองรับ query log ผ่าน broker
* ไม่ให้ service อื่นเข้าถึง DB โดยตรง

## Database
Location
```
db/log/log.db
```
Table: logs
|Column	|Type	|Description|
| ------------- | ------------- | ------------- |
|id	|INTEGER	|Auto increment
|timestamp	|TEXT	|ISO-8601 timestamp
|level	|TEXT	|DEBUG / INFO / WARN / ERROR
|service	|TEXT	|ชื่อ service ที่ส่ง log
|message	|TEXT	|log message
|trace_id	|TEXT	|optional correlation id
|extra	|TEXT	|JSON string

## FIFO Policy
หลัง insert ทุกครั้ง จะลบ log เก่าให้เหลือ 1000 record ล่าสุด

## Message Format
Log Event
```
{
  "timestamp": "2025-12-21T07:20:00Z",
  "level": "INFO",
  "service": "mock-worker",
  "message": "service started",
  "trace_id": null,
  "extra": {
    "pid": 1234
  }
}
```
## ZMQ Actions
### log

รับ log event จาก service
```
{
  "action": "log",
  "payload": { ...log_event... }
}
```
### query
ดึง log จากระบบ
Payload options:
```
{
  "level": "ERROR",
  "service": "mock-worker",
  "limit": 100
}
```
|Field	|Required	|Description|
| ------- | -------- | -----|
|level	|no	|filter ตาม level|
|service	|no	|filter ตาม service|
|limit	|no	|จำนวน record (default 100, max 1000)|

## Running
### Prerequisite
* Python 3.10+
* ZeroMQ broker ต้องรันอยู่
* Database schema ต้องถูกสร้างแล้ว

## Start Log Service
รันจาก project root เท่านั้น
```
cd ~/smart-shop-app
python3 -m services.log_service.log_service
```
## Testing
### Mock Log Sender
python3 mock_log_service.py

### Query Logs
```
python3 mock_log_query.py
```

### Development Notes
* log_service ใช้ DEALER socket
* recv_multipart() เป็น blocking call (ใช้ RCVTIMEO ใน debug mode)
* print(..., flush=True) ใช้เฉพาะ dev/debug
* production แนะนำให้รันผ่าน systemd



# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise