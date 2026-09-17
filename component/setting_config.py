from config import config
from fastapi import HTTPException
from nicegui import ui


class ConfigModal(ui.element):

  def __init__(self, device_id=None, api_key=None, database=None, mq=None):
    super().__init__()
    self.device_id = device_id
    self.database = database
    self.device = self.database.get_device_by_id(self.device_id) or {}
    self.device_name = self.device.get('name')
    self.api_key = api_key
    self.mq = mq

    schema = config.WEB_SCHEMA.get('webserver', {})
    db_schema = schema.get('database', {})
    self.columns_schema = db_schema.get('devices_table', [])
    self.io_schema = [
        col for col in self.columns_schema if col.get('title') == 'IO'
    ]

    self.io_inputs = (
        {}
    ) 

    with ui.dialog().props('persistent') as self.dialog, ui.card().classes(
        'p-6 rounded-2xl w-full max-w-2xl bg-white shadow-2xl'
    ):
      with ui.row().classes(
          'items-center justify-between w-full mb-4 border-b pb-3'
      ):
        with ui.row().classes('items-center gap-2'):
          ui.icon('tune', color='primary').classes('text-2xl')
          ui.label('System Configuration').classes(
              'text-xl font-bold text-slate-800'
          )
        ui.button(icon='close', on_click=self.dialog.close).props(
            'flat round dense text-color=grey'
        )

      # --- Form Fields ---
      with ui.column().classes('w-full gap-4 max-h-[70vh] overflow-y-auto pr-2'):

        # Core Info
        with ui.row().classes('w-full gap-4'):
          self.inp_device_name = ui.input('Device Name').classes('flex-1').props(
              'outlined dense'
          )
          self.inp_mqtt_broker = ui.input('MQTT Broker IP').classes(
              'flex-1'
          ).props('outlined dense')

        # Model Path
        self.inp_model_path = ui.input('Model Path').classes('w-full').props(
            'outlined dense'
        )

        # Dynamic IO Channels Section
        if self.io_schema:
          ui.label('I/O Configuration').classes(
              'text-xs font-bold text-slate-500 uppercase tracking-wider mt-2'
          )
          with ui.row().classes('w-full flex-wrap gap-4'):
            for item in self.io_schema:
              key = item['key']
              col_type = item.get('type', 'TEXT').upper()
              field_label = key.replace('_', ' ').title()

              if col_type == 'INTEGER':
                input_el = ui.number(
                    field_label, min=0, step=1, value=item.get('default', 0)
                ).classes('w-[47%]').props('outlined dense')
              else:
                input_el = ui.input(
                    field_label, value=str(item.get('default', ''))
                ).classes('w-[47%]').props('outlined dense')

              self.io_inputs[key] = (input_el, col_type)

      # --- Action Buttons ---
      with ui.row().classes('w-full justify-end gap-3 mt-6 border-t pt-4'):
        ui.button('Cancel', on_click=self.dialog.close).props(
            'flat text-color=grey'
        )
        ui.button('Save Changes', on_click=self._handle_save).classes(
            'bg-slate-800 text-white font-bold px-4'
        )

  def open(self):
    self.device = self.database.get_device_by_id(self.device_id) or {}
    self.inp_device_name.set_value(self.device.get('name', ''))
    self.inp_mqtt_broker.set_value(self.device.get('mqtt_broker', ''))
    self.inp_model_path.set_value(self.device.get('model_path', ''))

    # กำหนดค่าให้กับ dynamic IO inputs ตามข้อมูลจาก Database
    for key, (input_el, col_type) in self.io_inputs.items():
      val = self.device.get(key)
      if val is not None:
        input_el.set_value(int(val) if col_type == 'INTEGER' else str(val))

    self.dialog.open()

  def _handle_save(self):
    name = str(self.inp_device_name.value or '').strip()
    if not name:
      ui.notify('Device name cannot be empty', color='negative')
      return

    payload = {
        'name': name,
        'mqtt_broker': str(self.inp_mqtt_broker.value or '').strip(),
        'model_path': str(self.inp_model_path.value or '').strip(),
    }


    for key, (input_el, col_type) in self.io_inputs.items():
      if col_type == 'INTEGER':
        payload[key] = int(input_el.value or 0)
      else:
        payload[key] = str(input_el.value or '').strip()

    try:
      self.database.update_device_config(api_key=self.api_key, payload=payload)
      if self.mq:
        self.mq.on_send_config(payload, self.device_name)

      self.device = self.database.get_device_by_id(self.device_id)
      self.device_name = self.device.get('name')
      self.dialog.close()
      ui.notify('Configuration saved successfully', color='positive')

    except HTTPException as e:
      ui.notify(f'Config error: {e.detail}', color='negative')
    except Exception as e:
      ui.notify(f'Config error: {e}', color='negative')