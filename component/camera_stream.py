import time
from nicegui import ui


class VideoCard(ui.card):

  def __init__(self, stream_url: str):
    super().__init__()

    self.classes('w-full max-w-[1500px] p-4 shadow-md bg-white rounded-xl')
    self.stream_url = stream_url
    self.show_overlay = True

    with self:
      with ui.row().classes('items-center justify-between w-full mb-3'):
        ui.label('Live Camera Feed').classes('text-lg font-bold text-slate-800')

        with ui.row().classes('items-center gap-3'):
          self.toggle_switch = ui.switch(
              'Overlay', value=False, on_change=self.toggle_overlay
          )

          with ui.row().classes('items-center gap-1'):
            ui.icon('fiber_manual_record', color='red').classes(
                'animate-pulse text-xs'
            )
            ui.label('LIVE').classes('text-xs font-bold text-red-500 font-mono')


      with ui.element('div').classes(
          'w-full aspect-video bg-black rounded-lg overflow-hidden relative'
      ):
        self.img_element = ui.html(self._render_stream_html()).classes(
            'w-full h-full block'
        )

  def toggle_overlay(self, e):
    display_style = 'block' if e.value else 'none'
    ui.run_javascript(f"""
            const svg = document.getElementById("stream_svg_overlay");
            if (svg) svg.style.display = "{display_style}";
        """)

  def _render_stream_html(self, timestamp: float = None) -> str:
    src = f'{self.stream_url}?t={timestamp}' if timestamp else self.stream_url

    return f"""
        <div style="position: relative; width: 100%; height: 100%; display: block;">
            <img id="mjpeg_display" 
                 src="{src}" 
                 style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: fill; display: block;" 
                 onerror="this.style.opacity='0'; setTimeout(()=>{{ this.src='{self.stream_url}?t='+new Date().getTime(); this.style.opacity='1'; }}, 1000);" />

            <svg id="stream_svg_overlay"
                 viewBox="0 0 1000 1000" 
                 preserveAspectRatio="none"
                 style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; display: none; z-index: 10;">
                
                <rect x="460" y="56" width="77" height="90" 
                      fill="none" stroke="#22FF00" stroke-width="3" />

                <polygon points="459,558 203,352 47,706 307,903" 
                         fill="none" stroke="#22FF00" stroke-width="3" />

                <polygon points="547,553 796,335 959,674 712,890" 
                         fill="none" stroke="#22FF00" stroke-width="3" />

                <polygon points="184,0 805,0 812,318 503,568 185,334" 
                         fill="none" stroke="#22FF00" stroke-width="3" />
            </svg>
        </div>
        """

  def reload_stream(self):
    self.img_element.set_content(self._render_stream_html(time.time()))