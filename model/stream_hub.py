import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

JPEG_SOI = b'\xff\xd8'  # Start Of Image
JPEG_EOI = b'\xff\xd9'  # End Of Image
MAX_BUFFER_BYTES = 2_000_000  # กัน buffer บวมถ้าหา marker ไม่เจอผิดปกติ
RETRY_BACKOFF_SECONDS = 2
PULL_TIMEOUT_SECONDS = 5
IDLE_GRACE_SECONDS = 3  # หน่วงก่อนหยุดดึงจริง กัน reload หน้าแล้วต้องต่อใหม่ทันที


class _CameraStream:

  def __init__(self, source_url: str):
    self.source_url = source_url
    self.frame = None
    self.frame_lock = threading.Lock()
    self.viewers = 0
    self.thread = None
    self.stop_event = threading.Event()
    self.fail_count = 0  # นับความล้มเหลวติดต่อกัน ใช้ลด log spam ตอน device ปิดอยู่


class StreamHub:

  def __init__(self):
    self._lock = threading.Lock()
    self._streams = {}  # key: (device_id, cam_index) -> _CameraStream

  def acquire(self, key, source_url: str):
    with self._lock:
      entry = self._streams.get(key)
      if entry is None:
        entry = _CameraStream(source_url)
        self._streams[key] = entry
      entry.source_url = source_url  # เผื่อ ip เปลี่ยนหลังแก้ config
      entry.viewers += 1
      if entry.thread is None or not entry.thread.is_alive():
        entry.stop_event.clear()
        entry.thread = threading.Thread(
            target=self._pull_loop, args=(key, entry), daemon=True
        )
        entry.thread.start()
        logger.info('[StreamHub] start pulling %s', (key,))
      else:
        entry.stop_event.clear()
    return entry

  def release(self, key):
    with self._lock:
      entry = self._streams.get(key)
      if not entry:
        return
      entry.viewers = max(0, entry.viewers - 1)
      if entry.viewers == 0:
        entry.stop_event.set()
        logger.info('[StreamHub] no viewers left for %s', (key,))

  def get_frame(self, key):
    entry = self._streams.get(key)
    if not entry:
      return None
    with entry.frame_lock:
      return entry.frame

  def shutdown(self):
    with self._lock:
      for entry in self._streams.values():
        entry.stop_event.set()

  def _pull_loop(self, key, entry):
    """ดึง MJPEG จาก edge แล้วตัดเป็นเฟรม JPEG ทีละภาพด้วยการหา SOI/EOI marker
    (ทนกว่าการ parse multipart header เพราะไม่ต้องพึ่ง Content-Length ที่ edge
    ส่งมาให้ถูกเป๊ะ)
    """
    while not entry.stop_event.is_set():
      try:
        with requests.get(
            entry.source_url, stream=True, timeout=PULL_TIMEOUT_SECONDS
        ) as resp:
          if entry.fail_count > 0:
            logger.info('[StreamHub] recovered %s after %d failed attempt(s)',
                        (key,), entry.fail_count)
          entry.fail_count = 0
          buf = b''
          for chunk in resp.iter_content(chunk_size=4096):
            if entry.stop_event.is_set():
              break
            if not chunk:
              continue
            buf += chunk
            start = buf.find(JPEG_SOI)
            end = buf.find(JPEG_EOI, start + 2) if start != -1 else -1
            if start != -1 and end != -1:
              with entry.frame_lock:
                entry.frame = buf[start:end + 2]
              buf = buf[end + 2:]
            elif len(buf) > MAX_BUFFER_BYTES:
              buf = b''
      except Exception as e:
        entry.fail_count += 1
        # log ทุกครั้งตอนเพิ่งเริ่มพัง (fail_count==1) แล้วหลังจากนั้น log ห่างๆ
        # ทุก ๆ 10 ครั้ง (~70 วิ) กันกรณี device ปิดอยู่นาน ๆ แล้ว log ถูกถล่ม
        # ด้วยข้อความเดิมซ้ำทุก ~7 วิ ไม่มีที่สิ้นสุด
        if entry.fail_count == 1 or entry.fail_count % 10 == 0:
          logger.warning(
              '[StreamHub] pull error %s (attempt #%d): %s',
              (key,), entry.fail_count, e,
          )

      if entry.stop_event.is_set():
        break
      time.sleep(RETRY_BACKOFF_SECONDS)

    with entry.frame_lock:
      entry.frame = None
    logger.info('[StreamHub] stopped pulling %s', (key,))