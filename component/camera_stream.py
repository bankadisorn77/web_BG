import time
from typing import List, Union
from nicegui import ui

class VideoCard(ui.card):
    def __init__(self, stream_urls: Union[List[str], str]):
        super().__init__()
        self.classes('w-full max-w-[1500px] p-4 shadow-md bg-white rounded-xl')
        
        if isinstance(stream_urls, str):
            self.stream_urls = [stream_urls]
        else:
            self.stream_urls = stream_urls or []

        self.current_index = 0
        self.active_stream_url = self.stream_urls[0] if self.stream_urls else ''
        self.camera_buttons = []
        self.camera_dots = []  

        with self:
            # Header
            with ui.row().classes('items-center justify-between w-full mb-3'):
                ui.label('Live Camera Feed').classes('text-lg font-bold text-slate-800')

                with ui.row().classes('items-center gap-3'):
                    self.toggle_switch = ui.switch(
                        'Overlay', value=False, on_change=self.toggle_overlay
                    )
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('fiber_manual_record', color='red').classes('animate-pulse text-xs')
                        ui.label('LIVE').classes('text-xs font-bold text-red-500 font-mono')

            # Stream Video Screen
            with ui.element('div').classes(
                'w-full aspect-video bg-black rounded-lg overflow-hidden relative'
            ):
                self.img_element = ui.html(self._render_stream_html()).classes('w-full h-full block')

            # Segmented Control Bar
            if len(stream_urls) > 1:
              with ui.element('div').classes(
                'flex items-center justify-center p-1.5 bg-slate-100/80 rounded-2xl gap-2 w-fit mx-auto mt-4 shadow-inner border border-slate-200/60'
            ):
                for idx, url in enumerate(self.stream_urls):
                  is_active = (idx == self.current_index)
                  btn_theme = 'bg-white shadow-sm font-bold' if is_active else 'bg-transparent hover:bg-white/60 font-medium'
                  content_color = 'text-blue-600' if is_active else 'text-slate-600'

                  with ui.button(
                      on_click=lambda i=idx: self.switch_camera(i)
                  ).props('unelevated no-caps').classes(
                      f'px-4 py-2 rounded-xl transition-all duration-200 flex items-center gap-2 text-sm {btn_theme}'
                  ) as btn:
                      icon = ui.icon('videocam').classes(f'text-base {content_color}')
                      label = ui.label(f'CAM {idx + 1:02d}').classes(f' ml-2 tracking-wide text-xs {content_color}')
                      dot_style = 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' if is_active else 'bg-slate-300'
                      dot = ui.element('span').classes(f'ml-2 w-2 h-2 rounded-full {dot_style} transition-colors')
                      self.camera_buttons.append((btn, icon, label, dot))

    def switch_camera(self, index: int):
        if index < 0 or index >= len(self.stream_urls):
            return

        self.current_index = index
        self.active_stream_url = self.stream_urls[index]

        for i, (btn, icon, label, dot) in enumerate(self.camera_buttons):
            btn.classes(remove='bg-white shadow-sm font-bold bg-transparent hover:bg-white/60 font-medium')
            icon.classes(remove='text-blue-600 text-slate-600')
            label.classes(remove='text-blue-600 text-slate-600')
            dot.classes(remove='bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] bg-slate-300')

            if i == index:
                btn.classes(add='bg-white shadow-sm font-bold')
                icon.classes(add='text-blue-600')
                label.classes(add='text-blue-600')
                dot.classes(add='bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]')
            else:
                btn.classes(add='bg-transparent hover:bg-white/60 font-medium')
                icon.classes(add='text-slate-600')
                label.classes(add='text-slate-600')
                dot.classes(add='bg-slate-300')

        self.reload_stream()

    def toggle_overlay(self, e):
        display_style = 'block' if e.value else 'none'
        ui.run_javascript(f"""
            const svg = document.getElementById("stream_svg_overlay");
            if (svg) svg.style.display = "{display_style}";
        """)

    def _render_stream_html(self, timestamp: float = None) -> str:
      src = (
          f'{self.active_stream_url}?t={timestamp}'
          if timestamp
          else self.active_stream_url
      )
      overlay_style = (
          'block'
          if getattr(self, 'toggle_switch', None) and self.toggle_switch.value
          else 'none'
      )

      return f"""
        <div style="position: relative; width: 100%; height: 100%; display: block;">
            <img id="mjpeg_display" 
                 src="{src}" 
                 data-base-src="{self.active_stream_url}"
                 style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: fill; display: block;" 
                 onerror="this.style.opacity='0.2'; setTimeout(()=>{{ const base = this.getAttribute('data-base-src') || this.src.split('?')[0]; this.src = base + '?t=' + new Date().getTime(); this.style.opacity='1'; }}, 2000);" />

            <svg id="stream_svg_overlay"
                 viewBox="0 0 1000 1000" 
                 preserveAspectRatio="none"
                 style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; display: {overlay_style}; z-index: 10;">
                
                <rect x="460" y="56" width="77" height="90" fill="none" stroke="#22FF00" stroke-width="3" />
                <polygon points="459,558 203,352 47,706 307,903" fill="none" stroke="#22FF00" stroke-width="3" />
                <polygon points="547,553 796,335 959,674 712,890" fill="none" stroke="#22FF00" stroke-width="3" />
                <polygon points="184,0 805,0 812,318 503,568 185,334" fill="none" stroke="#22FF00" stroke-width="3" />
            </svg>
        </div>
        """

    def reload_stream(self):
        new_src = f'{self.active_stream_url}?t={time.time()}'
        ui.run_javascript(f"""
                const img = document.getElementById("mjpeg_display");
                if (img) {{
                    img.src = "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100%25' height='100%25'%3E%3Crect width='100%25' height='100%25' fill='%231e293b'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-size='20'%3ENO SIGNAL%3C/text%3E%3C/svg%3E";
                    
                    setTimeout(() => {{
                        img.setAttribute("data-base-src", "{self.active_stream_url}");
                        img.src = "{new_src}";
                    }}, 50);
                }}
            """)