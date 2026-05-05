"""
Test suite for i18n.js translation parity.
Verifies that all required translations exist, are complete, and match expected language coverage.
"""

import json
import re
from pathlib import Path


def _extract_locale_dicts(js_content: str) -> dict[str, dict[str, str]]:
    """
    Parse window.VM_I18N object from JavaScript file.
    Uses a more robust regex-based extraction that handles quotes inside values.

    Returns a dict of locale -> dict of key -> value.
    """
    # Find the start of window.VM_I18N
    match = re.search(r'window\.VM_I18N\s*=\s*\{', js_content)
    if not match:
        raise ValueError("Could not find window.VM_I18N declaration")

    # Find the opening brace
    start_brace = match.end() - 1  # Position of the '{'

    # Count braces to find the matching closing brace
    depth = 0
    end_pos = start_brace
    for i in range(start_brace, len(js_content)):
        if js_content[i] == '{':
            depth += 1
        elif js_content[i] == '}':
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    body = js_content[start_brace:end_pos]

    # Extract each locale block (en:, ko:, zh:, ja:)
    locales_out = {}

    # Pattern to find "en: {", "ko: {", etc.
    locale_pattern = r'(\w{2,5})\s*:\s*\{'

    for locale_match in re.finditer(locale_pattern, body):
        locale_name = locale_match.group(1)
        # Start searching from the brace after the locale name
        locale_brace_pos = locale_match.end() - 1

        # Find the matching closing brace for this locale
        depth = 0
        locale_end_pos = locale_brace_pos
        for i in range(locale_brace_pos, len(body)):
            if body[i] == '{':
                depth += 1
            elif body[i] == '}':
                depth -= 1
                if depth == 0:
                    locale_end_pos = i
                    break

        locale_body = body[locale_brace_pos + 1:locale_end_pos]

        # Extract key: value pairs from this locale
        # Pattern handles both single and double quotes, including escaped quotes
        # Using a more permissive pattern that allows any characters inside quotes
        pairs = {}

        # Pattern explanation:
        # (['"])         - Opening quote (capture group 1)
        # ((?:(?!\1).)*) - Content that doesn't contain the opening quote (non-greedy, use negative lookahead)
        # \1             - Same quote as opening
        # \s*:\s*        - Colon separator
        # (['"])         - Opening quote for value (capture group 2)
        # ((?:(?!\2).)*) - Content for value (non-greedy)
        # \2             - Same quote as value opening

        # Simpler approach: match key and value with different quote types
        kv_pattern = r"(['\"])([^'\"]*?)\1\s*:\s*(['\"])(.*?)\3"

        for kv_match in re.finditer(kv_pattern, locale_body, re.DOTALL):
            key = kv_match.group(2)
            value = kv_match.group(4)
            pairs[key] = value

        locales_out[locale_name] = pairs

    return locales_out


def _load_i18n_js() -> dict[str, dict[str, str]]:
    """Load and parse the i18n.js file."""
    i18n_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'js' / 'i18n.js'

    if not i18n_path.exists():
        raise FileNotFoundError(f"i18n.js not found at {i18n_path}")

    content = i18n_path.read_text(encoding='utf-8')
    return _extract_locale_dicts(content)


class TestI18nParity:
    """Test suite for i18n.js translation parity."""

    @classmethod
    def setup_class(cls):
        """Load i18n data once for all tests."""
        cls.locales = _load_i18n_js()

    def test_all_locales_present(self):
        """Verify that all required locales are present."""
        required_locales = {'en', 'ko', 'zh', 'ja'}
        found_locales = set(self.locales.keys())

        assert required_locales == found_locales, \
            f"Expected locales {required_locales}, but found {found_locales}"

    def test_ko_has_all_en_keys(self):
        """Verify that Korean has all English keys."""
        en_keys = set(self.locales['en'].keys())
        ko_keys = set(self.locales['ko'].keys())

        missing = en_keys - ko_keys
        if missing:
            pytest.fail(f"Korean (ko) is missing {len(missing)} keys from English: {sorted(missing)}")

    def test_zh_has_all_en_keys(self):
        """Verify that Chinese has all English keys."""
        en_keys = set(self.locales['en'].keys())
        zh_keys = set(self.locales['zh'].keys())

        missing = en_keys - zh_keys
        if missing:
            pytest.fail(f"Chinese (zh) is missing {len(missing)} keys from English: {sorted(missing)}")

    def test_ja_has_all_en_keys(self):
        """Verify that Japanese has all English keys."""
        en_keys = set(self.locales['en'].keys())
        ja_keys = set(self.locales['ja'].keys())

        missing = en_keys - ja_keys
        if missing:
            pytest.fail(f"Japanese (ja) is missing {len(missing)} keys from English: {sorted(missing)}")

    def test_no_empty_translations(self):
        """Verify that no locale has empty or None translations."""
        for locale_name, pairs in self.locales.items():
            empty_keys = []
            for key, value in pairs.items():
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    empty_keys.append(key)

            if empty_keys:
                pytest.fail(f"{locale_name} has {len(empty_keys)} empty values: {sorted(empty_keys)}")

    def test_no_orphan_keys_in_locales(self):
        """Verify that non-English locales have no keys absent from English."""
        en_keys = set(self.locales['en'].keys())

        for locale_name in ['ko', 'zh', 'ja']:
            locale_keys = set(self.locales[locale_name].keys())
            orphans = locale_keys - en_keys

            if orphans:
                pytest.fail(f"{locale_name} has {len(orphans)} orphan keys not in English: {sorted(orphans)}")

    def test_critical_keys_translated(self):
        """
        Verify that critical P0 keys are actually translated.
        Checks that non-English locales have different values from English for key terms.
        """
        critical_keys = [
            'connect', 'login', 'setup', 'gen.running',
            'twitter.post', 'reddit.post', 'gitmail.template',
            'cta.first.title'
        ]

        failures = {}

        for key in critical_keys:
            en_value = self.locales['en'].get(key)
            if not en_value:
                continue

            for locale_name in ['ko', 'zh', 'ja']:
                locale_value = self.locales[locale_name].get(key)

                # Check if the locale value is genuinely different from English
                # (i.e., it's not just the English value copied over)
                if locale_value == en_value:
                    if key not in failures:
                        failures[key] = []
                    failures[key].append(locale_name)

        if failures:
            failure_msg = []
            for key, locales in sorted(failures.items()):
                failure_msg.append(f"  {key}: not translated in {', '.join(locales)}")

            pytest.fail(
                f"Critical keys are not properly translated:\n" + "\n".join(failure_msg)
            )


def test_en_key_count():
    """Report the number of English keys found."""
    locales = _load_i18n_js()
    en_keys = len(locales['en'])
    print(f"\nEnglish key count: {en_keys}")
    assert en_keys > 0, "No English keys found"


def test_locale_coverage_summary():
    """Print a summary of translation coverage."""
    locales = _load_i18n_js()
    en_keys = set(locales['en'].keys())

    summary_lines = ["\nTranslation coverage summary:"]
    summary_lines.append(f"  English (en): {len(locales['en'])} keys")

    for locale in ['ko', 'zh', 'ja']:
        if locale in locales:
            locale_keys = set(locales[locale].keys())
            coverage = len(locale_keys & en_keys)
            total = len(en_keys)
            pct = (coverage / total * 100) if total > 0 else 0
            summary_lines.append(f"  {locale.upper()}: {coverage}/{total} keys ({pct:.1f}%)")
        else:
            summary_lines.append(f"  {locale.upper()}: MISSING")

    print("\n".join(summary_lines))


# pytest import for use in test functions
try:
    import pytest
except ImportError:
    # Provide a minimal pytest.fail replacement if pytest not imported yet
    class pytest:
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)
