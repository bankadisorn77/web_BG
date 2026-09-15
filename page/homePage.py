from component.dashboard_card import DashboardCard
from component.device_crad import DeviceCard
from nicegui import ui


class homePage:

  def __init__(
      self,
      logout=None,
      database=None,
      mq=None,
      on_device_update=None,
      on_device_update_all=None,
  ):
    self.database = database
    self.mq = mq
    self.cards_id = {}
    self.on_device_update = on_device_update
    self.on_device_update_all = on_device_update_all
    self.target_delete_device = None  # เก็บเครื่องที่กำลังจะลบ

    self.device = self.database.get_all_devices() if self.database else []
    (
        self.total_devices,
        self.active_devices,
        self.inactive_devices,
        self.error_devices,
    ) = (self.database.get_device_counts() if self.database else (0, 0, 0, 0))

    # Header Bar
    with ui.header().classes(
        'bg-white text-slate-800 shadow-sm justify-between items-center px-10'
        ' py-4'
    ):
      with ui.row().classes('items-center gap-3'):
        ui.icon('precision_manufacturing', color='primary').classes('text-3xl')
        ui.label('BG System').classes('text-2xl font-bold tracking-wide')
      with ui.row().classes('items-center gap-4'):
        ui.button('LOGOUT', on_click=logout, color='red').props(
            'unelevated text-color=white'
        )

    # ------------------ สร้าง Confirmation Dialog ไว้ที่ระดับ Page ------------------
    with ui.dialog() as self.confirm_dialog, ui.card().classes(
        'p-6 rounded-xl w-96'
    ):
      ui.label('Confirm Deletion').classes('text-lg font-bold text-slate-800')
      self.lbl_confirm_msg = ui.label('').classes('text-slate-600 my-2')

      with ui.row().classes('w-full justify-end gap-3 mt-4'):
        ui.button('Cancel', on_click=self.confirm_dialog.close).props(
            'flat text-color=grey'
        )
        ui.button(
            'Delete', color='red', on_click=self._on_confirm_delete_clicked
        ).props('unelevated text-color=white')

    # Dashboard Summary
    self.dashboard_card = DashboardCard(
        total_devices=self.total_devices,
        active_devices=self.active_devices,
        inactive_devices=self.inactive_devices,
        error_devices=self.error_devices,
    )

    # Container แสดงรายการ Cards
    self.devices_container = ui.row().classes(
        'w-full p-8 gap-6 flex-wrap justify-around items-start'
    )
    self._render_device_cards()

    if self.on_device_update:
      self.on_device_update(self.update_device_card)
    if self.on_device_update_all:
      self.on_device_update_all(self.update_all_device)

  def _render_device_cards(self):
    """Render Cards ทั้งหมดใหม่"""
    self.devices_container.clear()
    self.cards_id.clear()
    with self.devices_container:
      for dev in self.device:
        device_card = DeviceCard(
            device=dev, on_delete=lambda d=dev: self.deleteDevice(d)
        )
        self.cards_id[dev.get('id')] = device_card

  def update_all_device(self):
    self.device = self.database.get_all_devices() if self.database else []
    self._render_device_cards()
    self._refresh_dashboard_counts()

  def update_device_card(self, device_id, new_data):
    if device_id in self.cards_id:
      self.cards_id[device_id].update_status(new_data)
      self._refresh_dashboard_counts()

  def _refresh_dashboard_counts(self):
    (
        self.total_devices,
        self.active_devices,
        self.inactive_devices,
        self.error_devices,
    ) = (self.database.get_device_counts() if self.database else (0, 0, 0, 0))
    self.dashboard_card.update_counts(
        total=self.total_devices,
        active=self.active_devices,
        inactive=self.inactive_devices,
        error=self.error_devices,
    )

  def deleteDevice(self, device_data: dict):
    """เปิด Dialog ยืนยันการลบ"""
    self.target_delete_device = device_data
    dev_name = device_data.get('name', 'Unknown')
    self.lbl_confirm_msg.set_text(
        f'Are you sure you want to delete device "{dev_name}"?'
    )
    self.confirm_dialog.open()

  def _on_confirm_delete_clicked(self):
    """เมื่อกดปุ่ม Delete ใน Dialog"""
    self.confirm_dialog.close()
    if not self.target_delete_device:
      return

    device_id = self.target_delete_device.get('id')
    device_name = self.target_delete_device.get('name', 'Unknown')

    # 1. ลบข้อมูลใน Database
    if self.database:
      success = self.database.delete_device(device_id)
      if not success:
        ui.notify(
            f'Failed to delete device "{device_name}" from database',
            color='negative',
        )
        return

    # 2. แจ้ง Edge Device ผ่าน MQTT
    if self.mq:
      del_payload = {
          'action': 'delete',
          'device_id': device_id,
          'name': device_name,
      }
      self.mq.on_del_device(msg=del_payload, device_name=device_name)

    # 3. อัปเดตรายการในหน้า UI (Render ใหม่ ป้องกันปัญหา Slot แตก)
    self.device = [d for d in self.device if d.get('id') != device_id]
    self._render_device_cards()
    self._refresh_dashboard_counts()

    # 4. แสดง Notification
    ui.notify(f'Device "{device_name}" deleted successfully.', color='positive')
    self.target_delete_device = None