
# 📡 tb_control_service
## Overview

tb_control_service เป็น Service กลางสำหรับรับคำสั่งจาก ThingsBoard
ทำหน้าที่แปลง RPC / Attribute Update จาก ThingsBoard
ให้กลายเป็นคำสั่งภายในระบบ Smart-Shop

## Responsibilities

* subscribe RPC จาก ThingsBoard (MQTT)
* validate + parse command
* forward command เข้า Smart-Shop ผ่าน ZeroMQ
* ส่ง RPC response กลับ ThingsBoard

## Architecture
~~~
ThingsBoard
   |
   |  RPC (MQTT)
   v
+--------------------+
| tb_control_service |
+--------------------+
        |
        | ZMQ request
        v
 [ uplink_service / other services ]
~~~
## Supported RPC Methods
update_uplink_config

ใช้สำหรับเปิด/ปิด uplink และปรับ interval แบบ runtime

RPC Payload (ThingsBoard)
~~~
{
  "uplinks": [
    {
      "name": "http_test",
      "enabled": false
    },
    {
      "name": "thingsboard",
      "interval_sec": 30
    }
  ]
}
~~~
## Effect
* แก้ config.yaml
* uplink_service reload config อัตโนมัติ
* ไม่มี restart service

## ThingsBoard UI Setup (Summary)
* Device → RPC
* Method: update_uplink_config
* Type: Server-side RPC
* Payload: JSON (ตาม schema ด้านบน)

##Run
~~~
python3 -m services.tb_control_service.tb_control_service
~~~

## Logs (ตัวอย่าง)
~~~
[tb_control_service] RPC update_uplink_config received
[tb_control_service] forward to uplink_service
[tb_control_service] response sent to ThingsBoard
~~~

## Design Notes
* tb_control_service ไม่แก้ config เอง
* uplink_service เป็น owner ของ uplink runtime state
* รองรับการขยายไปควบคุม service อื่น (GPIO, Modbus, AI, ฯลฯ)

## Roadmap (Optional)
* ACL per RPC method
* Config validation schema
* Versioned config
* Audit log (who changed what)

# 🤝 License

โปรเจกต์นี้ใช้ภายใน Smartshop AI / DTC Enterprise

# 💗 Contact

ผู้ดูแลโปรเจกต์
>P’ Jum — AIoT R&D & Sourcing Manager   
>Pink - Assistance  
>D.T.C. Enterprise
