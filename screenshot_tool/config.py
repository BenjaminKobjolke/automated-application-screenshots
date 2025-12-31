"""Configuration for the screenshot tool."""

# Target application settings
APP_PROCESS_NAME = "KeyboardLayoutWatcher.exe"
APP_TITLE_SUBSTRING = "Keyboard Layout Watcher"

# Dropdown position relative to window top-left corner
# The language dropdown is at Location(100, yPos) with Size(150, 24)
# yPos is approximately 248 based on form layout
DROPDOWN_RELATIVE_POS = (175, 248)  # Center of dropdown

# Language codes in the order they appear in the dropdown (alphabetical by code)
LANGUAGE_CODES = [
    "ar",  # العربية (Arabic)
    "bg",  # Български (Bulgarian)
    "bn",  # বাংলা (Bengali)
    "cs",  # Čeština (Czech)
    "da",  # Dansk (Danish)
    "de",  # Deutsch (German)
    "en",  # English
    "es",  # Español (Spanish)
    "et",  # Eesti (Estonian)
    "fa",  # فارسی (Persian)
    "fi",  # Suomi (Finnish)
    "fr",  # Français (French)
    "he",  # עברית (Hebrew)
    "hi",  # हिन्दी (Hindi)
    "hr",  # Hrvatski (Croatian)
    "hu",  # Magyar (Hungarian)
    "it",  # Italiano (Italian)
    "ja",  # 日本語 (Japanese)
    "ko",  # 한국어 (Korean)
    "lt",  # Lietuvių (Lithuanian)
    "lv",  # Latviešu (Latvian)
    "ml",  # മലയാളം (Malayalam)
    "mr",  # मराठी (Marathi)
    "nl",  # Nederlands (Dutch)
    "no",  # Norsk (Norwegian)
    "pl",  # Polski (Polish)
    "pt",  # Português (Portuguese)
    "ro",  # Română (Romanian)
    "ru",  # Русский (Russian)
    "sk",  # Slovenčina (Slovak)
    "sl",  # Slovenščina (Slovenian)
    "sr",  # Српски (Serbian)
    "sv",  # Svenska (Swedish)
    "ta",  # தமிழ் (Tamil)
    "te",  # తెలుగు (Telugu)
    "th",  # ไทย (Thai)
    "tr",  # Türkçe (Turkish)
    "uk",  # Українська (Ukrainian)
    "ur",  # اردو (Urdu)
    "vi",  # Tiếng Việt (Vietnamese)
    "zh",  # 中文 (Chinese)
]

# Language names for display
LANGUAGE_NAMES = {
    "ar": "العربية",
    "bg": "Български",
    "bn": "বাংলা",
    "cs": "Čeština",
    "da": "Dansk",
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "et": "Eesti",
    "fa": "فارسی",
    "fi": "Suomi",
    "fr": "Français",
    "he": "עברית",
    "hi": "हिन्दी",
    "hr": "Hrvatski",
    "hu": "Magyar",
    "it": "Italiano",
    "ja": "日本語",
    "ko": "한국어",
    "lt": "Lietuvių",
    "lv": "Latviešu",
    "ml": "മലയാളം",
    "mr": "मराठी",
    "nl": "Nederlands",
    "no": "Norsk",
    "pl": "Polski",
    "pt": "Português",
    "ro": "Română",
    "ru": "Русский",
    "sk": "Slovenčina",
    "sl": "Slovenščina",
    "sr": "Српски",
    "sv": "Svenska",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "th": "ไทย",
    "tr": "Türkçe",
    "uk": "Українська",
    "ur": "اردو",
    "vi": "Tiếng Việt",
    "zh": "中文",
}

# Reverse lookup: display name -> language code
NAME_TO_CODE = {name: code for code, name in LANGUAGE_NAMES.items()}

# Output settings
DEFAULT_OUTPUT_DIR = "screenshots"
SCREENSHOT_FILENAME = "screenshot.png"  # Filename within each language subfolder

# Timing settings
DELAY_AFTER_CHANGE = 0.3  # Seconds to wait after language change for UI refresh
