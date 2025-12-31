"""Read dropdown values using pywinauto UI Automation."""

from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError

from .config import APP_PROCESS_NAME, NAME_TO_CODE


class DropdownReader:
    """Read the selected value from a ComboBox control."""

    def __init__(self, hwnd: int):
        """Initialize with window handle.

        Args:
            hwnd: Window handle of the target application
        """
        self.hwnd = hwnd
        self._app = None
        self._window = None

    def connect(self) -> bool:
        """Connect to the application window.

        Returns:
            True if connection successful
        """
        try:
            # Connect using the window handle
            self._app = Application(backend="uia").connect(handle=self.hwnd)
            self._window = self._app.window(handle=self.hwnd)
            return True
        except Exception as e:
            print(f"Failed to connect to window: {e}")
            return False

    def get_selected_language(self) -> str | None:
        """Get the currently selected language name from the dropdown.

        Returns:
            The selected language display name (e.g., "Deutsch"), or None if not found
        """
        try:
            if not self._window:
                if not self.connect():
                    return None

            # Find the ComboBox control
            # In Windows Forms, ComboBox is typically identified by its control type
            combobox = self._window.child_window(control_type="ComboBox")

            # Get the selected item text
            # For a DropDownList style ComboBox, we can get the text from the Edit child
            # or directly from the ComboBox's selected item
            try:
                # Try to get the selected item text directly
                selected_text = combobox.selected_text()
                if selected_text:
                    return selected_text
            except AttributeError:
                pass

            # Alternative: get the window text which shows the selected value
            try:
                selected_text = combobox.window_text()
                if selected_text:
                    return selected_text
            except Exception:
                pass

            # Another alternative: try to get from legacy patterns
            try:
                selected_text = combobox.legacy_properties().get('Value', '')
                if selected_text:
                    return selected_text
            except Exception:
                pass

            return None

        except ElementNotFoundError:
            print("ComboBox not found in window")
            return None
        except Exception as e:
            print(f"Error reading dropdown: {e}")
            return None

    def get_language_code(self) -> str | None:
        """Get the language code for the currently selected language.

        Returns:
            The language code (e.g., "de" for "Deutsch"), or None if not found
        """
        display_name = self.get_selected_language()
        if display_name:
            # Look up the code from the display name
            code = NAME_TO_CODE.get(display_name)
            if code:
                return code
            # If exact match fails, try case-insensitive match
            for name, code in NAME_TO_CODE.items():
                if name.lower() == display_name.lower():
                    return code
        return None
