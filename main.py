import gi
import time
import sqlite3

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Adw


class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect("timesheet.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                start_time TEXT,
                duration_seconds REAL
            )
        """)
        self.conn.commit()

    def log_entry(self, name, start, duration):
        self.cursor.execute(
            "INSERT INTO entries (task_name, start_time, duration_seconds) VALUES (?, ?, ?)",
            (name, start, duration),
        )
        self.conn.commit()


class ChessChronometer(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = DatabaseManager()
        self.set_title("Grandmaster Timesheet")
        self.set_default_size(450, 400)

        self.active_task_start = 0
        self.start_timestamp_str = ""
        self.is_running = False

        self.build_ui()
        self.apply_css()

    def build_ui(self):
        # Main Layout
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.add_css_class("chrono-frame")
        self.set_child(content)

        # Task Input
        self.task_entry = Gtk.Entry(placeholder_text="Current Task / Opening...")
        content.append(self.task_entry)

        # The Clock Face
        self.label_time = Gtk.Label(label="00:00:00")
        self.label_time.add_css_class("dial")
        content.append(self.label_time)

        # Plunger Button
        self.toggle_btn = Gtk.Button(label="PUSH PLUNGER")
        self.toggle_btn.add_css_class("plunger-button")
        self.toggle_btn.set_vexpand(True)
        self.toggle_btn.connect("clicked", self.on_toggle_timer)
        content.append(self.toggle_btn)

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        # Using a string here for portability, but you can use load_from_path
        css = """
        .chrono-frame { background-color: #3e2723; border-radius: 12px; }
        .dial { 
            font-size: 64px; 
            background: #f5f5dc; 
            color: #222; 
            border-radius: 100px; 
            padding: 40px;
            margin: 10px;
            border: 8px solid #1a1a1a;
        }
        .plunger-button { 
            font-weight: bold; 
            font-size: 18px; 
            background: #b71c1c; 
            color: white; 
        }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def on_toggle_timer(self, btn):
        if not self.is_running:
            self.is_running = True
            self.active_task_start = time.time()
            self.start_timestamp_str = time.ctime()
            self.toggle_btn.set_label("STOP MOVE")
            self.toggle_btn.remove_css_class("plunger-button")
            self.toggle_btn.add_css_class("suggested-action")  # GTK blue
            GLib.timeout_add(100, self.update_clock)
        else:
            self.is_running = False
            duration = time.time() - self.active_task_start
            self.db.log_entry(
                self.task_entry.get_text(), self.start_timestamp_str, duration
            )
            self.toggle_btn.set_label("START MOVE")
            self.toggle_btn.remove_css_class("suggested-action")
            self.toggle_btn.add_css_class("plunger-button")

    def update_clock(self):
        if not self.is_running:
            return False
        elapsed = time.time() - self.active_task_start
        self.label_time.set_label(time.strftime("%H:%M:%S", time.gmtime(elapsed)))
        return True


class ChronoApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.lynx.chesschrono")

    def do_activate(self):
        win = ChessChronometer(application=self)
        win.present()


app = ChronoApp()
app.run(None)
