import time

from nicegui import app, ui

from component.header import AppHeader


class RegisterPage:

  def __init__(self, database=None,logout=None):
    self.database = database
    self.username_input = None
    self.password_input = None
    self.comfrime_pass_input = None
    self.role_input = None
    # HEADER
    AppHeader(logout=logout)

    with ui.card().classes(
        'absolute-center w-80 shadow-lg p-6 bg-white rounded-xl'
    ):
        ui.label('BG System Register').classes(
            'text-xl font-bold text-center w-full mb-4 text-slate-800'
        )
        self.username_input = ui.input('Username').classes('w-full').props(
            'outlined dense'
        )
        self.role_input = ui.select(
            options=['User','admin'],
            label='Role'
        ).classes('w-full mt-2').props('outlined dense')
        self.password_input = ui.input(
            'Password', password=True, password_toggle_button=True
        ).classes('w-full mt-2').props('outlined dense')
        self.comfrime_pass_input = ui.input(
                    'Confrime password', password=True, password_toggle_button=True
        ).classes('w-full mt-2').props('outlined dense')
        #   self.password_input.on('keydown.enter', self.login)
        ui.button('REGISTER', on_click=self.register).classes(
            'w-full mt-4 bg-slate-800 text-white font-bold'
        )

  def register(self):
        username = (self.username_input.value or '').strip()
        password = self.password_input.value or ''
        comfrime_password = self.comfrime_pass_input.value or ''
        role = self.role_input.value or ''
        if username is '' or password is '' or comfrime_password is '':
            ui.notify('Missing information', color='negative')
            return

        if comfrime_password != password:
            ui.notify('Password not match', color='negative')
            self.password_input.value = ''
            self.comfrime_pass_input.value = ''
            return

        if not self.database:
            ui.notify('Database not available', color='negative')
            return

        reg,msg = self.database.register_user(username,password,role)
        if not reg:
            ui.notify(f'Error {msg}', color='negative')
            self.username_input.value =''
            self.password_input.value = ''
            self.comfrime_pass_input.value = ''
            self.role_input.value=''

        ui.notify(f'user [{username}] :Registration successful.', color='positive')
        self.username_input.value =''
        self.password_input.value = ''
        self.comfrime_pass_input.value = ''
        self.role_input.value='user'