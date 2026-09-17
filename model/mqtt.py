import asyncio
from collections import deque
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time

import paho.mqtt.client as MQ

import config.config as config

logger = logging.getLogger(__name__)

PAYLOAD_KEY_MAPPING = {
    'api_key': 'api_key',
    'camera_status': 'camera',
    'gpio_status': 'gpio',
    'program_status': 'program_status',
    'relay_status': 'relay_status',
    'light_status': 'light_status',
    'door_status': 'door_status',
    'alarm_status': 'alarm_status',
    'last_update': 'last_update',
}
STATUS_KEYS = [
    'device_status',
    'camera_status',
    'gpio_status',
    'program_status',
    'relay_status',
    'light_status',
    'door_status',
    'alarm_status',
]

LOG_DIR = config.DEVICE_LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)


def append_device_log(device_id, message: str):
  """เขียน log ของอุปกรณ์ลงไฟล์ โดยตั้งชื่อไฟล์ตาม device_id (ไม่ใช่ชื่อเครื่อง)

  เดิมใช้ชื่อเครื่องเป็นชื่อไฟล์ พอผู้ใช้เปลี่ยนชื่อเครื่องในหน้า config แล้ว
  ระบบจะไปสร้างไฟล์ log ใหม่ตามชื่อใหม่ ทำให้ log เก่าทั้งหมด "หาย" จากหน้าเว็บ
  (จริง ๆ ไฟล์เก่ายังอยู่แต่ไม่มีใครอ่าน) และถ้าชื่อมีอักขระที่ใช้เป็นชื่อไฟล์
  ไม่ได้ (/ \\ : * ? " < > |) จะเปิด/สร้างไฟล์ไม่ได้เลย
  -> เปลี่ยนมาใช้ device_id ซึ่งเป็น primary key ใน database ไม่มีวันเปลี่ยน
  และปลอดภัยกับ filesystem เสมอ
  """
  log_file = os.path.join(LOG_DIR, f'device_{device_id}.log')
  logger_for_device = logging.getLogger(f'dev_log_{device_id}')
  logger_for_device.setLevel(logging.INFO)
  logger_for_device.propagate = False

  if not logger_for_device.handlers:
    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    formatter = logging.Formatter(
        '[%(asctime)s] %(message)s', '%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger_for_device.addHandler(handler)

  logger_for_device.info(message)


def get_device_log_paths(device_id):
  """คืน path ของไฟล์ log ทั้งหมดของอุปกรณ์นี้ (รวมไฟล์ rotate .1 .2 .3)
  ใช้ตอนลบอุปกรณ์เพื่อเก็บกวาดไฟล์ให้หมด
  """
  base = os.path.join(LOG_DIR, f'device_{device_id}.log')
  return [base] + [f'{base}.{i}' for i in range(1, 6)]


def close_device_log_handlers(device_id):
  """ปิด file handler ของอุปกรณ์นี้ก่อนลบไฟล์ (สำคัญบน Windows ที่ลบไฟล์ซึ่ง
  ยังถูกเปิดค้างอยู่ไม่ได้)
  """
  lg = logging.getLogger(f'dev_log_{device_id}')
  for h in list(lg.handlers):
    try:
      h.close()
    except Exception:
      pass
    lg.removeHandler(h)


def get_recent_device_logs(device_id, lines: int = 100):
  log_file = os.path.join(LOG_DIR, f'device_{device_id}.log')
  if not os.path.exists(log_file):
    return []
  try:
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
      cleaned_logs = []
      for line in deque(f, maxlen=lines):
        clean_line = line.strip()
        clean_msg = re.sub(
            r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*', '', clean_line
        )
        cleaned_logs.append(clean_msg)
      return cleaned_logs
  except Exception as e:
    logger.error('[Log Read Error] %s', e)
    return []


class MQTT:

  def __init__(
      self,
      broker: str = None,
      port: int = None,
      database=None,
      on_card_update=None,
      on_page_update=None,
      on_terminal_log=None,
  ):
    self.database = database
    self.prefix = config.MQTT_TOPIC_PREFIX
    self.broker = broker or config.MQTT_BROKER
    self.port = port or config.MQTT_PORT
    self.client = MQ.Client(callback_api_version=MQ.CallbackAPIVersion.VERSION2)
    self.is_connected = False
    self.client.on_connect = self._on_connect
    self.client.on_disconnect = self._on_disconnect
    self.client.on_message = self._on_message

    self.client.reconnect_delay_set(min_delay=2, max_delay=30)

    self.pattern = re.compile(
        rf'^{self.prefix}/(?P<device>[^/]+)/(?P<subpath>.+)$'
    )
    self.on_card_update = on_card_update
    self.on_page_update = on_page_update
    self.on_terminal_log = on_terminal_log

    self.device_cache = {}
    self.main_loop = None
    self._heartbeat_task = None
    self._reconnect_task = None
    self._should_run = False
    self.TIMEOUT_THRESHOLD = config.DEVICE_TIMEOUT_SECONDS

  def topic(self, device_name='+'):
    sub_status = f'{self.prefix}/{device_name}/status'
    sub_heartbeat = f'{self.prefix}/{device_name}/heartbeat'
    sub_logs = f'{self.prefix}/{device_name}/logs'
    pub_program_control = f'{self.prefix}/{device_name}/program/control'
    pub_program_config = f'{self.prefix}/{device_name}/program/config'
    pub_delete_device = f'{self.prefix}/{device_name}/delete'
    return [sub_status, sub_heartbeat, sub_logs], [
        pub_program_control,
        pub_program_config,
        pub_delete_device,
    ]

  def _on_connect(self, client, userdata, flags, rc, properties=None):
    if rc == 0:
      self.is_connected = True
      sub_topics, _ = self.topic(device_name='+')
      for t in sub_topics:
        self.client.subscribe(t, qos=0)
      logger.info('Connected to %s:%s', self.broker, self.port)
    else:
      self.is_connected = False
      logger.error('Connection refused with code: %s', rc)

  def _on_disconnect(
      self, client, userdata, disconnect_flags, rc, properties=None
  ):
    self.is_connected = False
    logger.warning('Disconnected from broker (rc=%s).', rc)

  def _on_message(self, client, userdata, msg):
    match = self.pattern.match(msg.topic)
    if not match:
      return
    device_name = match.group('device')
    subpath = match.group('subpath')

    if subpath == 'logs':
      log_text = msg.payload.decode('utf-8', errors='ignore').strip()
      if log_text:
        # ผูก log กับ device_id (คงที่ตลอดอายุอุปกรณ์) ไม่ใช่ชื่อเครื่องที่
        # ผู้ใช้เปลี่ยนได้ ไม่งั้นพอเปลี่ยนชื่อแล้ว log เก่าจะหายไปจากหน้าเว็บ
        device_id = self._resolve_device_id(device_name)
        if device_id is not None:
          append_device_log(device_id, log_text)
          if (
              self.on_terminal_log
              and self.main_loop
              and not self.main_loop.is_closed()
          ):
            self.main_loop.call_soon_threadsafe(
                self.on_terminal_log, device_id, log_text
            )
      return

    try:
      payload_str = msg.payload.decode('utf-8')
      data = json.loads(payload_str)
    except Exception:
      data = {}

    if subpath == 'heartbeat':
      self.onHeartbeat(data=data,device_name=device_name)
    self._touch_device(device_name, data.get('api_key'))
    if subpath == 'status':
      self.onUpdateStatus(data, device_name)

  async def _reconnect_monitor_loop(self):
    while self._should_run:
      try:
        if not self.is_connected:
          logger.info(
              '[MQTT Watcher] Reconnecting to %s:%s...', self.broker, self.port
          )
          try:
            self.client.reconnect()
          except Exception:
            try:
              self.client.connect_async(self.broker, self.port, keepalive=60)
            except Exception as e:
              logger.error('[MQTT Watcher] Connect failed: %s', e)

        await asyncio.sleep(5)
      except asyncio.CancelledError:
        break
      except Exception as e:
        logger.error('[MQTT Watcher] Error: %s', e)
        await asyncio.sleep(5)

  def connectMQ(self):
    try:
      logger.info('Connecting to %s:%s...', self.broker, self.port)
      self._should_run = True

      try:
        self.main_loop = asyncio.get_running_loop()
      except RuntimeError:
        self.main_loop = asyncio.get_event_loop()

      self.client.loop_start()

      try:
        self.client.connect_async(self.broker, self.port, keepalive=60)
      except Exception as e:
        logger.error('Initial connect_async failed: %s', e)

      if self._heartbeat_task is None or self._heartbeat_task.done():
        self._heartbeat_task = self.main_loop.create_task(
            self._watchdog_timeout_loop()
        )

      if self._reconnect_task is None or self._reconnect_task.done():
        self._reconnect_task = self.main_loop.create_task(
            self._reconnect_monitor_loop()
        )

    except Exception as e:
      logger.error('Error connect async: %s', e)
      self.is_connected = False

  def disconnectMQ(self):
    try:
      self._should_run = False
      self.is_connected = False
      if self._reconnect_task and not self._reconnect_task.done():
        self._reconnect_task.cancel()
      if self._heartbeat_task and not self._heartbeat_task.done():
        self._heartbeat_task.cancel()

      self.client.loop_stop()
      self.client.disconnect()
    except Exception:
      pass

  def on_program_control(self, msg, device_name='TEST'):
    if self.is_connected:
      try:
        _, pub_topics = self.topic(device_name)
        payload = json.dumps(msg) if isinstance(msg, (dict, list)) else str(msg)
        self.client.publish(pub_topics[0], payload)
      except Exception as e:
        logger.error('Error publish status: %s', e)

  def on_send_config(self, msg, device_name='TEST'):
    if self.is_connected:
      try:
        _, pub_topics = self.topic(device_name)
        payload = json.dumps(msg) if isinstance(msg, (dict, list)) else str(msg)
        self.client.publish(pub_topics[1], payload)
      except Exception as e:
        logger.error('Error publish config: %s', e)

  def on_del_device(self, msg, device_name='TEST'):
    logger.info('Delete device name: %s', device_name)
    self.device_cache.pop(device_name, None)
    if self.is_connected:
      try:
        _, pub_topics = self.topic(device_name)
        payload = json.dumps(msg) if isinstance(msg, (dict, list)) else str(msg)
        self.client.publish(pub_topics[2], payload)
      except Exception as e:
        logger.error('Error publish delete: %s', e)

  def _resolve_device_id(self, device_name: str):
    """หา device_id จากชื่อเครื่องที่มากับ MQTT topic (cache ไว้ใน device_cache
    เพื่อไม่ต้อง query database ทุกครั้งที่มี log เข้ามา ซึ่งถี่มาก)
    """
    cached = self.device_cache.get(device_name, {})
    device_id = cached.get('device_id')
    if device_id is not None:
      return device_id
    if not self.database:
      return None
    row = self.database.get_device_by_name(device_name)
    if not row:
      return None
    device_id = row.get('id')
    self._touch_device(device_name, row.get('api_key'))
    self.device_cache[device_name]['device_id'] = device_id
    return device_id

  def _touch_device(self, device_name: str, api_key: str = None):
    now = time.time()
    if device_name not in self.device_cache:
      self.device_cache[device_name] = {
          'state': {},
          'last_seen': now,
          'api_key': api_key,
          'is_error': False,
      }
    else:
      self.device_cache[device_name]['last_seen'] = now
      self.device_cache[device_name]['is_error'] = False
      if api_key:
        self.device_cache[device_name]['api_key'] = api_key

  def onUpdateStatus(self, data, device_name):
    payload = self.map_payload_to_params(data)
    if not payload.get('api_key'):
      cached_key = self.device_cache.get(device_name, {}).get('api_key')
      if not cached_key and self.database:
        dev_row = self.database.get_device_by_name(device_name)
        cached_key = dev_row.get('api_key') if dev_row else None
      payload['api_key'] = cached_key

    self.checkStatusUpdate(payload, device_name)

  def onHeartbeat(self,data,device_name):
      self._touch_device(device_name, data.get('api_key'))
      running_val = data.get('Running Status', data.get('status'))
      if running_val in ('ON', 'ACTIVE'):
        target_status = 'ACTIVE'
      elif running_val in ('OFF', 'INACTIVE'):
        target_status = 'INACTIVE'
      else:
        target_status = None

      if not target_status:
        return

      cached_info = self.device_cache.get(device_name, {})
      api_key = cached_info.get('api_key')
      device_row = None
      if self.database:
        device_row = self.database.get_device_by_name(device_name)
        if not api_key:
          api_key = device_row.get('api_key') if device_row else None
          cached_info['api_key'] = api_key

      if not api_key:
        return

      current_status = device_row.get('device_status') if device_row else None

      if current_status != target_status:
        try:
          device_id = self.database.update_device_all_status(
              api_key=api_key, device_status=target_status
          )
          if device_id:
            cached_info.setdefault('state', {})['device_status'] = target_status
            self._dispatch_ui_update(
                device_id, {'device_status': target_status}
            )
            logger.info(
                '[%s] Heartbeat confirmed: status -> %s',
                device_name,
                target_status,
            )
        except Exception as e:
          logger.error(
              '[%s] Failed to update heartbeat status: %s', device_name, e
          )
      return

  def map_payload_to_params(self, payload: dict) -> dict:
    mapped_params = {}
    for param_name, payload_key in PAYLOAD_KEY_MAPPING.items():
      raw_value = payload.get(payload_key)
      if param_name == 'api_key':
        mapped_params['api_key'] = raw_value
      elif param_name == 'last_update':
        continue
      else:
        mapped_params[param_name] = raw_value
    return mapped_params

  def _dispatch_ui_update(self, device_id, data):
    if not self.main_loop or self.main_loop.is_closed():
      return

    raw_payload = {
        'device_status': data.get('device_status'),
        'camera': data.get('camera_status'),
        'gpio': data.get('gpio_status'),
        'program': data.get('program_status'),
        'relay_status': data.get('relay_status'),
        'light_status': data.get('light_status'),
        'door_status': data.get('door_status'),
        'alarm_status': data.get('alarm_status'),
    }
    # กันฟิลด์ที่ไม่ได้ส่งมาในรอบนี้ (None) ไปเขียนทับค่าดีๆ เดิมบนการ์ด/หน้า
    # device เช่น ตอนนี้ status topic ไม่มี device_status แล้ว ถ้าไม่กรอง
    # None ออก การ์ดจะโดนเซ็ต device_status เป็น None ทุกครั้งที่ door/relay
    # เปลี่ยน ทำให้ badge ขึ้น "DEVICE: None"
    ui_card_payload = {k: v for k, v in raw_payload.items() if v is not None}

    if self.on_card_update and device_id and ui_card_payload:
      self.main_loop.call_soon_threadsafe(
          self.on_card_update, device_id, ui_card_payload
      )

    if self.on_page_update:
      self.main_loop.call_soon_threadsafe(self.on_page_update)

  def checkStatusUpdate(self, data, device_name):
    self._touch_device(device_name, data.get('api_key'))
    cached_info = self.device_cache[device_name]
    old_state = cached_info['state']
    has_changed = False

    for key in STATUS_KEYS:
      new_value = data.get(key, None)
      if new_value is not None and new_value != old_state.get(key, None):
        has_changed = True
        old_state[key] = new_value

    if not old_state or has_changed:
      try:
        device_id = self.database.update_device_all_status(**data)
        if device_id:
          self._dispatch_ui_update(device_id, data)
      except Exception as e:
        logger.error('[%s] Error updating database: %s', device_name, e)

  async def _watchdog_timeout_loop(self):
    while self._should_run:
      try:
        await asyncio.sleep(5)
        now = time.time()

        for device_name, info in list(self.device_cache.items()):
          current_device_status = info.get('state', {}).get('device_status')
          if current_device_status == 'INACTIVE' or info.get('is_error'):
            continue

          # ขาดการติดต่อเกินกว่าค่าที่กำหนด
          if (now - info['last_seen']) >= self.TIMEOUT_THRESHOLD:
            logger.warning(
                '[Watchdog] Device %s lost response (>%ss) -> Setting to ERROR',
                device_name,
                self.TIMEOUT_THRESHOLD,
            )
            info['is_error'] = True

            api_key = info.get('api_key')
            if not api_key and self.database:
              dev_row = self.database.get_device_by_name(device_name)
              api_key = dev_row.get('api_key') if dev_row else None

            if api_key:
              timeout_payload = {
                  'api_key': api_key,
                  'device_status': 'ERROR',
                  'camera_status': 'OFF',
                  'gpio_status': 'OFF',
                  'program_status': 'OFF',
                  'relay_status': 'OFF',
                  'light_status': 'OFF',
                  'door_status': 'OFF',
                  'alarm_status': 'OFF',
              }

              for k in STATUS_KEYS:
                info['state'][k] = timeout_payload[k]

              try:
                device_id = self.database.update_device_all_status(
                    **timeout_payload
                )
                if device_id:
                  self._dispatch_ui_update(device_id, timeout_payload)
              except Exception as e:
                logger.error(
                    '[Watchdog] Failed to update timeout status: %s', e
                )

      except asyncio.CancelledError:
        break
      except Exception as e:
        logger.error('Watchdog loop error: %s', e)
