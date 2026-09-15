from nicegui import ui


class DashboardCard(ui.card):

  def __init__(
      self,
      total_devices=0,
      active_devices=0,
      inactive_devices=0,
      error_devices=0,
      align_items=None,
  ):
    self.total_devices = total_devices
    self.active_devices = active_devices
    self.inactive_devices = inactive_devices
    self.error_devices = error_devices
    super().__init__(align_items=align_items)
    self.classes('w-full p-6 shadow-md bg-white rounded-2xl')

    with self:
      with ui.row().classes('w-full gap-4 items-center justify-between no-wrap'):

        # 1. Total Device
        with ui.card().classes(
            'flex-1 items-center p-4 bg-slate-50 border border-slate-100'
            ' shadow-none rounded-xl'
        ):
          ui.label('Total Devices').classes(
              'text-xs font-semibold text-slate-500 uppercase tracking-wider'
          )
          self.t_count = ui.label(str(self.total_devices)).classes(
              'text-3xl font-bold text-slate-800 mt-1'
          )

        # 2. Active Device
        with ui.card().classes(
            'flex-1 items-center p-4 bg-emerald-50 border border-emerald-100'
            ' shadow-none rounded-xl'
        ):
          ui.label('Active Devices').classes(
              'text-xs font-semibold text-emerald-600 uppercase tracking-wider'
          )
          self.a_count = ui.label(str(self.active_devices)).classes(
              'text-3xl font-bold text-emerald-600 mt-1'
          )

        # 3. Inactive Device
        with ui.card().classes(
            'flex-1 items-center p-4 bg-slate-100 border border-slate-200'
            ' shadow-none rounded-xl'
        ):
          ui.label('Inactive Devices').classes(
              'text-xs font-semibold text-slate-600 uppercase tracking-wider'
          )
          self.i_count = ui.label(str(self.inactive_devices)).classes(
              'text-3xl font-bold text-slate-600 mt-1'
          )

        # 4. Error Device
        with ui.card().classes(
            'flex-1 items-center p-4 bg-rose-50 border border-rose-100'
            ' shadow-none rounded-xl'
        ):
          ui.label('Error Devices').classes(
              'text-xs font-semibold text-rose-600 uppercase tracking-wider'
          )
          self.e_count = ui.label(str(self.error_devices)).classes(
              'text-3xl font-bold text-rose-600 mt-1'
          )

  def update_counts(
      self, total: int = 0, active: int = 0, inactive: int = 0, error: int = 0
  ):
    self.t_count.set_text(str(total))
    self.a_count.set_text(str(active))
    self.i_count.set_text(str(inactive))
    self.e_count.set_text(str(error))
