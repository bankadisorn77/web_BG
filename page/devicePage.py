from datetime import datetime
import json
from component.camera_stream import VideoCard
from component.header import AppHeader
from component.result_display import ResultDisplay
from component.result_log import ResultLog
from component.setting_config import ConfigModal
from component.terminal_log import TerminalLog
from config import config
from model.mqtt import get_recent_device_logs
from nicegui import app, ui


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
    # Camera UI is generated from Edge registration data.
    self.camera_config = self._load_json_config(self.device.get('camera_config'))
    if isinstance(self.camera_config, list) and self.camera_config:
      self.camera_indexes = list(range(1, len(self.camera_config) + 1))
      self.camera_labels = [
          str(item.get('id', f'CAM {idx:02d}')).upper()
          if isinstance(item, dict) else f'CAM {idx:02d}'
          for idx, item in enumerate(self.camera_config, start=1)
      ]
    else:
      # Backward-compatible fallback for existing devices.
      self.camera_indexes = [1, 2]
      self.camera_labels = ['CAM 01', 'CAM 02']

    self.camera_count = len(self.camera_indexes)
    self.stream_url = [
        f'/stream/{self.device_id}/{idx}' for idx in self.camera_indexes
    ]
    self.mq = mq

    web_schema = config.WEB_SCHEMA
    self.device_schema = web_schema.get('edge_device', [])
    self.badges = {}

    config_modal = ConfigModal(
        device_id=self.device_id,
        api_key=self.api_key,
        database=database,
        mq=self.mq,
    )
    result_log = ResultLog(database=self.database, device_id=self.device_id)

    # 1. Header
    AppHeader(logout=logout, device_name=self.device_name)

    with ui.row().classes('w-full px-10 py-1 gap-8 items-start no-wrap'):

      with ui.column().classes('w-3/4 gap-6'):
        VideoCard(stream_urls=self.stream_url, camera_labels=self.camera_labels)

      with ui.column().classes('w-1/4 gap-6'):
        with ui.card().classes('w-full p-6 shadow-md bg-white rounded-xl'):
          with ui.row().classes('items-center justify-between w-full mb-3'):
            ui.label('Machine Status').classes(
                'text-l font-bold text-slate-700 mb-2'
            )
            ui.button(icon='settings', on_click=config_modal.open).props(
                'flat round text-color=slate-700'
            ).bind_visibility_from(
                app.storage.user, 'role', backward=lambda r: r == 'admin'
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

          # Dynamic Badges Generation
          with ui.row().classes(
              'w-full flex-wrap gap-2 pt-2 border-t border-slate-100'
          ):
            for section in self.device_schema:
              for item in section.get('items', []):
                if item['key'] == 'program_status':
                  continue

                key = item['key']
                label = item['label']
                default_val = item['default']
                color_map = item.get('color_map', {})

                init_color = color_map.get(default_val, 'grey')
                badge_el = ui.badge(
                    f'{label}: {default_val}', color=init_color
                ).classes('text-[10px] font-bold px-2')

                self.badges[key] = {
                    'element': badge_el,
                    'label': label,
                    'color_map': color_map,
                    'default': default_val,
                }

        self.terminal = TerminalLog(
            title=f'Logs: {self.device_name}', max_lines=150
        )

        self.result_display = ResultDisplay(
            database=self.database, device_id=self.device_id
        )
        if self.device_name:
          history_logs = get_recent_device_logs(self.device_id, lines=60)
          for log_line in history_logs:
            self.terminal.write(log_line)

        if on_terminal_log_register:
          on_terminal_log_register(self.handle_incoming_realtime_log)

    self.sync_dashboard()
    if self.on_log_update:
      self.on_log_update(self.log_update)
    if self.on_device_update:
      self.on_device_update(self.sync_dashboard)

  @staticmethod
  def _load_json_config(value):
    if not value:
      return None
    if isinstance(value, (dict, list)):
      return value
    try:
      return json.loads(value)
    except (TypeError, ValueError):
      return None

  def handle_incoming_realtime_log(self, message: str):
    self.terminal.write(f'{message}')

  def reset_badges(self):
    for key, item in self.badges.items():
      item['element'].set_text(f"{item['label']}: OFF").props('color=grey')

  def sync_dashboard(self):
    self.device = self.database.get_device_by_id(self.device_id) or {}
    device_status = self.device.get('device_status', 'INACTIVE')
    program_status = self.device.get('program_status', self.device.get('program', 'OFF'))

    if device_status == 'ACTIVE':
      self.btn_service.enable()

      if program_status == 'RUNNING':
        self.status_icon.props('name=check_circle color=green')
        self.status_label.set_text('RUNNING')
        self.status_label.classes(replace='text-green-600 font-bold text-lg')

        self.btn_service.set_text('STOP')
        self.btn_service.classes(replace='bg-red-600 text-white font-bold px-3')
        for key, item in self.badges.items():
          val = self.device.get(key, item['default'])
          color = item['color_map'].get(val, 'grey')
          item['element'].set_text(f"{item['label']}: {val}").props(
              f'color={color}'
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
        if 'device_status' in self.badges:
          color = self.badges['device_status']['color_map'].get(
              device_status, 'green'
          )
          self.badges['device_status']['element'].set_text(
              f"{self.badges['device_status']['label']}: {device_status}"
          ).props(f'color={color}')

    else:
      self.status_icon.props('name=cancel color=grey')
      self.status_label.set_text(device_status)
      self.status_label.classes(
          replace='text-slate-400 font-bold text-lg text-red-100'
      )
      self.btn_service.set_text('START')
      self.btn_service.classes(replace='bg-slate-400 text-white font-bold px-3')
      self.btn_service.disable()

      self.reset_badges()
      if 'device_status' in self.badges:
        color = self.badges['device_status']['color_map'].get(
            device_status, 'grey'
        )
        self.badges['device_status']['element'].set_text(
            f"{self.badges['device_status']['label']}: {device_status}"
        ).props(f'color={color}')

  def switch_service(self):
    self.device = self.database.get_device_by_id(self.device_id)
    if not self.device or self.device.get('device_status') != 'ACTIVE':
      ui.notify('Device is INACTIVE. Cannot switch service.', color='warning')
      return

    if self.device.get('program_status', self.device.get('program')) == 'RUNNING':
      self.device['program_status'] = 'OFF'
      ui.notify('Service stopped', color='red')
    else:
      self.device['program_status'] = 'RUNNING'
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