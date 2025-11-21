#!/usr/bin/env python3
"""
Unit tests for configuration module.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from src.utils.config import Config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config = Config(config_dir=self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test config initialization."""
        self.assertTrue(self.test_dir.exists())
        self.assertTrue(self.config.config_file.exists())

    def test_default_config_created(self):
        """Test that default config is created on first run."""
        self.assertTrue(self.config.config_file.exists())

        # Verify default values
        self.assertTrue(self.config.get('general.enabled'))
        self.assertEqual(self.config.get('general.timeout_seconds'), 30)

    def test_get_existing_key(self):
        """Test getting an existing configuration value."""
        value = self.config.get('general.enabled')
        self.assertIsNotNone(value)
        self.assertIsInstance(value, bool)

    def test_get_nonexistent_key_with_default(self):
        """Test getting a nonexistent key with default value."""
        value = self.config.get('nonexistent.key', 'default_value')
        self.assertEqual(value, 'default_value')

    def test_get_nested_key(self):
        """Test getting nested configuration values."""
        value = self.config.get('notifications.enabled')
        self.assertIsNotNone(value)
        self.assertIsInstance(value, bool)

    def test_set_value(self):
        """Test setting a configuration value."""
        result = self.config.set('general.enabled', False)
        self.assertTrue(result)

        # Verify value was set
        value = self.config.get('general.enabled')
        self.assertFalse(value)

    def test_set_nested_value(self):
        """Test setting a nested configuration value."""
        result = self.config.set('notifications.sound', True)
        self.assertTrue(result)

        value = self.config.get('notifications.sound')
        self.assertTrue(value)

    def test_set_new_section(self):
        """Test creating a new configuration section."""
        result = self.config.set('new_section.new_key', 'new_value')
        self.assertTrue(result)

        value = self.config.get('new_section.new_key')
        self.assertEqual(value, 'new_value')

    def test_save_and_load(self):
        """Test saving and loading configuration."""
        # Set some values
        self.config.set('general.timeout_seconds', 45)
        self.config.set('notifications.sound', True)

        # Create new config instance to load from file
        new_config = Config(config_dir=self.test_dir)

        # Verify values were persisted
        self.assertEqual(new_config.get('general.timeout_seconds'), 45)
        self.assertTrue(new_config.get('notifications.sound'))

    def test_is_enabled(self):
        """Test is_enabled helper method."""
        self.assertTrue(self.config.is_enabled())

        self.config.set_enabled(False)
        self.assertFalse(self.config.is_enabled())

    def test_set_enabled(self):
        """Test set_enabled helper method."""
        result = self.config.set_enabled(False)
        self.assertTrue(result)
        self.assertFalse(self.config.is_enabled())

        result = self.config.set_enabled(True)
        self.assertTrue(result)
        self.assertTrue(self.config.is_enabled())

    def test_get_timeout(self):
        """Test get_timeout helper method."""
        timeout = self.config.get_timeout()
        self.assertEqual(timeout, 30)

    def test_set_timeout(self):
        """Test set_timeout helper method."""
        result = self.config.set_timeout(60)
        self.assertTrue(result)
        self.assertEqual(self.config.get_timeout(), 60)

    def test_set_timeout_bounds(self):
        """Test that timeout is bounded between 10 and 300 seconds."""
        # Test minimum bound
        self.config.set_timeout(5)
        self.assertEqual(self.config.get_timeout(), 10)

        # Test maximum bound
        self.config.set_timeout(500)
        self.assertEqual(self.config.get_timeout(), 300)

        # Test valid value
        self.config.set_timeout(45)
        self.assertEqual(self.config.get_timeout(), 45)

    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        # Change some values
        self.config.set('general.timeout_seconds', 99)
        self.config.set('notifications.sound', True)

        # Reset to defaults
        result = self.config.reset_to_defaults()
        self.assertTrue(result)

        # Verify defaults are restored
        self.assertEqual(self.config.get('general.timeout_seconds'), 30)
        self.assertFalse(self.config.get('notifications.sound'))

    def test_export_config(self):
        """Test exporting configuration."""
        export_path = self.test_dir / "export.json"
        result = self.config.export_config(export_path)

        self.assertTrue(result)
        self.assertTrue(export_path.exists())

    def test_import_config(self):
        """Test importing configuration."""
        # Set some custom values
        self.config.set('general.timeout_seconds', 45)
        self.config.set('notifications.sound', True)

        # Export config
        export_path = self.test_dir / "export.json"
        self.config.export_config(export_path)

        # Create new config and import
        new_test_dir = Path(tempfile.mkdtemp())
        try:
            new_config = Config(config_dir=new_test_dir)
            result = new_config.import_config(export_path)

            self.assertTrue(result)
            self.assertEqual(new_config.get('general.timeout_seconds'), 45)
            self.assertTrue(new_config.get('notifications.sound'))

        finally:
            shutil.rmtree(new_test_dir)

    def test_merge_with_defaults(self):
        """Test that loading incomplete config merges with defaults."""
        # Manually create a minimal config file
        import json

        minimal_config = {
            'general': {
                'enabled': False
            }
        }

        with open(self.config.config_file, 'w') as f:
            json.dump(minimal_config, f)

        # Load config
        new_config = Config(config_dir=self.test_dir)

        # Should have custom value
        self.assertFalse(new_config.get('general.enabled'))

        # Should have default values for missing keys
        self.assertEqual(new_config.get('general.timeout_seconds'), 30)
        self.assertTrue(new_config.get('notifications.enabled'))


if __name__ == '__main__':
    unittest.main()
