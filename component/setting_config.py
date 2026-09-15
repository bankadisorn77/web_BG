from fastapi import HTTPException
from nicegui import ui


class ConfigModal(ui.element):

  def __init__(self, device_id=None, api_key=None, database=None, mq=None):
    super().__init__()
    self.device_id = device_id
    self.database = database
    self.device = self.database.get_device_by_id(self.device_id)
    self.device_name = self.device.get('name')
    self.api_key = api_key
    self.mq = mq

    with ui.dialog().props('persistent') as self.dialog, ui.card().classes(
        'p-6 rounded-2xl w-full max-w-2xl bg-white shadow-2xl'
    ):
      with ui.row().classes('items-center justify-between w-full mb-4 border-b pb-3'):
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

        # Device & General
        with ui.row().classes('w-full gap-4'):
          self.inp_device_name = ui.input('Device ID').classes('flex-1').props(
              'outlined dense'
          )
          self.inp_mqtt_broker = ui.input('MQTT Server IP').classes(
              'flex-1'
          ).props('outlined dense')

        # GPIO Channels & Timing
        ui.label('GPIO Channels').classes(
            'text-xs font-bold text-slate-500 uppercase tracking-wider mt-2'
        )
        with ui.row().classes('w-full gap-4'):
          self.inp_input_channel = ui.number(
              'Input Channel', min=0, step=1
          ).classes('w-1/4').props('outlined dense')
          self.inp_output_alarm_channel = ui.number(
              'Output Alarm', min=0, step=1
          ).classes('w-1/4').props('outlined dense')
          self.inp_output_relay_channel = ui.number(
              'Output Contor', min=0, step=1
          ).classes('w-1/4').props('outlined dense')
          self.inp_output_light_channel = ui.number(
              'Output StateMachine', min=0, step=1
          ).classes('w-1/4').props('outlined dense')

        # Paths
        ui.label('Model').classes(
            'text-xs font-bold text-slate-500 uppercase tracking-wider mt-2'
        )
        self.inp_model_path = ui.input('Model Path').classes('w-full').props(
            'outlined dense'
        )

      # --- Action Buttons ---
      with ui.row().classes('w-full justify-end gap-3 mt-6 border-t pt-4'):
        ui.button('Cancel', on_click=self.dialog.close).props(
            'flat text-color=grey'
        )
        ui.button('Save Changes', on_click=self._handle_save).classes(
            'bg-slate-800 text-white font-bold px-4'
        )

  def open(self):
    self.device = self.database.get_device_by_id(self.device_id)
    self.inp_device_name.set_value(self.device.get('name', ''))
    self.inp_mqtt_broker.set_value(self.device.get('mqtt_broker', ''))
    self.inp_input_channel.set_value(self.device.get('input_channel', 0))
    self.inp_output_alarm_channel.set_value(
        self.device.get('output_alarm_channel', 0)
    )
    self.inp_output_relay_channel.set_value(
        self.device.get('output_relay_channel', 1)
    )
    self.inp_output_light_channel.set_value(
        self.device.get('output_light_channel', 2)
    )
    self.inp_model_path.set_value(self.device.get('model_path', ''))
    self.dialog.open()

  def _handle_save(self):
    name = str(self.inp_device_name.value or '').strip()
    input_channel = int(self.inp_input_channel.value or 0)
    output_alarm_channel = int(self.inp_output_alarm_channel.value or 0)
    output_relay_channel = int(self.inp_output_relay_channel.value or 1)
    output_light_channel = int(self.inp_output_light_channel.value or 2)
    mqtt_broker = str(self.inp_mqtt_broker.value or '').strip()
    model_path = str(self.inp_model_path.value or '').strip()

    if not name:
      ui.notify('Device name cannot be empty', color='negative')
      return

    try:
      self.database.update_device_config(
          api_key=self.api_key,
          name=name,
          input_channel=input_channel,
          output_alarm_channel=output_alarm_channel,
          output_relay_channel=output_relay_channel,
          output_light_channel=output_light_channel,
          model_path=model_path,
          mqtt_broker=mqtt_broker,
      )

      # ส่ง config ใหม่ไปหาอุปกรณ์ผ่าน MQTT (คีย์เหล่านี้เป็นสัญญากับ firmware
      # ห้ามเปลี่ยนชื่อ)
      msg = {
          'name': name,
          'input_channel': input_channel,
          'output_alarm_channel': output_alarm_channel,
          'output_relay_channel': output_relay_channel,
          'output_light_channel': output_light_channel,
          'model_path': model_path,
          'mqtt_broker': mqtt_broker,
      }
      if self.mq:
        self.mq.on_send_config(msg, self.device_name)

      self.device = self.database.get_device_by_id(self.device_id)
      self.device_name = self.device.get('name')
      self.dialog.close()
      ui.notify('Configuration saved', color='positive')

    except HTTPException as e:
      ui.notify(f'Config error: {e.detail}', color='negative')
    except Exception as e:
      ui.notify(f'Config error: {e}', color='negative')
