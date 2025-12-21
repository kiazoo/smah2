# 📦 uplink_service
## Overview

uplink_service เป็น Service กลาง (Central Uplink Gateway) ของ Smart-Shop Platform
ทำหน้าที่รับข้อมูลจาก service ภายในทั้งหมด แล้วจัดการส่งข้อมูลขึ้น platform ภายนอก เช่น
* ThingsBoard (HTTP / MQTT)
* HTTP Endpoint (Node-RED, Backend อื่น)
* MQTT Broker ภายนอก

โดยรองรับ:
* multi-uplink
* runtime enable/disable
* buffering + retry
* hot-reload config
* health snapshot integration

## Responsibilities

* รับ push_data จาก internal services ผ่าน ZeroMQ
* aggregate ข้อมูลต่อ uplink แบบ stateful
* ดึง health snapshot จาก health_service
* ส่งข้อมูลขึ้น platform ตาม schedule
* buffer ข้อมูลเมื่อส่งไม่สำเร็จ และ flush เมื่อกลับมา online
* รับ config update จาก ThingsBoard RPC (ผ่าน tb_control_service)

## Architecture
~~~
[ internal services ]
        |
        |  push_data (ZMQ)
        v
+--------------------+
|  uplink_service    |
|--------------------|
| Aggregator         |
| BufferStore        |
| HealthClient       |
| ConfigManager      |
+--------------------+
   |        |        |
   |        |        |
ThingsBoard  HTTP   MQTT
~~~

## Payload Flow
### Input (push_data)
~~~
{
  "source": "sensor_1",
  "data": {
    "temperature": 29.4,
    "humidity": 74
  }
}
~~~
### Output (uplink payload)
~~~
{
  "device_id": "SMARTSHOP-001",
  "timestamp": "2025-12-21T14:36:01.503Z",
  "services": {
    "sensor_1": {
      "temperature": 29.4,
      "humidity": 74
    }
  },
  "health": {
    "status": "ok",
    "cpu": 32.1,
    "ram": 41.2
  }
}
~~~
## Configuration

📄 services/uplink_service/config.yaml
~~~
device:
  id: SMARTSHOP-001

broker:
  address: tcp://127.0.0.1:5555

uplinks:
  - name: thingsboard
    type: thingsboard
    enabled: true
    protocol: http
    host: xio.dtciot.com
    token: XXXXX
    interval_sec: 10

  - name: http_test
    type: http
    enabled: true
    url: http://203.150.210.39:8900/uplink
    interval_sec: 10
~~~

⚠️ config สามารถถูกแก้ runtime ผ่าน ThingsBoard RPC ได้

## Runtime Behavior
* ถ้า ไม่มี data ใหม่ → ไม่ยิง uplink
* ถ้า ส่งไม่สำเร็จ → เก็บลง buffer
* ถ้า server กลับมา → flush buffer อัตโนมัติ
* health จะส่งเฉพาะเมื่อเปลี่ยนค่า

## Run
~~~
python3 -m services.uplink_service.uplink_service
~~~
## Logs (ตัวอย่าง)
~~~
[uplink_service] RECV push_data from=sensor_service
[uplink_service] sent uplink=http_test
[uplink_service] sent uplink=thingsboard
~~~
## Key Design Decisions
* Aggregator แยก state ต่อ uplink
* device_id / timestamp ถูก enforce ที่ uplink layer
* uplink_service ไม่สนใจ schema ภายในของ service
* HTTP uplink ไม่ใช้ 4xx/5xx สำหรับ telemetry validation

# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise
