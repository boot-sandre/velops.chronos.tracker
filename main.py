import gi
import time
import sqlite3
from datetime import datetime

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw, Gio


class DatabaseManager:
    def __init__(self, db_path="timesheet.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Create projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        # Create entries table with project link
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                task_name TEXT,
                start_time TEXT,
                duration_seconds REAL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        self.conn.commit()

    def add_project(self, name):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO projects (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_projects(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM projects")
        return [row[0] for row in cursor.fetchall()]

    def save_entry(self, project_name, duration):
        cursor = self.conn.cursor()
        # Get project ID
        cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
        project_row = cursor.fetchone()
        project_id = project_row[0] if project_row else None

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO entries (project_id, task_name, start_time, duration_seconds)
            VALUES (?, ?, ?, ?)
        """,
            (project_id, "Work Session", start_time, duration),
        )
        self.conn.commit()


class DualChessChrono(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = DatabaseManager()
        self.set_title("VelOps Productivity")
        self.set_default_size(600, 500)

        self.state = 0
        self.work_elapsed = 0
        self.break_elapsed = 0
        self.last_tick = 0

        self.build_ui()
        self.apply_css()
        self.refresh_project_list()

        GLib.timeout_add(100, self.update_clocks)

    def build_ui(self):
        main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_layout.set_margin_end(20)
        main_layout.add_css_class("chrono-frame")
        self.set_child(main_layout)

        # --- Project Management Section ---
        proj_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # Project DropDown
        self.project_model = Gio.ListStore(item_type=Gtk.StringObject)
        self.project_dropdown = Gtk.DropDown(
            model=self.project_model,
            expression=Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"),
        )

        # New Project Entry
        self.new_proj_entry = Gtk.Entry(placeholder_text="New Project Name...")
        add_proj_btn = Gtk.Button(label="Add Project")
        add_proj_btn.connect("clicked", self.on_add_project)

        proj_box.append(Gtk.Label(label="Project:"))
        proj_box.append(self.project_dropdown)
        proj_box.append(self.new_proj_entry)
        proj_box.append(add_proj_btn)
        main_layout.append(proj_box)

        # --- Clock Display ---
        clock_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        clock_hbox.set_homogeneous(True)

        work_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.work_label = Gtk.Label(label="00:00:00")
        self.work_label.add_css_class("dial")
        work_vbox.append(Gtk.Label(label="PROJECT WORK"))
        work_vbox.append(self.work_label)

        break_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.break_label = Gtk.Label(label="00:00:00")
        self.break_label.add_css_class("dial")
        break_vbox.append(Gtk.Label(label="PAUSE / IDLE"))
        break_vbox.append(self.break_label)

        clock_hbox.append(work_vbox)
        clock_hbox.append(break_vbox)
        main_layout.append(clock_hbox)

        self.toggle_btn = Gtk.Button(label="START SESSION")
        self.toggle_btn.add_css_class("plunger-button")
        self.toggle_btn.connect("clicked", self.on_toggle)
        main_layout.append(self.toggle_btn)

        self.stop_btn = Gtk.Button(label="STOP & SAVE SESSION")
        self.stop_btn.add_css_class("stop-button")
        self.stop_btn.connect("clicked", self.on_stop)
        main_layout.append(self.stop_btn)

    def on_add_project(self, btn):
        name = self.new_proj_entry.get_text().strip()
        if name and self.db.add_project(name):
            self.refresh_project_list()
            self.new_proj_entry.set_text("")

    def refresh_project_list(self):
        self.project_model.remove_all()
        projects = self.db.get_projects()
        for p in projects:
            self.project_model.append(Gtk.StringObject.new(p))

    def on_toggle(self, btn):
        now = time.time()
        if self.state == 0 or self.state == 2:
            self.state = 1
            self.work_label.add_css_class("active-dial")
            self.break_label.remove_css_class("active-dial")
            btn.set_label("SWITCH TO BREAK")
        else:
            self.state = 2
            self.break_label.add_css_class("active-dial")
            self.work_label.remove_css_class("active-dial")
            btn.set_label("SWITCH TO WORK")
        self.last_tick = now

    def on_stop(self, btn):
        selected_item = self.project_dropdown.get_selected_item()
        if selected_item and self.work_elapsed > 1:
            project_name = selected_item.get_string()
            self.db.save_entry(project_name, self.work_elapsed)
            print(f"Saved {self.format_time(self.work_elapsed)} to {project_name}")

        self.state = 0
        self.work_elapsed = 0
        self.break_elapsed = 0
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
        self.work_label.set_label(self.format_time(self.work_elapsed))
        self.break_label.set_label(self.format_time(self.break_elapsed))
        return True

    def format_time(self, seconds):
        return time.strftime("%H:%M:%S", time.gmtime(seconds))

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        # Keep existing CSS styles
        css = """
        .chrono-frame { background-color: #4e342e; border-radius: 15px; padding: 20px; }
        .dial { 
            font-size: 48px; font-family: 'Monospace'; background: #fdf5e6; 
            color: #444; border-radius: 15px; padding: 20px; border: 5px solid #8d6e63;
        }
        .active-dial { border: 5px solid #d4a017; background: #ffffff; color: #000; }
        .plunger-button { margin: 10px; padding: 15px; background: #3e2723; color: #d7ccc8; font-weight: bold; }
        .stop-button { margin: 10px; padding: 10px; background: #263238; color: #eceff1; }
        .stop-button:hover { background: #b71c1c; }
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


if __name__ == "__main__":
    app = ChronoApp()
    app.run(None)
