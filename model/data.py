import base64
from datetime import datetime
import logging
import os
import re
import secrets
import sqlite3
import threading
from typing import Optional, Tuple
import bcrypt
import fastapi

import config.config as config

logger = logging.getLogger(__name__)

# Pattern สำหรับตรวจสอบความปลอดภัยของ Identifier ใน SQL (Column/Table Name)
IDENTIFIER_REGEX = re.compile(r'^[a-zA-Z0-9_]+$')


class Database:

  def __init__(self, db_url: str):
    db_dir = os.path.dirname(db_url)
    if db_dir:
      os.makedirs(db_dir, exist_ok=True)
    else:
      os.makedirs('.', exist_ok=True)

    self.db = sqlite3.connect(db_url, check_same_thread=False, timeout=15)
    self.db.row_factory = sqlite3.Row
    self.schema = config.WEB_SCHEMA.get('webserver', {})
    self.db_schema = self.schema.get('database', {})
    self.columns_schema = self.db_schema.get('devices_table', [])
    self._lock = threading.Lock()

    with self._lock:
      try:
        cursor = self.db.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')

        self.CreateDeviceTable(cursor=cursor)
        self._ensure_schema_columns(cursor)

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
      except Exception as e:
        self.db.rollback()
        logger.error('Error during database initialization: %s', e)
        raise e

  # ================= Helper Security methods =================
  def _get_valid_table_columns(self, cursor: sqlite3.Cursor, table_name: str) -> set:
    if not IDENTIFIER_REGEX.match(table_name):
      return set()
    cursor.execute(f'PRAGMA table_info({table_name})')
    return {row[1] for row in cursor.fetchall()}

  def ensure_default_admin(self, username: str, password: str, role: str):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT COUNT(*) FROM users')
      count_row = cursor.fetchone()
      count = count_row[0] if count_row else 0
      if count > 0:
        return

    logger.warning(
        "No users found. Creating default admin account '%s'."
        ' Please log in and change the password immediately.',
        username,
    )
    self.register_user(username, password, role)

  # ================= User management methods =================
  def register_user(self, username: str, password: str, role: str):
    hashed_password = self.hash_password(password)
    with self._lock:
      try:
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT 1 FROM users WHERE username = ?', (username,)
        )
        result = cursor.fetchone()
        if result:
          return False, 'This user is already registered.'
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, hashed_password, role),
        )
        self.db.commit()
        return True, ''
      except Exception as e:
        self.db.rollback()
        logger.error('Error registering user %s: %s', username, e)
        return False, e

  def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(
          'SELECT password, role FROM users WHERE username = ?', (username,)
      )
      result = cursor.fetchone()

    if result:
      stored_hashed_password = result['password']
      user_role = result['role']

      if self.verify_password(password, stored_hashed_password):
        # อัปเดตเวลา last_login
        try:
          with self._lock:
            cur = self.db.cursor()
            cur.execute(
                'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?',
                (username,),
            )
            self.db.commit()
        except Exception as e:
          logger.warning('Could not update last_login for %s: %s', username, e)
        return True, user_role

    return False, None

  def hash_password(self, password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

  def verify_password(self, password: str, hashed: str) -> bool:
    try:
      return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
      logger.error('Password verification error: %s', e)
      return False

  def get_all_user(self):
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT id, username, role, last_login FROM users')
      return [dict(row) for row in cursor.fetchall()]

  def edit_user(self, id, username=None, password=None, role=None):
    update_fields = []
    params = []

    if username is not None:
      update_fields.append('username = ?')
      params.append(username)
    if password is not None:
      update_fields.append('password = ?')
      hash_pwd = self.hash_password(password)
      params.append(hash_pwd)
    if role is not None:
      update_fields.append('role = ?')
      params.append(role)

    if not update_fields:
      return False, 'No fields to update'

    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
    params.append(id)

    with self._lock:
      cursor = self.db.cursor()
      try:
        cursor.execute(query, tuple(params))
        self.db.commit()
        return True, 'UPDATE SUCCESFUL'
      except sqlite3.IntegrityError as e:
        self.db.rollback()
        return False, f'Username already exists: {e}'
      except Exception as e:
        self.db.rollback()
        logger.error('Error updating user id %s: %s', id, e)
        return False, e

  def delete_user(self, user_id: int):
    with self._lock:
      try:
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        self.db.commit()
        return True, 'DELETED'
      except Exception as e:
        self.db.rollback()
        logger.error('Error deleting user id %s: %s', user_id, e)
        return False, str(e)

  # ================= Device management methods =================
  def register_device(
      self,
      name: str,
      ip_address: str,
      mac_address: str,
      io_channel: dict,
      model_path: str,
      save_image_path: str,
      mqtt_broker: str,
      project_id: str = None,
      project_config: str = None,
      camera_config: str = None,
      io_config: str = None,
  ) -> str:
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT 1 FROM devices WHERE name = ?', (name,))
      if cursor.fetchone():
        raise fastapi.HTTPException(
            status_code=400, detail=f"Device name '{name}' already exists"
        )

      valid_cols = self._get_valid_table_columns(cursor, 'devices')

      base_cols = [
          'name',
          'ip_address',
          'mac_address',
          'model_path',
          'save_image_path',
          'mqtt_broker',
      ]
      base_vals = [
          name,
          ip_address,
          mac_address,
          model_path,
          save_image_path,
          mqtt_broker,
      ]

      optional_values = {
          'project_id': project_id,
          'project_config': project_config,
          'camera_config': camera_config,
          'io_config': io_config,
      }
      for key, value in optional_values.items():
        if key in valid_cols and value is not None:
          base_cols.append(key)
          base_vals.append(value)


      extra_cols = []
      extra_vals = []
      for k, v in io_channel.items():
        if IDENTIFIER_REGEX.match(k) and k in valid_cols:
          extra_cols.append(k)
          extra_vals.append(v)
        else:
          logger.warning('Skipping invalid or nonexistent column in register_device: %s', k)

      all_cols = base_cols + extra_cols + ['api_key']
      columns_str = ', '.join(all_cols)
      placeholders_str = ', '.join(['?'] * len(all_cols))

      sql_query = f'INSERT INTO devices ({columns_str}) VALUES ({placeholders_str})'

      max_retries = 5
      for _ in range(max_retries):
        api_key = secrets.token_hex(16)
        full_values = tuple(base_vals + extra_vals + [api_key])

        try:
          cursor.execute(sql_query, full_values)
          self.db.commit()
          return api_key
        except sqlite3.IntegrityError:
          self.db.rollback()
          continue
        except Exception as e:
          self.db.rollback()
          logger.error('Error inserting device: %s', e)
          raise fastapi.HTTPException(
              status_code=500, detail=f'Database error: {e}'
          )

    raise fastapi.HTTPException(
        status_code=400,
        detail=(
            'Failed to generate a unique API key after multiple attempts.'
            ' Please try again.'
        ),
    )

  def verify_api_key(self, api_key: str) -> Optional[dict]:
    if not api_key:
      return None
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute('SELECT * FROM devices WHERE api_key = ?', (api_key,))
      row = cursor.fetchone()
    return dict(row) if row else None

  def get_device_by_name(self, name: str) -> Optional[dict]:
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

  def get_device_by_id(self, device_id: int) -> Optional[dict]:
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
      self.db.rollback()
      logger.error('[Database Error] delete_device: %s', e)
      return False

  def _cleanup_device_files(self, device_id: int, image_files: list):
    upload_dir = getattr(config, 'UPLOAD_DIR', 'uploads')
    abs_upload_dir = os.path.abspath(upload_dir)

    for filename in image_files:
      if not filename:
        continue
      safe_filename = os.path.basename(filename)
      path = os.path.abspath(os.path.join(abs_upload_dir, safe_filename))

      if os.path.commonpath([abs_upload_dir, path]) == abs_upload_dir:
        try:
          if os.path.exists(path):
            os.remove(path)
        except Exception as e:
          logger.warning('Could not delete image %s: %s', path, e)
      else:
        logger.error('Security alert: Path traversal attempt blocked for: %s', filename)

    try:
      from model.mqtt import close_device_log_handlers, get_device_log_paths
      close_device_log_handlers(device_id)
      for log_path in get_device_log_paths(device_id):
        if os.path.exists(log_path):
          os.remove(log_path)
    except Exception as e:
      logger.warning('Could not delete log files for device %s: %s', device_id, e)

  # ================= Update device methods =================
  def update_device_config(self, api_key: str, payload: dict) -> bool:
    device = self.verify_api_key(api_key)
    if not device:
      logger.warning('update_device_config: Invalid API key (%s)', api_key)
      return False

    device_id = device.get('id')
    new_name = payload.get('name')

    if new_name and new_name != device.get('name'):
      existing = self.get_device_by_name(new_name)
      if existing and existing.get('id') != device_id:
        raise fastapi.HTTPException(
            status_code=400, detail=f"Device name '{new_name}' already exists"
        )

    with self._lock:
      cursor = self.db.cursor()
      valid_columns = self._get_valid_table_columns(cursor, 'devices')
      valid_columns.difference_update({'id', 'api_key'})

      update_fields = []
      params = []

      for key, value in payload.items():
        if IDENTIFIER_REGEX.match(key) and key in valid_columns and value is not None:
          update_fields.append(f'{key} = ?')
          params.append(value)

      if not update_fields:
        return False

      query = f"UPDATE devices SET {', '.join(update_fields)} WHERE id = ?"
      params.append(device_id)

      try:
        cursor.execute(query, tuple(params))
        self.db.commit()
      except Exception as e:
        self.db.rollback()
        logger.error('Error updating device config for id %s: %s', device_id, e)
        return False

    return True

  def update_device_all_status(self, api_key: str, **kwargs):
    device = self.verify_api_key(api_key)
    if not device:
      logger.warning(
          'update_device_all_status failed: Invalid API key (%s)', api_key
      )
      return None

    device_id = device.get('id')

    with self._lock:
      cursor = self.db.cursor()
      valid_columns = self._get_valid_table_columns(cursor, 'devices')
      valid_columns.difference_update({'id', 'api_key'})

      fields = []
      values = []

      for key, val in kwargs.items():
        if val is not None and IDENTIFIER_REGEX.match(key) and key in valid_columns:
          fields.append(f'{key} = ?')
          values.append(val)

      if 'last_seen' in self._get_valid_table_columns(cursor, 'devices'):
        fields.append('last_seen = CURRENT_TIMESTAMP')

      if not fields:
        return device_id

      query = f"UPDATE devices SET {', '.join(fields)} WHERE id = ?"
      values.append(device_id)

      try:
        cursor.execute(query, tuple(values))
        self.db.commit()
      except Exception as e:
        self.db.rollback()
        logger.error('Error updating device status for id %s: %s', device_id, e)
        return None

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
      self.db.rollback()
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

  def get_latest_log(self, device_id: int) -> Optional[dict]:
    with self._lock:
      cursor = self.db.cursor()
      cursor.execute(
          'SELECT * FROM logs WHERE device_id = ? ORDER BY log_time DESC'
          ' LIMIT 1',
          (device_id,),
      )
      row = cursor.fetchone()
    return dict(row) if row else None

  def base64_to_image(self, base64_string: str, device_id) -> Optional[str]:
    upload_dir = getattr(config, 'UPLOAD_DIR', 'uploads')
    abs_upload_dir = os.path.abspath(upload_dir)
    os.makedirs(abs_upload_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'device_{device_id}_{timestamp}.jpg'
    output_path = os.path.join(abs_upload_dir, filename)

    try:
      # จัดการกรณี base64 มี data URI scheme ติดมาด้วย
      if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]

      image_bytes = base64.b64decode(base64_string)

      with open(output_path, 'wb') as f:
        f.write(image_bytes)
      return filename
    except Exception as e:
      logger.error('Error saving image for device %s: %s', device_id, e)
      return None

  # ================= create table =================
  def _ensure_schema_columns(self, cursor):
    """Add newly configured device columns to existing SQLite databases."""
    valid_types = {'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC'}
    existing = self._get_valid_table_columns(cursor, 'devices')
    for col in self.columns_schema:
      key = col.get('key', '')
      if not IDENTIFIER_REGEX.match(key) or key in existing:
        continue
      col_type = str(col.get('type', 'TEXT')).upper()
      if col_type not in valid_types:
        col_type = 'TEXT'
      # New optional columns deliberately default to NULL so old devices remain valid.
      cursor.execute('ALTER TABLE devices ADD COLUMN {} {}'.format(key, col_type))
      existing.add(key)

  def CreateDeviceTable(self, cursor):
    columns = []

    base_col = [
        'id INTEGER PRIMARY KEY AUTOINCREMENT',
        'name TEXT NOT NULL',
        'ip_address TEXT NOT NULL',
        'mac_address TEXT NOT NULL',
        "model_path TEXT NOT NULL DEFAULT 'Yolov12best_bg_v2_openvino_model'",
        "save_image_path TEXT NOT NULL DEFAULT 'save_image_output'",
        "mqtt_broker TEXT NOT NULL DEFAULT 'broker.emqx.io'",
        'api_key TEXT NOT NULL UNIQUE',
        'last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    ]

    ALLOWED_SQL_TYPES = {'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC'}

    for col in self.columns_schema:
      key = col.get('key', '')
      if not IDENTIFIER_REGEX.match(key):
        logger.error('Invalid column name rejected: %s', key)
        continue

      col_type = col.get('type', 'TEXT').upper()
      if col_type not in ALLOWED_SQL_TYPES:
        col_type = 'TEXT'

      is_null = col.get('null', False)
      null_clause = '' if is_null else 'NOT NULL'

      default_val = col.get('default')
      if isinstance(default_val, str):
        # Escape single quote ใน default value
        safe_default = default_val.replace("'", "''")
        default_clause = f"DEFAULT '{safe_default}'"
      elif default_val is not None:
        default_clause = f'DEFAULT {default_val}'
      else:
        default_clause = ''

      col_def = (
          f'{key} {col_type} {null_clause} {default_clause}'.strip().replace(
              '  ', ' '
          )
      )
      columns.append(col_def)

    all_col = base_col + columns
    create_table_sql = f"CREATE TABLE IF NOT EXISTS devices ({', '.join(all_col)})"

    cursor.execute(create_table_sql)


database = Database

if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  db = Database('data/db_system.db')