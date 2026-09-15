from nicegui import ui


class DeviceCard(ui.card):

  def __init__(self, device: dict = None, on_delete=None):
    super().__init__()
    self.device = device or {}
    self.on_delete = on_delete
    self.classes('w-80 p-6 shadow-lg bg-white rounded-2xl')

    device_name = self.device.get('name', 'None')
    device_id = self.device.get('id', 'None')

    with self:
      with ui.row().classes('w-full items-center justify-between mb-0 px-2'):
        ui.label(device_name).classes(
            'text-xl font-bold text-slate-800 text-center'
        )
        # เรียก request_delete แทน เพื่อไม่ให้ชน internal method ของ NiceGUI
        ui.button(icon='delete', on_click=self.request_delete).props(
            'flat round dense text-color=red'
        )

      ui.separator().classes('mb-4')

      with ui.row().classes('w-full justify-between items-start mb-6 gap-4'):
        # Hardware Status
        with ui.column().classes('flex-1 gap-2'):
          ui.label('Hardware status').classes(
              'text-xs text-slate-400 font-semibold w-full text-center'
          )
          self.cam_status = ui.badge('CAMERA: OFF', color='grey').classes(
              'w-full text-center text-[10px] py-1'
          )
          self.gpio_status = ui.badge('GPIO: OFF', color='grey').classes(
              'w-full text-center text-[10px] py-1'
          )
          self.program_status = ui.badge('AI: OFF', color='grey').classes(
              'w-full text-center text-[10px] py-1'
          )
          self.device_status = ui.badge(
              'DEVICE: INACTIVE', color='grey'
          ).classes('w-full text-center text-[10px] py-1')

        ui.separator().props('vertical').classes('self-stretch')

        # Output Channel
        with ui.column().classes('flex-1 gap-2'):
          ui.label('Output channel').classes(
              'text-xs text-slate-400 font-semibold w-full text-center'
          )
          self.door_input = ui.badge(
              'Door Sensor: CLOSED', color='grey'
          ).classes('w-full text-center text-[10px] py-1')
          self.alarm_output = ui.badge('Alarm Siren: OFF', color='grey').classes(
              'w-full text-center text-[10px] py-1'
          )
          self.relay_output = ui.badge('Main Relay: OFF', color='grey').classes(
              'w-full text-center text-[10px] py-1'
          )
          self.status_output = ui.badge(
              'Tower Light: OFF', color='grey'
          ).classes('w-full text-center text-[10px] py-1')

      ui.button(
          'VIEW', on_click=lambda: ui.navigate.to(f'/device/{device_id}')
      ).classes('w-full bg-blue-600 text-white font-bold rounded-lg py-2')

    self.update_status(self.device)

  def request_delete(self):
    """เรียกเมื่อผู้ใช้คลิกปุ่มถังขยะจริงๆ (ไม่ใช้ชื่อ _handle_delete)"""
    if callable(self.on_delete):
      self.on_delete()

  def _get_status_color(self, val: str) -> str:
    """แยกฟังก์ชันสีออกมา เพื่อป้องกัน f-string เครื่องหมายคำพูดซ้อน"""
    if val in ('ONLINE', 'ACTIVE', 'ON', 'RUNNING'):
      return 'green'
    if val == 'ERROR':
      return 'red'
    return 'grey'

  def update_status(self, new_data: dict = None):
    if not self.device:
      return

    if new_data:
      self.device.update(new_data)

    program_status = self.device.get('program', 'OFF')
    device_status = self.device.get('device_status', 'INACTIVE')

    if program_status == 'RUNNING' and device_status == 'ACTIVE':
      cam = self.device.get('camera', 'OFF')
      gpio = self.device.get('gpio', 'OFF')
      door = self.device.get('door_status', 'CLOSED')
      alarm = self.device.get('alarm_status', 'OFF')
      relay = self.device.get('relay_status', 'OFF')
      light = self.device.get('light_status', 'OFF')

      self.cam_status.set_text(f'CAMERA: {cam}')
      self.cam_status.props(f'color={self._get_status_color(cam)}')

      self.gpio_status.set_text(f'GPIO: {gpio}')
      self.gpio_status.props(f'color={self._get_status_color(gpio)}')

      self.program_status.set_text('AI: RUNNING')
      self.program_status.props('color=green')

      self.device_status.set_text(f'DEVICE: {device_status}')
      self.device_status.props('color=green')

      # Door sensor logic
      door_color = (
          'orange'
          if door == 'OPEN'
          else ('green' if door in ('CLOSED', 'CLOSE') else 'grey')
      )
      self.door_input.set_text(f'Door Sensor: {door}')
      self.door_input.props(f'color={door_color}')

      self.alarm_output.set_text(f'Alarm Siren: {alarm}')
      self.alarm_output.props(f'color={self._get_status_color(alarm)}')

      self.relay_output.set_text(f'Main Relay: {relay}')
      self.relay_output.props(f'color={self._get_status_color(relay)}')

      self.status_output.set_text(f'Tower Light: {light}')
      self.status_output.props(f'color={self._get_status_color(light)}')

    else:
      dev_color = (
          'green'
          if device_status == 'ACTIVE'
          else ('red' if device_status == 'ERROR' else 'grey')
      )

      self.cam_status.set_text('CAMERA: OFF')
      self.cam_status.props('color=grey')

      self.gpio_status.set_text('GPIO: OFF')
      self.gpio_status.props('color=grey')

      self.program_status.set_text('AI: OFF')
      self.program_status.props('color=grey')

      self.device_status.set_text(f'DEVICE: {device_status}')
      self.device_status.props(f'color={dev_color}')

      self.door_input.set_text('Door Sensor: OFF')
      self.door_input.props('color=grey')

      self.alarm_output.set_text('Alarm Siren: OFF')
      self.alarm_output.props('color=grey')

      self.relay_output.set_text('Main Relay: OFF')
      self.relay_output.props('color=grey')

      self.status_output.set_text('Tower Light: OFF')
      self.status_output.props('color=grey')