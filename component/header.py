from nicegui import app, ui
import config.config as config

class AppHeader(ui.header):
    def __init__(self, logout=None,device_name=None):
        super().__init__()
        self.classes(
            'bg-white text-slate-800 border-b border-slate-100 shadow-sm '
            'justify-between items-center px-8 py-3 w-full'
        )
        self.device_name = device_name
        self.logout = logout
        self.web_schema = config.WEB_SCHEMA
        webserver = self.web_schema.get("webserver", {}) if isinstance(self.web_schema, dict) else {}
        header_info = webserver.get("hearder", {}) 
        self.project_name = header_info.get("project_name", "Default Project")
        self.project_title = header_info.get("project_title", "Default Title")

        with self:
            with ui.row().classes('items-center gap-3 cursor-pointer'):
                with ui.element('div').classes('p-2 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center'):
                    ui.icon('precision_manufacturing').classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label(self.project_name).classes('text-xl font-extrabold tracking-tight text-slate-900 leading-tight')
                    ui.label(self.project_title).classes('text-[11px] font-medium text-slate-400')
            with ui.row().classes('items-center gap-2'):
                if self.device_name is not None:
                    ui.label(
                        device_name
                    ).classes('px-3 font-semibold rounded-lg')
                    ui.separator().props('vertical').classes('h-6 mx-2 border-slate-200')
                ui.button(
                    'Home', icon='dashboard', on_click=lambda: ui.navigate.to('/')
                ).props('flat dense no-caps color=slate-700').classes('px-3 font-semibold hover:bg-slate-50 rounded-lg')
                ui.button(
                    'Users', icon='manage_accounts', on_click=lambda: ui.navigate.to('/management')
                ).props('flat dense no-caps color=slate-700').classes(
                    'px-3 font-semibold hover:bg-slate-50 rounded-lg'
                ).bind_visibility_from(app.storage.user, 'role', backward=lambda r: r == 'admin')

                ui.button(
                    'Register', icon='person_add', on_click=lambda: ui.navigate.to('/register')
                ).props('flat dense no-caps color=slate-700').classes(
                    'px-3 font-semibold hover:bg-slate-50 rounded-lg'
                ).bind_visibility_from(app.storage.user, 'role', backward=lambda r: r == 'admin')
                ui.separator().props('vertical').classes('h-6 mx-2 border-slate-200')

                with ui.row().classes('items-center gap-2 mr-2'):
                    ui.avatar(icon='person', size='sm', color='slate-200', text_color='slate-700').classes('font-bold')
                    with ui.column().classes('gap-0'):
                        ui.label().bind_text_from(app.storage.user, 'username', backward=lambda u: u or 'Guest').classes(
                            'text-xs font-bold text-slate-800 leading-none'
                        )
                        ui.label().bind_text_from(app.storage.user, 'role', backward=lambda r: (r or 'User').upper()).classes(
                            'text-[9px] font-semibold text-blue-600 tracking-wider'
                        )

                ui.button(
                    'Logout', icon='logout', on_click=self.handle_logout
                ).props('flat dense no-caps color=red-600').classes(
                    'px-3 py-1 bg-red-50 hover:bg-red-100 rounded-lg font-semibold text-xs'
                )

    def handle_logout(self):
        if callable(self.logout):
            self.logout()
        else:
            app.storage.user.clear()
            ui.navigate.to('/login')