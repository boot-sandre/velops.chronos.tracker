import gi
import time

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw


class DualChessChrono(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("VelOps Productivity")
        self.set_default_size(600, 400)

        # 0 = Stopped, 1 = Work Active, 2 = Break Active
        self.state = 0
        self.work_elapsed = 0
        self.break_elapsed = 0
        self.last_tick = 0

        self.build_ui()
        self.apply_css()

        # Start the global heartbeat (10fps is enough for UI)
        GLib.timeout_add(100, self.update_clocks)

    def build_ui(self):
        main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_layout.set_margin_end(20)
        main_layout.add_css_class("chrono-frame")
        self.set_child(main_layout)

        # The Dual Clock Display
        clock_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        clock_hbox.set_homogeneous(True)

        # Work Side (Left)
        work_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.work_label = Gtk.Label(label="00:00:00")
        self.work_label.add_css_class("dial")
        work_vbox.append(Gtk.Label(label="PROJECT WORK"))
        work_vbox.append(self.work_label)

        # Break Side (Right)
        break_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.break_label = Gtk.Label(label="00:00:00")
        self.break_label.add_css_class("dial")
        break_vbox.append(Gtk.Label(label="PAUSE / IDLE"))
        break_vbox.append(self.break_label)

        clock_hbox.append(work_vbox)
        clock_hbox.append(break_vbox)
        main_layout.append(clock_hbox)

        # The Toggle Button (The Plunger)
        self.toggle_btn = Gtk.Button(label="START SESSION")
        self.toggle_btn.add_css_class("plunger-button")
        self.toggle_btn.connect("clicked", self.on_toggle)
        main_layout.append(self.toggle_btn)

        # Stop and Reset Button
        self.stop_btn = Gtk.Button(label="STOP & RESET SESSION")
        self.stop_btn.add_css_class("stop-button")
        self.stop_btn.connect("clicked", self.on_stop)
        main_layout.append(self.stop_btn)

    def on_toggle(self, btn):
        now = time.time()
        if self.state == 0 or self.state == 2:
            self.state = 1  # Switch to Work
            self.work_label.add_css_class("active-dial")
            self.break_label.remove_css_class("active-dial")
            btn.set_label("SWITCH TO BREAK")
        else:
            self.state = 2  # Switch to Break
            self.break_label.add_css_class("active-dial")
            self.work_label.remove_css_class("active-dial")
            btn.set_label("SWITCH TO WORK")

        self.last_tick = now

    def on_stop(self, btn):
        # Stop everything
        self.state = 0

        # Summary for the user
        print(
            f"Session Ended.\nWork: {self.format_time(self.work_elapsed)}\nBreak: {self.format_time(self.break_elapsed)}"
        )

        # Reset counters
        self.work_elapsed = 0
        self.break_elapsed = 0

        # Reset UI
        self.work_label.set_label("00:00:00")
        self.break_label.set_label("00:00:00")
        self.work_label.remove_css_class("active-dial")
        self.break_label.remove_css_class("active-dial")
        self.toggle_btn.set_label("START SESSION")

    def update_clocks(self):
        if self.state == 0:
            return True

        now = time.time()
        delta = now - self.last_tick
        self.last_tick = now

        if self.state == 1:
            self.work_elapsed += delta
        elif self.state == 2:
            self.break_elapsed += delta

        # Update labels
        self.work_label.set_label(self.format_time(self.work_elapsed))
        self.break_label.set_label(self.format_time(self.break_elapsed))
        return True

    def format_time(self, seconds):
        return time.strftime("%H:%M:%S", time.gmtime(seconds))

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        .chrono-frame { background-color: #4e342e; border-radius: 15px; border: 4px solid #2d1b18; }
        .dial { 
            font-size: 48px; 
            font-family: 'Monospace';
            background: #fdf5e6; 
            color: #444; 
            border-radius: 15px; 
            padding: 20px;
            border: 5px solid #8d6e63;
        }
        .active-dial { 
            border: 5px solid #d4a017; /* Gold highlight for active clock */
            background: #ffffff;
            color: #000;
        }
        .plunger-button { 
            margin: 20px; 
            padding: 15px; 
            font-weight: bold; 
            background: #3e2723;
            color: #d7ccc8;
        }
        .stop-button {
            margin: 0 20px 20px 20px;
            padding: 10px;
            background: #263238;
            color: #eceff1;
            border: 1px solid #455a64;
        }
        .stop-button:hover {
            background: #b71c1c; /* Turns red on hover to signal danger/reset */
        }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )


class ChronoApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.lynx.chesschrono")

    def do_activate(self):
        win = DualChessChrono(application=self)
        win.present()


app = ChronoApp()
app.run(None)
