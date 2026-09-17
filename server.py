from contextlib import asynccontextmanager
import logging
import os
import time

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from nicegui import app, ui
import uvicorn

import config.config as config
from model.data import Database
from model.mqtt import MQTT
from model.stream_hub import StreamHub
from page.devicePage import devicePage
from page.homePage import homePage
from page.loginPage import loginPage
from page.registerPage import RegisterPage
from page.managementPage import Management

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

SESSION_TIMEOUT = config.SESSION_TIMEOUT_SECONDS
CARD_CALLBACKS = set()
PAGE_CALLBACKS = set()
DEVICE_LIST_CALLBACKS = set()
LOG_CALLBACKS = {} 
TERMINAL_LOG_CALLBACKS = {}
OFFLINE_FRAME = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'
    b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19'
    b'\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444'
    b"\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00"
    b'\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01'
    b'\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf'
    b'\x00\xff\xd9'
)

def trigger_card_update(device_id, payload):
  for cb in list(CARD_CALLBACKS):
    try:
      cb(device_id, payload)
    except Exception:
      CARD_CALLBACKS.discard(cb)


def trigger_page_update():
  for cb in list(PAGE_CALLBACKS):
    try:
      cb()
    except Exception:
      PAGE_CALLBACKS.discard(cb)


def trigger_device_list_update():
  for cb in list(DEVICE_LIST_CALLBACKS):
    try:
      cb()
    except Exception:
      DEVICE_LIST_CALLBACKS.discard(cb)


def trigger_log_update(device_id):
  for cb in list(LOG_CALLBACKS.get(device_id, set())):
    try:
      cb()
    except Exception:
      LOG_CALLBACKS.get(device_id, set()).discard(cb)


def trigger_terminal_log_update(device_id, message):
  cbs = TERMINAL_LOG_CALLBACKS.get(device_id, set())
  for cb in list(cbs):
    try:
      cb(message)
    except Exception:
      cbs.discard(cb)


def register_log_callback(device_id, callback):
  LOG_CALLBACKS.setdefault(device_id, set()).add(callback)


database = Database(config.DB_PATH)
database.ensure_default_admin(
    config.DEFAULT_ADMIN_USERNAME, config.DEFAULT_ADMIN_PASSWORD,config.DEFAULT_ADMIN_ROLE
)

mq = MQTT(
    database=database,
    on_card_update=trigger_card_update,
    on_page_update=trigger_page_update,
    on_terminal_log=trigger_terminal_log_update,
)


# ดึงภาพจาก edge เส้นเดียวต่อกล้อง แล้วกระจายให้ผู้ชมทุกคน (ดู model/stream_hub.py)
stream_hub = StreamHub()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
  mq.connectMQ()
  yield
  mq.disconnectMQ()
  stream_hub.shutdown()


server_app = FastAPI(title='BG System API', lifespan=lifespan)
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
server_app.mount('/media', StaticFiles(directory=config.UPLOAD_DIR), name='media')


def keep_alive():
  if app.storage.user.get('authenticated', False):
    app.storage.user['last_active'] = time.time()


def check_auth() -> bool:
  if not app.storage.user.get('authenticated', False):
    ui.navigate.to('/login')
    return False

  last_active = app.storage.user.get('last_active', time.time())
  current_time = time.time()

  if current_time - last_active > SESSION_TIMEOUT:
    app.storage.user.clear()
    ui.notify('Session timeout due to inactivity.', color='warning')
    ui.navigate.to('/login')
    return False

  return True


def logout():
  app.storage.user.clear()
  ui.navigate.to('/login')


@ui.page('/login')
def login_page():
  if app.storage.user.get('authenticated', False):
    ui.navigate.to('/')
    return
  loginPage(database=database)

@ui.page('/register')
def reg_page():
  if not check_auth():
    return
  RegisterPage(database=database,logout=logout)
  ui.timer(1.0, check_auth)

@ui.page('/management')
def reg_page():
  # if not check_auth():
  #   return
  Management(database=database,logout=logout)
  # ui.timer(1.0, check_auth)


@ui.page('/')
def main():
  if not check_auth():
    return
  homePage(
      logout=logout,
      database=database,
      mq=mq,
      on_device_update=CARD_CALLBACKS.add,
      on_device_update_all=DEVICE_LIST_CALLBACKS.add,
  )
  ui.timer(1.0, check_auth)


@ui.page('/device/{device_id}')
def device_page(device_id: int):
  if not check_auth():
    return
  device = database.get_device_by_id(device_id)
  if not device:
    ui.notify('Device not found', color='negative')
    ui.navigate.to('/')
    return

  device_name = device.get('name', '')

  def register_terminal_listener(callback):
    TERMINAL_LOG_CALLBACKS.setdefault(device_id, set()).add(callback)

  devicePage(
      device_id=device_id,
      logout=logout,
      database=database,
      keep_alive_func=keep_alive,
      mq=mq,
      on_log_update=lambda func: register_log_callback(device_id, func),
      on_device_status_update=PAGE_CALLBACKS.add,
      on_terminal_log_register=register_terminal_listener,
  )
  ui.timer(1.0, check_auth)




@server_app.post('/register_device')
async def register_device(payload: dict = Body(...)):
  try:
    api_key = database.register_device(
        payload.get('name'),
        payload.get('ip_address'),
        payload.get('mac_address'),
        payload.get('input_channel'),
        payload.get('output_alarm_channel'),
        payload.get('output_relay_channel'),
        payload.get('output_light_channel'),
        payload.get('model_path'),
        payload.get('save_image_path'),
        payload.get('mqtt_broker'),
    )
    trigger_device_list_update()
    return {'api_key': api_key}
  except HTTPException:
    raise
  except Exception as e:
    logger.error('Error registering device: %s', e)
    raise HTTPException(status_code=500, detail='Internal server error')


@server_app.post('/image_log')
async def image_log(
    payload: dict = Body(...), x_api_key: str = Header(..., alias='X-API-Key')
):
  image = payload.get('image')
  detected_objects = payload.get('detected_objects', None)
  device = database.verify_api_key(x_api_key)
  success = database.add_log(
      api_key=x_api_key,
      image_input_path=image,
      detected_objects=detected_objects,
  )
  if not success:
    raise HTTPException(status_code=400, detail='Failed to add log')
  if device:
    trigger_log_update(device.get('id'))
  return {'message': 'Log added successfully'}


def is_request_authenticated(request: Request) -> bool:
  try:
    return bool(app.storage.user.get('authenticated', False))
  except Exception:
    session_id = request.session.get('id') if 'session' in request.scope else None
    if not session_id:
      return False
    user_storage = getattr(app.storage, '_users', {}).get(session_id)
    if user_storage is None:
      return False
    try:
      return bool(user_storage.get('authenticated', False))
    except Exception:
      return False


@app.get('/stream/{device_id}/{cam_index}')
async def stream_device(request: Request, device_id: int, cam_index: int):
  if not is_request_authenticated(request):
    raise HTTPException(status_code=401, detail='Not authenticated')

  device = database.get_device_by_id(device_id)
  if not device or not device.get('ip_address'):
    raise HTTPException(status_code=404, detail='Device not found or has no IP')

  source_url = (
      f"http://{device['ip_address']}:{config.EDGE_MJPEG_PORT}"
      f'/video_feed_{cam_index}'
  )
  key = (device_id, cam_index)

  def frame_generator():
    stream_hub.acquire(key, source_url)
    yield (
        b'--frame\r\n'
        b'Content-Type: image/jpeg\r\n'
        b'Content-Length: '
        + str(len(OFFLINE_FRAME)).encode()
        + b'\r\n\r\n'
        + OFFLINE_FRAME
        + b'\r\n'
    )

    try:
      last_sent = None
      no_frame_count = 0
      while True:
        frame = stream_hub.get_frame(key)

        if frame is not None and frame is not last_sent:
          last_sent = frame
          no_frame_count = 0
          yield (
              b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n'
              b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n'
              + frame + b'\r\n'
          )
        elif frame is None:
          no_frame_count += 1
          if no_frame_count >= 25 and last_sent != OFFLINE_FRAME:
            last_sent = OFFLINE_FRAME
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: '
                + str(len(OFFLINE_FRAME)).encode()
                + b'\r\n\r\n'
                + OFFLINE_FRAME
                + b'\r\n'
            )
        time.sleep(0.04)
    finally:
      stream_hub.release(key)

  return StreamingResponse(
      frame_generator(),
      media_type='multipart/x-mixed-replace; boundary=frame',
  )


ui.run_with(
    server_app,
    mount_path='/',
    title='BG System',
    storage_secret=config.STORAGE_SECRET,
)

if __name__ == '__main__':
  uvicorn.run(
      'server:server_app',
      host=config.SERVER_HOST,
      port=config.SERVER_PORT,
      reload=True,
      reload_dirs=[
          'component',
          'config',
          'model',
          'page',
      ],
      # reload_excludes=[
      #     '*.db',
      #     '*.db-wal',
      #     '*.db-shm',
      #     '*.log',
      #     'data/*',
      #     'server_device_logs/*',
      #     'uploads/*',
      # ],
  )