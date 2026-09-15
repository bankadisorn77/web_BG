from nicegui import ui

VALID_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')


class ResultLog(ui.element):

  def __init__(self, database=None, device_id=None):
    super().__init__()
    self.database = database
    self.device_id = device_id
    self.logs = self.database.get_logs(device_id) if self.database else []

    with ui.dialog() as self.preview_dialog:
      with ui.card().classes(
          'p-4 rounded-2xl bg-slate-900 shadow-2xl w-[80vw] max-w-5xl flex'
          ' flex-col items-center gap-3'
      ):
        with ui.row().classes('w-full justify-between items-center px-2'):
          self.lbl_preview_title = ui.label('Preview').classes(
              'text-white font-mono text-sm font-semibold truncate'
              ' max-w-[70vw]'
          )
          ui.button(
              icon='close', on_click=self.preview_dialog.close
          ).props('flat round dense text-color=white')

        self.preview_image = ui.image().classes(
            'w-full max-h-[75vh] object-contain rounded-lg bg-black/40'
        )

    with ui.dialog() as self.dialog:
      with ui.card().classes(
          'p-6 rounded-2xl w-[85vw] max-w-6xl bg-white shadow-2xl flex'
          ' flex-col'
      ):
        with ui.row().classes(
            'items-center justify-between w-full mb-4 border-b pb-3'
        ):
          with ui.row().classes('items-center gap-2'):
            ui.label('Image Log Gallery').classes(
                'text-xl font-bold text-slate-800'
            )

          with ui.row().classes('items-center gap-2'):
            ui.button(icon='refresh', on_click=self.load_images).props(
                'flat round dense text-color=slate-700'
            )
            ui.button(icon='close', on_click=self.dialog.close).props(
                'flat round dense text-color=grey'
            )

        self.gallery_container = ui.row().classes(
            'w-full max-h-[70vh] overflow-y-auto gap-4 p-2 justify-start'
            ' items-start'
        )

  def load_images(self):
    self.logs = self.database.get_logs(self.device_id) if self.database else []
    self.gallery_container.clear()

    filenames = [
        item['image_path']
        for item in self.logs
        if item.get('image_path')
        and item['image_path'].lower().endswith(VALID_IMAGE_EXTENSIONS)
    ]

    if not filenames:
      with self.gallery_container:
        ui.label('No image logs found for this device yet.').classes(
            'text-slate-400 italic'
        )
      return

    with self.gallery_container:
      for filename in filenames:
        with ui.card().classes(
            'p-2 w-48 bg-slate-50 hover:bg-slate-100 hover:shadow-md'
            ' transition-all rounded-xl border border-slate-200 cursor-pointer'
        ):
          ui_img = ui.image(f'/media/{filename}').classes(
              'w-full h-32 object-cover rounded-lg'
          )
          ui_img.on('click', lambda _, name=filename: self._open_full_image(name))

          ui.label(filename).classes(
              'text-[11px] font-mono text-slate-600 truncate w-full text-center'
              ' mt-1'
          )

  def _open_full_image(self, filename: str):
    self.lbl_preview_title.set_text(filename)
    self.preview_image.set_source(f'/media/{filename}')
    self.preview_dialog.open()

  def open(self):
    self.load_images()
    self.dialog.open()

  def close(self):
    self.dialog.close()
