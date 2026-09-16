from nicegui import app, ui

class UserCard(ui.card):
    def __init__(self, database=None, index=1, user_id=None, name=None, role=None, on_deleted=None):
        super().__init__()
        self.classes('w-full max-w-md p-4 shadow-sm border border-slate-100 rounded-xl')
        self.database = database
        self.user_id = user_id or 999
        self.name = name or 'NO name found'
        self.role = role or 'No role found'
        self.on_deleted = on_deleted
        
        with self:
            with ui.row().classes('w-full items-center justify-between no-wrap gap-4'):
                with ui.row().classes('items-center gap-4'):
                    with ui.element('div').classes('flex items-center justify-center w-8 h-8 rounded-full bg-slate-100'):
                        ui.label(str(index)).classes('text-xs font-bold text-slate-500')
                    
                    with ui.column().classes('gap-0'):
                        ui.label(self.name).classes('text-base font-semibold text-slate-800')
                        ui.label(self.role).classes('text-xs font-medium text-slate-400 uppercase tracking-wider')
                
                with ui.row().classes('items-center gap-1 no-wrap'):
                    ui.button(icon='edit').props('flat round dense color=grey-8').classes('hover:bg-slate-100')
                    ui.button(icon='delete', on_click=self.handle_delete).props(
                        'flat round dense color=red'
                    ).classes('hover:bg-red-50')


    async def confirm_action(self,title: str, message: str) -> bool:
        with ui.dialog() as dialog, ui.card().classes('p-6 rounded-xl'):
            ui.label(title).classes('text-lg font-bold')
            ui.label(message).classes('text-sm text-slate-500 mb-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat color=grey')
                ui.button('Confirm', on_click=lambda: dialog.submit(True), color='red').props('unelevated')

        result =  await dialog
        return result or False
    
    async def handle_delete(self):
        if not self.database:
            return
        is_confirmed = await self.confirm_action('DELETE',f'delete {self.name} ')

        if is_confirmed:
            status, msg = self.database.delete_user(str(self.user_id))
            if status:
                ui.notify(f'User [{self.name}] deleted successfully.', color='positive')
            else:
                ui.notify(f'Error {msg}', color='negative')
                return
            
            if callable(self.on_deleted):
                self.on_deleted()
        else:
            ui.notify('Cancel', color='info')

