from datetime import datetime

from nicegui import ui

from component.camera_stream import VideoCard
from component.result_display import ResultDisplay
from component.result_log import ResultLog
from component.setting_config import ConfigModal
from component.terminal_log import TerminalLog
from model.mqtt import get_recent_device_logs


class devicePage:

  def __init__(
      self,
      device_id,
      logout,
      database,
      keep_alive_func=None,
      mq=None,
      on_log_update=None,
      on_device_status_update=None,
      on_terminal_log_register=None,
  ):
    self.on_log_update = on_log_update
    self.on_device_update = on_device_status_update
    if keep_alive_func:
      ui.on('mousemove', keep_alive_func)
      ui.on('click', keep_alive_func)
      ui.on('keydown', keep_alive_func)
    self.database = database
    self.device = self.database.get_device_by_id(device_id)
    self.logout = logout
    self.device_id = device_id
    self.api_key = self.device.get('api_key', None) if self.device else None
    self.device_name = self.device.get('name', '') if self.device else ''
    self.ip_address = (
        self.device.get('ip_address') if self.device else 'localhost'
    )
    self.stream_url = (
        f'http://{self.ip_address}:8095/video_feed'
        if self.device
        else 'http://localhost:8095/stream'
    )
    self.mq = mq

    config_modal = ConfigModal(
        device_id=self.device_id,
        api_key=self.api_key,
        database=database,
        mq=self.mq,
    )
    result_log = ResultLog(database=self.database, device_id=self.device_id)

    # 1. Header
    with ui.header().classes(
        'bg-white text-slate-800 shadow-sm justify-between items-center px-10'
        ' py-4'
    ):
      with ui.row().classes('items-center gap-3'):
        ui.icon('precision_manufacturing', color='primary').classes('text-3xl')
        ui.label('BG System').classes('text-2xl font-bold tracking-wide')
      with ui.row().classes('items-center gap-4'):
        ui.button(
            'HOME', on_click=lambda: ui.navigate.to('/'), color='blue'
        ).props('unelevated text-color=white')
        ui.button('LOGOUT', on_click=self.logout, color='red').props(
            'unelevated text-color=white'
        )

    # 2. Main Dashboard Layout
    with ui.row().classes('w-full px-10 py-1 gap-8 items-start no-wrap'):
      # คอลัมน์ซ้าย: Video Stream และ Result Display
      with ui.column().classes('w-3/4 gap-6'):
        VideoCard(stream_url=self.stream_url)

      # คอลัมน์ขวา: Status Card และ Terminal Logs
      with ui.column().classes('w-1/4 gap-6'):
        with ui.card().classes('w-full p-6 shadow-md bg-white rounded-xl'):
          with ui.row().classes('items-center justify-between w-full mb-3'):
            ui.label('Machine Status').classes(
                'text-l font-bold text-slate-700 mb-2'
            )
            ui.button(icon='settings', on_click=config_modal.open).props(
                'flat round text-color=slate-700'
            )
          with ui.row().classes('items-center justify-between w-full mb-3'):
            with ui.row().classes('items-center gap-2'):
              self.status_icon = ui.icon('cancel', color='grey').classes(
                  'text-2xl'
              )
              self.status_label = ui.label('STOPPED').classes(
                  'text-slate-500 font-bold text-lg'
              )
            with ui.row().classes('items-center justify-end'):
              ui.button('IMAGE LOGS', on_click=result_log.open).props(
                  'dense unelevated'
              ).classes('bg-green-600 text-white font-bold px-3')
              self.btn_service = (
                  ui.button('START', on_click=lambda: self.switch_service())
                  .props('dense unelevated')
                  .classes('bg-green-600 text-white font-bold px-3')
              )

          with ui.row().classes('w-full gap-2 pt-2 border-t border-slate-100'):
            self.badge_cam = ui.badge('CAM: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_gpio = ui.badge('GPIO: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_device = ui.badge('DEVICE: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_door = ui.badge('Door: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_alarm = ui.badge('Alarm: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_relay = ui.badge('Relay: OFF', color='grey').classes(
                'text-[10px] font-bold px-2'
            )
            self.badge_light = ui.badge(
                'Tower Light: OFF', color='grey'
            ).classes('text-[10px] font-bold px-2')

        self.terminal = TerminalLog(
            title=f'Logs: {self.device_name}', max_lines=150
        )

        self.result_display = ResultDisplay(
            database=self.database, device_id=self.device_id
        )
        if self.device_name:
          history_logs = get_recent_device_logs(self.device_name, lines=60)
          for log_line in history_logs:
            self.terminal.write(log_line)

        if on_terminal_log_register:
          on_terminal_log_register(self.handle_incoming_realtime_log)

    self.sync_dashboard()
    if self.on_log_update:
      self.on_log_update(self.log_update)
    if self.on_device_update:
      self.on_device_update(self.sync_dashboard)

  def handle_incoming_realtime_log(self, message: str):
    self.terminal.write(f'{message}')

  def sync_dashboard(self):
    self.device = self.database.get_device_by_id(self.device_id)
    if self.device and self.device.get('device_status') == 'ACTIVE':
      self.btn_service.enable()

      if self.device.get('program') == 'RUNNING':
        hw = self.device
        self.status_icon.props('name=check_circle color=green')
        self.status_label.set_text('RUNNING')
        self.status_label.classes(replace='text-green-600 font-bold text-lg')

        self.btn_service.set_text('STOP')
        self.btn_service.classes(replace='bg-red-600 text-white font-bold px-3')

        self.badge_cam.set_text(
            'CAM: ONLINE' if hw.get('camera') == 'ONLINE' else 'CAM: ERROR'
        )
        self.badge_cam.props(
            f"color={'green' if hw.get('camera') == 'ONLINE' else 'red'}"
        )
        self.badge_gpio.set_text(
            'GPIO: ONLINE' if hw.get('gpio') == 'ONLINE' else 'GPIO: ERROR'
        )
        self.badge_gpio.props(
            f"color={'green' if hw.get('gpio') == 'ONLINE' else 'red'}"
        )

        self.badge_device.set_text(f"DEVICE: {hw.get('device_status')}")
        self.badge_device.props('color=green')
        self.badge_door.set_text(f"Door Sensor: {hw.get('door_status')}")
        self.badge_door.props(
            f"color={'orange' if hw.get('door_status') == 'OPEN' else ('green' if hw.get('door_status') == 'CLOSE' else 'grey')}"
        )
        self.badge_alarm.set_text(f"Alarm Siren: {hw.get('alarm_status')}")
        self.badge_alarm.props(
            f"color={'red' if hw.get('alarm_status') == 'ON' else 'grey'}"
        )
        self.badge_relay.set_text(f"Main Relay: {hw.get('relay_status')}")
        self.badge_relay.props(
            f"color={'green' if hw.get('relay_status') == 'ON' else 'grey'}"
        )
        self.badge_light.set_text(f"Tower Light: {hw.get('light_status')}")
        self.badge_light.props(
            f"color={'green' if hw.get('light_status') == 'ON' else 'grey'}"
        )

      else:
        self.status_icon.props('name=check color=green')
        self.status_label.set_text('STOPPED')
        self.status_label.classes(replace='text-slate-500 font-bold text-lg')

        self.btn_service.set_text('START')
        self.btn_service.classes(
            replace='bg-green-600 text-white font-bold px-3'
        )

        self.reset_badges()

    else:
      self.status_icon.props('name=cancel color=grey')
      self.status_label.set_text(
          self.device.get('device_status') if self.device else 'INACTIVE'
      )
      self.status_label.classes(
          replace='text-slate-400 font-bold text-lg text-red-100'
      )
      self.btn_service.set_text('START')
      self.btn_service.classes(replace='bg-slate-400 text-white font-bold px-3')
      self.btn_service.disable()
      self.reset_badges()
      self.badge_device.set_text('DEVICE: INACTIVE')
      self.badge_device.props('color=grey')

  def reset_badges(self):
    self.badge_cam.set_text('CAM: OFF').props('color=grey')
    self.badge_gpio.set_text('GPIO: OFF').props('color=grey')
    self.badge_door.set_text('Door: OFF').props('color=grey')
    self.badge_alarm.set_text('Alarm: OFF').props('color=grey')
    self.badge_relay.set_text('Relay: OFF').props('color=grey')
    self.badge_light.set_text('Tower Light: OFF').props('color=grey')

  def switch_service(self):
    self.device = self.database.get_device_by_id(self.device_id)
    if not self.device or self.device.get('device_status') != 'ACTIVE':
      ui.notify(
          'Device is INACTIVE. Cannot switch service.', color='warning'
      )
      return

    if self.device.get('program') == 'RUNNING':
      self.device['program'] = 'OFF'
      ui.notify('Service stopped', color='red')
    else:
      self.device['program'] = 'RUNNING'
      ui.notify('Service started', color='green')
    self.mq.on_program_control(
        msg=self.device['program'], device_name=self.device['name']
    )
    self.database.update_device_all_status(
        program_status=self.device['program'], api_key=self.device['api_key']
    )
    self.sync_dashboard()

  def log_update(self):
    self.result_display.load_img()
