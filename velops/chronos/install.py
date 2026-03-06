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