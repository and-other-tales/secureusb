#!/usr/bin/env python3
"""
Configuration Module for SecureUSB

Manages application configuration and settings.
"""

import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Manages SecureUSB configuration."""

    DEFAULT_CONFIG = {
        'version': 1,
        'general': {
            'enabled': True,
            'auto_start': True,
            'timeout_seconds': 30,
            'default_action': 'deny',  # deny, allow, power_only
        },
        'notifications': {
            'enabled': True,
            'sound': False,
            'show_on_deny': True,
            'show_on_timeout': True,
        },
        'security': {
            'require_totp_for_whitelisted': True,
            'log_retention_days': 90,
            'block_unknown_devices': True,
        },
        'ui': {
            'show_device_details': True,
            'remember_window_position': True,
            'theme': 'system',  # system, light, dark
        }
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Configuration directory path. If None, uses ~/.config/secureusb
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".config" / "secureusb"
        else:
            self.config_dir = Path(config_dir)

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"

        self.config = self._load_config()

        # Create config file if it doesn't exist
        if not self.config_file.exists():
            self.save()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)

                # Merge with defaults to add any new settings
                return self._merge_configs(self.DEFAULT_CONFIG, config)

            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                return copy.deepcopy(self.DEFAULT_CONFIG)
        else:
            # Return default config (file will be created in __init__)
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """
        Recursively merge loaded config with defaults.

        Args:
            default: Default configuration dictionary
            loaded: Loaded configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        result = copy.deepcopy(default)

        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value

        return result

    def save(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Configuration key path (e.g., 'general.enabled')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> bool:
        """
        Set configuration value using dot notation.

        Args:
            key_path: Configuration key path (e.g., 'general.enabled')
            value: Value to set

        Returns:
            True if successful, False otherwise
        """
        keys = key_path.split('.')
        config = self.config

        try:
            # Navigate to parent of target key
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # Set the value
            config[keys[-1]] = value
            return self.save()

        except Exception as e:
            print(f"Error setting config value: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """
        Reset configuration to defaults.

        Returns:
            True if successful, False otherwise
        """
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        return self.save()

    def is_enabled(self) -> bool:
        """Check if USB protection is enabled."""
        return self.get('general.enabled', True)

    def set_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable USB protection.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful, False otherwise
        """
        return self.set('general.enabled', enabled)

    def get_timeout(self) -> int:
        """Get authorization timeout in seconds."""
        return self.get('general.timeout_seconds', 30)

    def set_timeout(self, seconds: int) -> bool:
        """
        Set authorization timeout.

        Args:
            seconds: Timeout in seconds (minimum 10, maximum 300)

        Returns:
            True if successful, False otherwise
        """
        seconds = max(10, min(300, seconds))
        return self.set('general.timeout_seconds', seconds)

    def export_config(self, export_path: Path) -> bool:
        """
        Export configuration to file.

        Args:
            export_path: Path to export file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, import_path: Path) -> bool:
        """
        Import configuration from file.

        Args:
            import_path: Path to import file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(import_path, 'r') as f:
                imported = json.load(f)

            self.config = self._merge_configs(self.DEFAULT_CONFIG, imported)
            return self.save()

        except Exception as e:
            print(f"Error importing config: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    print("=== SecureUSB Configuration Test ===\n")

    config = Config()

    print("Current Configuration:")
    print(f"  Enabled: {config.is_enabled()}")
    print(f"  Timeout: {config.get_timeout()}s")
    print(f"  Auto-start: {config.get('general.auto_start')}")
    print(f"  Notifications: {config.get('notifications.enabled')}")
    print(f"  Require TOTP for whitelisted: {config.get('security.require_totp_for_whitelisted')}")

    # Test setting values
    print("\nTesting configuration changes...")
    config.set('general.timeout_seconds', 45)
    config.set('notifications.sound', True)

    print(f"  New timeout: {config.get_timeout()}s")
    print(f"  Sound enabled: {config.get('notifications.sound')}")

    print(f"\nConfig file: {config.config_file}")
