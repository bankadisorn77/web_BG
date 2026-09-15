import os

# ------------------------------------------------------------------
# MQTT
# ------------------------------------------------------------------
MQTT_BROKER = os.environ.get('MQTT_BROKER', '169.254.26.65')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_TOPIC_PREFIX = os.environ.get('MQTT_TOPIC_PREFIX', 'BackgrindingMQTT')

# เวลา (วินาที) ที่ไม่มีข้อความจากอุปกรณ์เข้ามาแล้วถือว่าอุปกรณ์หลุด/ERROR
DEVICE_TIMEOUT_SECONDS = int(os.environ.get('DEVICE_TIMEOUT_SECONDS', '60'))

# ------------------------------------------------------------------
# Web session
# ------------------------------------------------------------------
SESSION_TIMEOUT_SECONDS = int(os.environ.get('SESSION_TIMEOUT_SECONDS', '600'))

# ควรตั้งค่านี้ผ่าน environment variable จริงเวลา deploy ใช้งานจริง
# (ค่า default ใช้ได้เฉพาะตอนพัฒนา/ทดสอบเท่านั้น)
STORAGE_SECRET = os.environ.get('BG_STORAGE_SECRET', 'BGsystem')

# ------------------------------------------------------------------
# Path ต่างๆ
# ------------------------------------------------------------------
DB_PATH = os.environ.get('BG_DB_PATH', 'data/db_system.db')
UPLOAD_DIR = os.environ.get('BG_UPLOAD_DIR', 'uploads')
DEVICE_LOG_DIR = os.environ.get('BG_DEVICE_LOG_DIR', 'server_device_logs')

# ------------------------------------------------------------------
# บัญชีผู้ดูแลระบบเริ่มต้น (ใช้ตอนยังไม่มี user ใดๆ ใน database เลย)
# แนะนำให้ตั้งค่าใหม่ผ่าน environment variable แล้วเปลี่ยนรหัสผ่านทันทีหลัง deploy
# ------------------------------------------------------------------
DEFAULT_ADMIN_USERNAME = os.environ.get('BG_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.environ.get('BG_ADMIN_PASSWORD', '1234')
DEFAULT_ADMIN_ROLE = os.environ.get('BG_ADMIN_ROLE', 'admin')

# ------------------------------------------------------------------
# Uvicorn server
# ------------------------------------------------------------------
SERVER_HOST = os.environ.get('BG_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.environ.get('BG_SERVER_PORT', '8080'))
