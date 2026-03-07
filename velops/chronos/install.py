"""
VelOps Chronos Tracker: Track your work time with effortless workflow
Copyright (C) 2026  Simon ANDRÉ

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import sys
from pathlib import Path
import importlib.resources


def install_desktop_integration():
    """Copies the .desktop and .svg files to the host OS so it appears in the app launcher."""
    app_dir = Path.home() / ".local" / "share" / "applications"
    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    
    app_dir.mkdir(parents=True, exist_ok=True)
    icon_dir.mkdir(parents=True, exist_ok=True)

    try:
        # For Python 3.10+, use files() API
        assets = importlib.resources.files("velops.chronos") / "assets"
        
        desktop_dest = app_dir / "velops.chronos.tracker.desktop"
        icon_dest = icon_dir / "velops.chronos.tracker.svg"

        # Copy if they don't exist
        if not desktop_dest.exists():
            desktop_dest.write_bytes((assets / "velops.chronos.tracker.desktop").read_bytes())
        
        if not icon_dest.exists():
            icon_dest.write_bytes((assets / "velops.chronos.tracker.svg").read_bytes())
            
    except Exception as e:
        print(f"Warning: Failed to install desktop integration: {e}", file=sys.stderr)