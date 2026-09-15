from datetime import datetime
import os
import re

from nicegui import ui


class ResultDisplay(ui.card):

  def __init__(self, database=None, device_id=None):
    super().__init__()
    self.database = database
    self.device_id = device_id
    self.classes('w-full p-4 shadow-md bg-white rounded-xl')

    with self:
      with ui.row().classes('items-center justify-between w-full mb-3'):
        ui.label('Inspection Result').classes('text-l font-bold text-slate-800')

        with ui.row().classes('items-center gap-1'):
          ui.icon('photo_camera', color='slate').classes('text-xs')
          self.lbl_timestamp = ui.label('--:--:--').classes(
              'text-xs font-bold text-slate-600 font-mono'
          )

      with ui.element('div').classes(
          'w-full aspect-video bg-black rounded-lg overflow-hidden flex'
          ' items-center justify-center relative'
      ):
        self.img_display = ui.image().classes(
            'w-full h-full object-contain block'
        )

    self.load_img()

  def _extract_timestamp(self, filename: str) -> str:
    basename = os.path.basename(filename)
    match = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', basename)
    if match:
      year, month, day, hour, minute, second = match.groups()
      return f'{year}-{month}-{day} {hour}:{minute}:{second}'
    try:
      mtime = os.path.getmtime(filename)
      return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
      return '--:--:--'

  def load_img(self):
    if not self.database:
      return
    log = self.database.get_latest_log(self.device_id)
    if not log:
      return
    image_path = log.get('image_path')
    if not image_path:
      return

    timestamp_str = self._extract_timestamp(image_path)
    self.lbl_timestamp.set_text(timestamp_str)

    self.img_display.set_source(f'/media/{image_path}')
    self.img_display.update()
