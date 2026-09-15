from nicegui import ui


class TerminalLog(ui.card):

  def __init__(self, title: str = 'Terminal Logs', max_lines: int = 100):
    super().__init__()
    self.classes('w-full p-4 bg-white rounded-xl shadow-md')

    with self:
      with ui.row().classes('w-full justify-between items-center mb-2'):
        with ui.row().classes('items-center gap-2'):
          ui.icon('terminal', color='green').classes('text-lg')
          ui.label(title).classes('text-sm font-semibold tracking-wider')

        ui.button(icon='delete', on_click=self.clear_log).props(
            'flat dense round text-color=slate-700'
        )

      self.log_view = ui.log(max_lines=max_lines).classes(
          'w-full h-40 bg-black p-3 rounded-lg font-mono text-xs'
          ' text-green-400 overflow-y-auto'
      )

  def write(self, message: str):
    self.log_view.push(message)

  def clear_log(self):
    self.log_view.clear()
