"""
Child app config — persisted to data/child_config.json
"""
import os, json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'child_config.json')

DEFAULTS = {
    # Identity
    "app_name":           "Grefin Timer",
    "pc_name":            "PC-01",
    "shop_name":          "PC Cafe",
    # Admin
    "admin_keyword":      "grefin",
    "admin_password":     "admin",
    # Branding
    "logo_path":          os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png'),
    "logo_taskbar_path":  os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo_taskbar.png'),
    # Networking
    "server_port":        9000,
    "standalone":         True,
    "parent_ip":          "",
    "parent_port":        9100,
    # Serial / coin
    "com_port":           "COM1",
    "baud_rate":          9600,
    "com_mode":           "Auto",
    "coin_map":           {"1": 1800, "5": 9000, "10": 18000, "20": 36000},
    # Timer appearance
    "timer_speed":        1.0,
    "timer_font_size":    26,
    "timer_color":        "#00e5ff",
    "blink_threshold":    60,
    # Overlay
    "animation_path":     os.path.join(os.path.dirname(__file__), '..', 'assets', 'one_piece_ship.gif'),
    "background_type":    "Live Wallpaper",
    "background_path":    os.path.join(os.path.dirname(__file__), '..', 'assets', 'luffy_nika_live_wallpaper.mp4'),
    "shutdown_countdown": 180,
    "dev_mode": False,
    # Startup / security options
    "launch_on_startup": False,
    "disable_task_manager": False,
    "disable_signout": False,
    "disable_task_view": False,
    "watchdog_reboot_enabled": True,
    # Sound options
    "voice_file_30s": os.path.join(os.path.dirname(__file__), '..', 'assets', 'no_more_time.wav'),
    # Schedule settings
    "schedule_enabled": False,
    "opening_hours": "09:00",
    "closing_hours": "23:00",
    "warning_time": "30:00",  # 30 minutes before closing
    "warning_message": "⚠ Shop is closing soon!",  # This is overridden by timer manager with closing time
    "closing_message": "Sorry, we are now closed!",
    "closing_logo_path": os.path.join(os.path.dirname(__file__), '..', 'assets', 'closing_logo.jpg'),
}

def load() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            cfg = DEFAULTS.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULTS.copy()

def save(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
