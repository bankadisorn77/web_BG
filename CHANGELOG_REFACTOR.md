# สรุปการ Refactor โปรเจกต์ BG System

หลักการที่ยึดตลอดการแก้ไข: **ชื่อ field/คีย์ที่ใช้รับ-ส่งข้อมูลกับภายนอก
(MQTT topic, MQTT payload keys, REST API JSON fields, HTTP header) ไม่ถูกแก้ไข
แม้แต่ตัวเดียว** เพื่อไม่ให้กระทบ firmware ของอุปกรณ์ที่คุยกับระบบนี้อยู่ ได้แก่:

- MQTT topic prefix `BackgrindingMQTT` และรูปแบบ topic ทั้งหมด
- MQTT payload keys: `api_key`, `device_status`, `camera_status`,
  `gpio_status`, `program_status`, `relay_status`, `light_status`,
  `door_status`, `alarm_status`, `last_update`
- REST `/register_device` fields: `name`, `ip_address`, `mac_address`,
  `input_channel`, `output_alarm_channel`, `output_relay_channel`,
  `output_light_channel`, `model_path`, `save_image_path`, `mqtt_broker`
- REST `/image_log` fields: `image`, `detected_objects`, header `X-API-Key`

สิ่งที่แก้ไขได้ทั้งหมดด้านล่างนี้เป็นเรื่อง**ภายใน**ระบบเท่านั้น (ชื่อตัวแปร,
โครงสร้างโค้ด, การจัดการ state, การตั้งค่า) ไม่กระทบ protocol กับอุปกรณ์

---

## 1. บั๊ก/ช่องโหว่ที่แก้ไข (สำคัญ)

| จุด | ปัญหาเดิม | แก้เป็น |
|---|---|---|
| `page/loginPage.py` | ตรวจรหัสผ่านด้วย `USER = {'admin': '1234'}` ฝังในโค้ด (plain text) ทั้งที่มีระบบ bcrypt ใน DB อยู่แล้วแต่ไม่เคยถูกเรียกใช้ | ใช้ `database.authenticate_user()` จริง พร้อม bootstrap บัญชีแอดมินเริ่มต้นแบบ hash อัตโนมัติตอน start server (`model/data.py: ensure_default_admin`, ตั้งค่าได้ผ่าน env `BG_ADMIN_USERNAME` / `BG_ADMIN_PASSWORD`) |
| `server.py` | `UPDATE_DEVICE_ALL_CALLBACK` และ `UPDATE_LOG_CALLBACK` เป็นตัวแปร global เดี่ยว ถ้าเปิดหลายแท็บ/หลายอุปกรณ์พร้อมกัน callback ของหน้าที่โหลดทีหลังจะไปทับของหน้าก่อนหน้า ทำให้บางหน้าไม่อัปเดตข้อมูล | เปลี่ยนเป็น `DEVICE_LIST_CALLBACKS` (set) และ `LOG_CALLBACKS` (dict แยกตาม device_id) รองรับหลาย session พร้อมกัน เหมือนที่ `CARD_CALLBACKS`/`PAGE_CALLBACKS` ทำอยู่แล้ว |
| `server.py` | mount `StaticFiles(directory='uploads')` โดยไม่เช็คว่าโฟลเดอร์มีอยู่จริง ทำให้แอป crash ตั้งแต่ตอน start ถ้ายังไม่เคยมีการอัปโหลดรูปเลย | สร้างโฟลเดอร์ด้วย `os.makedirs(..., exist_ok=True)` ก่อน mount เสมอ |
| `model/data.py` | SQLite connection/cursor ตัวเดียวถูกใช้ร่วมกันระหว่าง thread ของ FastAPI/NiceGUI และ thread ของ MQTT client โดยไม่มีการล็อก เสี่ยง race condition เมื่อมีหลาย request/ข้อความเข้ามาพร้อมกัน | เพิ่ม `threading.Lock()` ครอบทุก query, ใช้ cursor ใหม่ต่อการเรียกแต่ละครั้งแทนการใช้ cursor ตัวเดียวร่วมกัน |
| `model/data.py` ตาราง `devices` | คอลัมน์ `Light_status` (L ใหญ่) ไม่ตรงกับ key อื่นที่เป็นตัวเล็กหมด ทำให้ต้องเขียนโค้ดเช็คสองชื่อ (`device.get('Light_status', device.get('light_status', ...))`) ในหลายจุด เสี่ยง bug ถ้ามีจุดไหนลืมเช็ค | เปลี่ยนเป็น `light_status` ให้ตรงกับคีย์อื่น พร้อมทำ migration อัตโนมัติสำหรับฐานข้อมูลเก่าที่เคยสร้างคอลัมน์เดิมไว้แล้ว (ข้อมูลอุปกรณ์ที่เคยลงทะเบียนไว้จะไม่หาย) |
| `model/data.py` | `update_device_config` ไม่เช็คว่าชื่ออุปกรณ์ใหม่ไปซ้ำกับเครื่องอื่นหรือไม่ (ต่างจาก `register_device` ที่เช็ค) เปลี่ยนชื่อซ้ำได้ทำให้แยกอุปกรณ์ไม่ออกในภายหลัง | เพิ่มการเช็คชื่อซ้ำก่อนบันทึก และแจ้ง error ที่อ่านเข้าใจได้บนหน้า config modal |
| `page/devicePage.py: switch_service` | เรียก `ui.notification(...)` ซึ่งไม่มี API นี้ใน NiceGUI (ของจริงคือ `ui.notify`) อาจทำให้เกิด error เวลาอุปกรณ์ไม่ ACTIVE แล้วกดปุ่ม START/STOP | แก้เป็น `ui.notify(...)` |
| `model/mqtt.py` | `DEVICE_CACHE` เป็น global dict ระดับโมดูล ถ้าในอนาคตมีการสร้าง `MQTT()` มากกว่า 1 instance (เช่น ต่อหลาย broker) ข้อมูลจะปนกัน | ย้ายมาเป็น `self.device_cache` (attribute ของ instance) |

## 2. โครงสร้าง/การตั้งค่า (Maintainability)

- **เพิ่ม `config.py`**: รวมค่าคงที่ที่เดิมฝังกระจายอยู่หลายไฟล์ (MQTT broker
  IP/port, session timeout, device timeout, path ของ DB/uploads/logs,
  storage secret) มาไว้ที่เดียว อ่านค่าจาก environment variable ได้ทั้งหมด
  ทำให้ deploy คนละ environment (dev/staging/prod) โดยไม่ต้องแก้โค้ด
- **เพิ่ม `requirements.txt`**: เดิมไม่มีไฟล์นี้เลย ทำให้ setup โปรเจกต์ใหม่
  บนเครื่องอื่นต้องเดาว่าต้องลง package อะไรบ้าง
- **ใช้ `logging` แทน `print`** ทุกจุดใน `server.py`, `model/data.py`,
  `model/mqtt.py` เพื่อให้ควบคุมระดับ log (INFO/WARNING/ERROR) และรูปแบบ
  timestamp ได้เป็นมาตรฐานเดียวกัน
- **แก้ชื่อตัวแปร/พารามิเตอร์ภายในที่สะกดผิดหรือสื่อความหมายไม่ชัด** (ไม่กระทบ
  ภายนอก): `device_page_stutus_update` → `on_device_status_update`,
  `badge_Alarm`/`badge_Relay`/`badge_ligh` → `badge_alarm`/`badge_relay`/
  `badge_light`, ตัวแปรใน `setting_config.py` (`inputChannel`, `outputAlarm`,
  `outputContor`, `outputStateMachine`) → ตั้งชื่อให้ตรงกับคีย์จริงที่ใช้
- **มาตรฐาน indentation**: ไฟล์ในโปรเจกต์เดิมผสมกันระหว่าง 2-space กับ 4-space
  ตอนนี้ปรับให้เป็น 2-space ทั้งหมดให้สอดคล้องกัน
- **เอา dead code ออก**: `component/setting_config.py` เดิมมี
  try/except ซ้อนกันสองชั้นโดยชั้นนอกไม่มีทางถูกเรียกถึง
- ลบ import ที่ไม่ได้ใช้ (`socket` ใน `camera_stream.py`, `app` ใน
  `homePage.py`) และแปลงไฟล์ที่มี line ending แบบ CRLF ปนอยู่ให้เป็น LF
  ทั้งไฟล์ (`camera_stream.py`)

## 3. สิ่งที่ตั้งใจ "ไม่" แตะ

- ชื่อ method สาธารณะของ `MQTT` และ `Database` (เช่น `connectMQ`,
  `on_program_control`, `register_device`, `update_device_all_status`) คงไว้
  เหมือนเดิมทั้งหมด เพราะถูกเรียกใช้ข้ามไฟล์หลายจุด การเปลี่ยนจะเพิ่มความเสี่ยง
  โดยไม่ได้ประโยชน์ด้าน maintainability มากนัก
- UI/CSS classes ของ NiceGUI ทั้งหมดคงเดิม ไม่เปลี่ยนหน้าตาแอป

## 4. สิ่งที่แนะนำให้ทำต่อ (ยังไม่ได้แก้ในรอบนี้)

1. **เปลี่ยนรหัสผ่านแอดมินเริ่มต้นทันทีหลัง deploy** — ตอนนี้ระบบ auto-สร้าง
   บัญชี `admin` / `admin1234` (ตั้งค่าเองได้ผ่าน env `BG_ADMIN_USERNAME`,
   `BG_ADMIN_PASSWORD`) ให้อัตโนมัติถ้ายังไม่มี user ใน DB เลย ควรมีหน้า
   "เปลี่ยนรหัสผ่าน" หรือคำสั่ง CLI สำหรับจัดการ user ในระยะยาว
2. **ตั้งค่า `BG_STORAGE_SECRET` และ `MQTT_BROKER` ผ่าน environment
   variable จริงตอน deploy** อย่าใช้ค่า default ที่มากับ `config.py`
3. พิจารณาเพิ่ม unit test ให้ `model/data.py` (ใช้ sqlite in-memory) และ
   `model/mqtt.py` (mock paho-mqtt client) เพราะตอนนี้ยังไม่มี test เลย
4. พิจารณาใช้ SQLAlchemy หรือ query builder แทน raw SQL string ต่อไป ถ้า
   schema เริ่มซับซ้อนขึ้นเรื่อยๆ ในอนาคต
