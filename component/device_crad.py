from nicegui import ui

from config import config


class DeviceCard(ui.card):

  def __init__(self, device: dict = None, on_delete=None):
    super().__init__()
    self.device = device or {}
    self.on_delete = on_delete
    self.classes('w-80 p-6 shadow-lg bg-white rounded-2xl')
    web_schema = config.WEB_SCHEMA
    device_schema = web_schema.get('edge_device',[])
    hw_status = device_schema[0]
    io_status = device_schema[1]
    self.badges = {}
    device_name = self.device.get('name', 'None')
    device_id = self.device.get('id', 'None')

    with self:
      with ui.row().classes('w-full items-center justify-between mb-0 px-2'):
        ui.label(device_name).classes(
            'text-xl font-bold text-slate-800 text-center'
        )
        ui.button(icon='delete', on_click=self.request_delete).props(
            'flat round dense text-color=red'
        )

      ui.separator().classes('mb-4')

      with ui.row().classes('w-full justify-between items-start mb-6 gap-4'):
        # Hardware Status
        with ui.column().classes('flex-1 gap-2'):
          ui.label(hw_status.get('title','status')).classes(
              'text-xs text-slate-400 font-semibold w-full text-center'
          )
          for indix,item in enumerate(hw_status.get('items',[])):
            key = item['key']
            label = item['label']
            default_val = item["default"]
            color_map = item.get("color_map", {})

            init_color = color_map.get(default_val, "grey")

            badge_el = ui.badge(
                f"{label}: {default_val}", color=init_color
            ).classes("w-full text-center text-[10px] py-1")

            self.badges[key] = {
                  'element': badge_el,
                  'label': label,
                  'color_map': color_map,
                  'default': default_val,
              }

        ui.separator().props('vertical').classes('self-stretch')

        # Output Channel
        with ui.column().classes('flex-1 gap-2'):
          ui.label(io_status.get('title','status')).classes(
              'text-xs text-slate-400 font-semibold w-full text-center'
          )
          for indix,item in enumerate(io_status.get('items',[])):
            key = item['key']
            label = item['label']
            default_val = item["default"]
            color_map = item.get("color_map", {})
          
            init_color = color_map.get(default_val, "grey")
          
            badge_el = ui.badge(
              f"{label}: {default_val}", color=init_color
            ).classes("w-full text-center text-[10px] py-1")
          
            self.badges[key] = {
                  'element': badge_el,
                  'label': label,
                  'color_map': color_map,
                  'default': default_val,
              }

      ui.button(
          'VIEW', on_click=lambda: ui.navigate.to(f'/device/{device_id}')
      ).classes('w-full bg-blue-600 text-white font-bold rounded-lg py-2')

    self.update_status(self.device)

  def request_delete(self):
    if callable(self.on_delete):
      self.on_delete()

  def update_status(self, new_data: dict = None):
    if not self.device:
      return

    if new_data:
      self.device.update(new_data)

    program_status = self.device.get('program_status', self.device.get('program', 'OFF'))
    device_status = self.device.get('device_status', 'INACTIVE')
    is_operational = program_status == 'RUNNING' and device_status == 'ACTIVE'
    for key, item in self.badges.items():
      badge = item['element']
      label = item['label']
      color_map = item['color_map']

      if is_operational:
        val = self.device.get(key,item['default'])
        color = color_map.get(val, 'grey')
        badge.set_text(f'{label}: {val}')
        badge.props(f'color={color}')
      else:
        if key == 'device_status':
          dev_color = (
              'green'
              if device_status == 'ACTIVE'
              else ('red' if device_status == 'ERROR' else 'grey')
          )
          badge.set_text(f'{label}: {device_status}')
          badge.props(f'color={dev_color}')
        else:
          badge.set_text(f'{label}: OFF')
          badge.props('color=grey')

  