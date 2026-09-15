import time

from nicegui import app, ui


class loginPage:

  def __init__(self, database=None):
    self.database = database
    self.username_input = None
    self.password_input = None
    with ui.card().classes(
        'absolute-center w-80 shadow-lg p-6 bg-white rounded-xl'
    ):
      ui.label('BG System Login').classes(
          'text-xl font-bold text-center w-full mb-4 text-slate-800'
      )
      self.username_input = ui.input('Username').classes('w-full').props(
          'outlined dense'
      )
      self.password_input = ui.input(
          'Password', password=True, password_toggle_button=True
      ).classes('w-full mt-2').props('outlined dense')
      self.password_input.on('keydown.enter', self.login)
      ui.button('LOGIN', on_click=self.login).classes(
          'w-full mt-4 bg-slate-800 text-white font-bold'
      )

  def login(self):
    username = (self.username_input.value or '').strip()
    password = self.password_input.value or ''

    if not self.database:
      ui.notify('Database not available', color='negative')
      return

    if self.database.authenticate_user(username, password):
      app.storage.user['authenticated'] = True
      app.storage.user['username'] = username
      app.storage.user['last_active'] = time.time()
      ui.notify(f'Welcome {username}', color='positive')
      ui.navigate.to('/')
    else:
      ui.notify('Username or Password wrong', color='negative')
