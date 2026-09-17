import base64
from datetime import datetime
import logging
import os
import secrets
import sqlite3
import threading
from typing import Tuple, Optional
import bcrypt
import fastapi

import config.config as config

logger = logging.getLogger(__name__)


class Database:

  def __init__(self, db_url: str):
    os.makedirs(os.path.dirname(db_url) or '.', exist_ok=True)
    self.db = sqlite3.connect(db_url, check_same_thread=False, timeout=15)
    self.db.row_factory = sqlite3.Row
    self._lock = threading.Lock()

    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('PRAGMA journal_mode=WAL;')

      cursor.execute("""CREATE TABLE IF NOT EXISTS devices (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              ip_address TEXT NOT NULL default '',
              mac_address TEXT NOT NULL default '',
              gpio TEXT NOT NULL default 'OFF',
              camera TEXT NOT NULL default 'OFF',
              program TEXT NOT NULL default 'OFF',
              device_status TEXT NOT NULL default 'INACTIVE',
              door_status TEXT NOT NULL default 'CLOSE',
              alarm_status TEXT NOT NULL default 'OFF',
              relay_status TEXT NOT NULL default 'OFF',
              light_status TEXT NOT NULL default 'OFF',
              input_channel INTEGER NOT NULL default 0,
              output_alarm_channel INTEGER NOT NULL default 0,
              output_relay_channel INTEGER NOT NULL default 1,
              output_light_channel INTEGER NOT NULL default 2,
              model_path TEXT NOT NULL default 'Yolov12best_bg_v2_openvino_model',
              save_image_path TEXT NOT NULL default 'save_image_output',
              mqtt_broker TEXT NOT NULL default 'broker.emqx.io',
              api_key TEXT NOT NULL unique,
              last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          )""")
      cursor.execute("""CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'user',
              last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          )""")
      cursor.execute("""CREATE TABLE IF NOT EXISTS logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              device_id INTEGER NOT NULL,
              image_path TEXT NOT NULL,
              detected_objects TEXT,
              log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (device_id) REFERENCES devices (id)
          )""")
      self.db.commit()


  def ensure_default_admin(self, username: str, password: str, role: str):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT COUNT(*) FROM users')
      (count,) = cursor.fetchone()
      if count > 0:
        return
    logger.warning(
        "No users found. Creating default admin account '%s'."
        ' Please log in and change the password immediately.',
        username,
    )
    self.register_user(username, password,role)

  # ================= User management methods =================
  def register_user(self, username: str, password: str, role: str):
    hashed_password = self.hash_password(password)
    with self._lock:
      try:
        cursor = self.db.cursor()
        cursor.execute(
                  'SELECT password FROM users WHERE username = ?', (username,)
              )
        result = cursor.fetchone()
        if result:
          return False,'This user is already registered.'
        cursor.execute(
            'INSERT INTO users (username, password,role) VALUES (?, ?, ?)',
            (username, hashed_password,role),
        )
        self.db.commit()
        return True,''
      except Exception as e:
        return False,e

  def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
    with self._lock:
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT password, role FROM users WHERE username = ?', (username,)
        )
        result = cursor.fetchone()
    if result:
        stored_hashed_password = result[0]
        user_role = result[1]
        
        if self.verify_password(password, stored_hashed_password):
            return True, user_role  

    return False, None  

  def hash_password(self, password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

  def verify_password(self, password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

  def get_all_user(self):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(
        'SELECT * FROM users'
      )
      return [dict(row) for row in cursor.fetchall()]
    
  def edit_user(self,id,username=None,password=None,role=None):
      update_fields = []
      params = []
      if username is not None:
        update_fields.append('username = ?')
        params.append(username)
      if password is not None:
        update_fields.append('password = ?')
        hash = self.hash_password(password)
        params.append(hash)
      if role is not None:
        update_fields.append('role = ?')
        params.append(role)
      if not update_fields:
        return False
      
      query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
      params.append(id)
      with self._lock:
          cursor = self.db.cursor()
          try:
            cursor.execute(query,tuple(params))
            return True,'UPDATE SUCCESFUL'
          except Exception as e:
            return False,e
          
  def delete_user(self, user_id: int):
      with self._lock:
          try:
              cursor = self.db.cursor()
              cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
              self.db.commit()
              
              return True, 'DELETED'
          except Exception as e:
              self.db.rollback()
              return False, str(e)
  # ================= Device management methods =================
  def register_device(
      self,
      name: str,
      ip_address: str,
      mac_address: str,
      input_channel: int,
      output_alarm_channel: int,
      output_relay_channel: int,
      output_light_channel: int,
      model_path: str,
      save_image_path: str,
      mqtt_broker: str,
  ) -> str:
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT 1 FROM devices WHERE name = ?', (name,))
      if cursor.fetchone():
        raise fastapi.HTTPException(
            status_code=400, detail=f"Device name '{name}' already exists"
        )

      max_retries = 5
      for _ in range(max_retries):
        api_key = secrets.token_hex(16)
        try:
          cursor.execute(
              """INSERT INTO devices (
                          name, ip_address, mac_address, input_channel,
                          output_alarm_channel, output_relay_channel, output_light_channel,
                          model_path, save_image_path, mqtt_broker, api_key
                      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (
                  name,
                  ip_address,
                  mac_address,
                  input_channel,
                  output_alarm_channel,
                  output_relay_channel,
                  output_light_channel,
                  model_path,
                  save_image_path,
                  mqtt_broker,
                  api_key,
              ),
          )
          self.db.commit()
          return api_key
        except sqlite3.IntegrityError:
          continue

    raise fastapi.HTTPException(
        status_code=400,
        detail=(
            'Failed to generate a unique API key after multiple attempts.'
            ' Please try again.'
        ),
    )

  def verify_api_key(self, api_key: str) -> dict:
    if not api_key:
      return None
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT * FROM devices WHERE api_key = ?', (api_key,))
      row = cursor.fetchone()
    return dict(row) if row else None

  def get_device_by_name(self, name: str) -> dict:
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT * FROM devices WHERE name = ?', (name,))
      row = cursor.fetchone()
    return dict(row) if row else None

  def get_device_counts(self):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT COUNT(*) FROM devices')
      total = cursor.fetchone()[0]

      cursor.execute(
          "SELECT COUNT(*) FROM devices WHERE device_status = 'ACTIVE'"
      )
      active = cursor.fetchone()[0]

      cursor.execute(
          "SELECT COUNT(*) FROM devices WHERE device_status = 'INACTIVE'"
      )
      inactive = cursor.fetchone()[0]

      cursor.execute(
          "SELECT COUNT(*) FROM devices WHERE device_status = 'ERROR'"
      )
      error = cursor.fetchone()[0]

    return total, active, inactive, error

  def get_all_devices(self):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT * FROM devices')
      return [dict(row) for row in cursor.fetchall()]

  def get_device_by_id(self, device_id: int):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
      row = cursor.fetchone()
    return dict(row) if row else None

  def delete_device(self, device_id: int) -> bool:
    try:
      image_files = [
          row.get('image_path')
          for row in self.get_logs(device_id)
          if row.get('image_path')
      ]

      with self._lock:
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM logs WHERE device_id = ?', (device_id,))
        cursor.execute('DELETE FROM devices WHERE id = ?', (device_id,))
        self.db.commit()
        deleted = cursor.rowcount > 0

      if deleted:
        self._cleanup_device_files(device_id, image_files)
      return deleted
    except Exception as e:
      logger.error('[Database Error] delete_device: %s', e)
      return False

  def _cleanup_device_files(self, device_id: int, image_files: list):
    upload_dir = getattr(config, 'UPLOAD_DIR', 'uploads')
    for filename in image_files:
      path = os.path.join(upload_dir, os.path.basename(filename))
      try:
        if os.path.exists(path):
          os.remove(path)
      except Exception as e:
        logger.warning('Could not delete image %s: %s', path, e)
    try:
      from model.mqtt import close_device_log_handlers, get_device_log_paths
      close_device_log_handlers(device_id)
      for log_path in get_device_log_paths(device_id):
        if os.path.exists(log_path):
          os.remove(log_path)
    except Exception as e:
      logger.warning('Could not delete log files for device %s: %s', device_id, e)

  # ================= Update device methods =================
  def update_device_config(
      self,
      api_key: str,
      name: str = None,
      input_channel: int = None,
      output_alarm_channel: int = None,
      output_relay_channel: int = None,
      output_light_channel: int = None,
      model_path: str = None,
      mqtt_broker: str = None,
  ):
    device = self.verify_api_key(api_key)
    if not device:
      logger.warning('update_device_config: Invalid API key (%s)', api_key)
      return False

    device_id = device.get('id')
    if name is not None and name != device.get('name'):
      existing = self.get_device_by_name(name)
      if existing and existing.get('id') != device_id:
        raise fastapi.HTTPException(
            status_code=400, detail=f"Device name '{name}' already exists"
        )

    update_fields = []
    params = []

    if name is not None:
      update_fields.append('name = ?')
      params.append(name)
    if input_channel is not None:
      update_fields.append('input_channel = ?')
      params.append(input_channel)
    if output_alarm_channel is not None:
      update_fields.append('output_alarm_channel = ?')
      params.append(output_alarm_channel)
    if output_relay_channel is not None:
      update_fields.append('output_relay_channel = ?')
      params.append(output_relay_channel)
    if output_light_channel is not None:
      update_fields.append('output_light_channel = ?')
      params.append(output_light_channel)
    if model_path is not None:
      update_fields.append('model_path = ?')
      params.append(model_path)
    if mqtt_broker is not None:
      update_fields.append('mqtt_broker = ?')
      params.append(mqtt_broker)

    if not update_fields:
      return False

    query = f"UPDATE devices SET {', '.join(update_fields)} WHERE id = ?"
    params.append(device_id)
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(query, tuple(params))
      self.db.commit()
    return True

  def update_device_all_status(
      self,
      api_key: str,
      device_status: str = None,
      camera_status: str = None,
      gpio_status: str = None,
      program_status: str = None,
      relay_status: str = None,
      light_status: str = None,
      door_status: str = None,
      alarm_status: str = None,
      **kwargs,
  ):
    device = self.verify_api_key(api_key)
    if not device:
      logger.warning(
          'update_device_all_status failed: Invalid API key (%s)', api_key
      )
      return None

    device_id = device.get('id')
    fields = []
    values = []

    status_mapping = {
        'device_status': device_status,
        'camera': camera_status,
        'gpio': gpio_status,
        'program': program_status,
        'relay_status': relay_status,
        'light_status': light_status,
        'door_status': door_status,
        'alarm_status': alarm_status,
    }

    for col, val in status_mapping.items():
      if val is not None:
        fields.append(f'{col} = ?')
        values.append(val)

    fields.append('last_seen = CURRENT_TIMESTAMP')

    query = f"UPDATE devices SET {', '.join(fields)} WHERE id = ?"
    values.append(device_id)
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(query, tuple(values))
      self.db.commit()

    return device_id

  # ================= Log management methods =================
  def add_log(
      self,
      api_key: str,
      image_input_path: str,
      detected_objects: str = None,
  ) -> bool:
    device = self.verify_api_key(api_key)
    if not device:
      logger.warning('add_log failed: Invalid API key (%s)', api_key)
      return False

    try:
      device_id = device.get('id')
      image_output_path = self.base64_to_image(image_input_path, device_id)
      if not image_output_path:
        return False

      detection_info = detected_objects if detected_objects else None
      with self._lock:
        cursor = self.db.cursor()
        cursor.execute(
            'INSERT INTO logs (device_id, image_path, detected_objects)'
            ' VALUES (?, ?, ?)',
            (device_id, image_output_path, detection_info),
        )
        self.db.commit()
      return True
    except Exception as e:
      logger.error('Error adding log: %s', e)
      return False

  def get_logs(self, device_id: int):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(
          'SELECT * FROM logs WHERE device_id = ? ORDER BY log_time DESC',
          (device_id,),
      )
      return [dict(row) for row in cursor.fetchall()]

  def get_latest_log(self, device_id: int):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(
          'SELECT * FROM logs WHERE device_id = ? ORDER BY log_time DESC'
          ' LIMIT 1',
          (device_id,),
      )
      row = cursor.fetchone()
    return dict(row) if row else None

  def base64_to_image(self, base64_string: str, device_id):
    upload_dir = getattr(config, 'UPLOAD_DIR', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'device_{device_id}_{timestamp}.jpg'
    output_path = os.path.join(upload_dir, filename)

    try:
      with open(output_path, 'wb') as f:
        f.write(base64.b64decode(base64_string))
      return filename
    except Exception as e:
      logger.error('Error saving image: %s', e)
      return None


database = Database

if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  db = Database('data/db_system.db')
