import time
from nicegui import app, ui
from component.header import AppHeader
from component.user_card import UserCard

class Management:

    def __init__(self, database=None, logout=None):
        self.database = database
        try:
            self.users = database.get_all_user()
        except Exception as e:
            self.users = [0]
        AppHeader(logout=logout)
        
        with ui.card().classes('w-[80%] self-center p-6 bg-slate-50 border border-slate-100 shadow-sm rounded-xl'):

            with ui.row().classes('w-full items-center justify-between border-b border-slate-200 pb-4 px-2'):
                ui.label('User Management').classes('text-2xl font-bold tracking-wide text-slate-800')
                
                self.user_search = ui.input(
                    placeholder='Search by name...'
                ).classes('w-64').props('outlined dense').on('update:model-value', lambda: self.render_user_list.refresh())
                

                with self.user_search.add_slot('append'):
                    ui.icon('search', color='slate-400')

            with ui.column().classes('w-full items-center p-4 gap-4 mx-auto'):
                self.render_user_list()

    @ui.refreshable
    def render_user_list(self):
        try:
            users = self.database.get_all_user()
        except Exception:
            users = []

        search_query = getattr(self, 'user_search', None)
        if search_query and search_query.value:
            query = search_query.value.strip().lower()
            users = [u for u in users if query in u.get('username', '').lower()]

        for index, user in enumerate(users, start=1):
            UserCard(
                database=self.database,
                index=index,
                user_id=user['id'],          
                name=user['username'],
                role=user['role'],
                on_deleted=self.render_user_list.refresh  
            )
