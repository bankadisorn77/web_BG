import os
import json
from dotenv import load_dotenv
load_dotenv()

# ------------------------------------------------------------------
# MQTT Configuration
# ------------------------------------------------------------------
MQTT_BROKER = os.environ.get('MQTT_BROKER', '169.254.26.65')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_TOPIC_PREFIX = os.environ.get('MQTT_TOPIC_PREFIX', 'BackgrindingMQTT')
DEVICE_TIMEOUT_SECONDS = int(os.environ.get('DEVICE_TIMEOUT_SECONDS', '60'))
# ------------------------------------------------------------------
# Web Session & Security
# ------------------------------------------------------------------
SESSION_TIMEOUT_SECONDS = int(os.environ.get('SESSION_TIMEOUT_SECONDS', '600'))
STORAGE_SECRET = os.environ.get('BG_STORAGE_SECRET', 'BGsystem')
# ------------------------------------------------------------------
# Database & File Storage
# ------------------------------------------------------------------
DB_PATH = os.environ.get('BG_DB_PATH', 'data/db_system.db')
UPLOAD_DIR = os.environ.get('BG_UPLOAD_DIR', 'uploads')
DEVICE_LOG_DIR = os.environ.get('BG_DEVICE_LOG_DIR', 'server_device_logs')
# ------------------------------------------------------------------
# Web Authentication
# ------------------------------------------------------------------
DEFAULT_ADMIN_USERNAME = os.environ.get('BG_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.environ.get('BG_ADMIN_PASSWORD', '1234')
DEFAULT_ADMIN_ROLE = os.environ.get('BG_ADMIN_ROLE', 'admin')
# ------------------------------------------------------------------
# Web Server Configuration
# ------------------------------------------------------------------
SERVER_HOST = os.environ.get('BG_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.environ.get('BG_SERVER_PORT', '8080'))

PLATFORM_NAME = os.environ.get('BG_PLATFORM_NAME', 'Vision Inspection Platform')

try:
    with open('config/device_schema.json', 'r', encoding='utf-8') as file:
        WEB_SCHEMA = json.load(file)
except Exception as e:
        WEB_SCHEMA = {}
        print('[Lode schema ERROR]',e)
