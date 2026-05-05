"""
Test suite for i18n key validation across templates and i18n.js.
Ensures every i18n key referenced in HTML templates exists in i18n.js,
and checks for unused keys that may indicate dead code or typos.
"""

import re
from pathlib import Path


def _extract_locale_dicts(js_content: str) -> dict[str, dict[str, str]]:
    """
    Parse window.VM_I18N object from JavaScript file.
    Uses brace-counting to extract locale blocks robustly.

    Returns a dict of locale -> dict of key -> value.
    """
    match = re.search(r'window\.VM_I18N\s*=\s*\{', js_content)
    if not match:
        raise ValueError("Could not find window.VM_I18N declaration")

    start_brace = match.end() - 1
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
    locales_out = {}
    locale_pattern = r'(\w{2,5})\s*:\s*\{'

    for locale_match in re.finditer(locale_pattern, body):
        locale_name = locale_match.group(1)
        locale_brace_pos = locale_match.end() - 1

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
        pairs = {}

        # Match key: value pairs. Handles both single and double quotes.
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


def _collect_template_keys() -> dict[str, list[tuple[str, int]]]:
    """
    Collect all i18n keys from HTML templates.
    Returns a dict of key -> list of (file_path, line_number) tuples.
    """
    templates_dir = Path(__file__).parent.parent / 'dashboard' / 'templates'
    if not templates_dir.exists():
        raise FileNotFoundError(f"Templates directory not found at {templates_dir}")

    keys_by_file = {}
    template_pattern = r'data-i18n(?:-html|-placeholder)?\s*=\s*["\']([^"\']+)["\']'

    for html_file in templates_dir.glob('*.html'):
        content = html_file.read_text(encoding='utf-8')
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for match in re.finditer(template_pattern, line):
                key = match.group(1)
                if key not in keys_by_file:
                    keys_by_file[key] = []
                keys_by_file[key].append((html_file.name, line_num))

    return keys_by_file


def _collect_js_keys() -> set[str]:
    """
    Collect all i18n keys referenced in JavaScript files via T() function calls.
    Looks for patterns like T('key') or T("key").
    """
    js_dir = Path(__file__).parent.parent / 'dashboard' / 'static' / 'js'
    if not js_dir.exists():
        raise FileNotFoundError(f"JS directory not found at {js_dir}")

    keys = set()
    # Match T('key') or T("key") patterns
    js_pattern = r'\bT\s*\(\s*["\']([^"\']+)["\']\s*\)'

    for js_file in js_dir.glob('*.js'):
        content = js_file.read_text(encoding='utf-8')
        for match in re.finditer(js_pattern, content):
            key = match.group(1)
            keys.add(key)

    return keys


class TestTemplateI18nKeys:
    """Test suite for i18n key validation in templates."""

    @classmethod
    def setup_class(cls):
        """Load i18n data and template keys once for all tests."""
        cls.locales = _load_i18n_js()
        cls.en_keys = set(cls.locales['en'].keys())
        cls.template_keys = _collect_template_keys()
        cls.js_keys = _collect_js_keys()
        cls.all_used_keys = set(cls.template_keys.keys()) | cls.js_keys

    def test_every_template_key_exists_in_en(self):
        """
        Verify that every data-i18n* key in templates exists in the English locale.
        Report missing keys with file:line locations.
        """
        missing_keys = {}

        for key, locations in self.template_keys.items():
            if key not in self.en_keys:
                missing_keys[key] = locations

        if missing_keys:
            error_lines = []
            for key in sorted(missing_keys.keys()):
                locations = missing_keys[key]
                for filename, line_num in locations:
                    error_lines.append(f"  {key}: {filename}:{line_num}")

            pytest.fail(
                f"Found {len(missing_keys)} i18n keys in templates that don't exist in en locale:\n"
                + "\n".join(error_lines)
            )

    def test_keys_used_in_js_exist_in_i18n(self):
        """
        Verify that every T('key') call in JavaScript files references a key that exists in en locale.
        """
        missing_keys = {}

        for key in self.js_keys:
            if key not in self.en_keys:
                missing_keys[key] = True

        if missing_keys:
            error_lines = [f"  {key}" for key in sorted(missing_keys.keys())]
            pytest.fail(
                f"Found {len(missing_keys)} i18n keys in JS that don't exist in en locale:\n"
                + "\n".join(error_lines)
            )

    def test_no_unused_keys_in_i18n_js(self):
        """
        Report (informational) all keys defined in English that are NOT used anywhere
        (neither in templates nor in JS files). This identifies potential dead code.
        Actual unused keys are reported but don't fail the test.
        """
        unused_keys = self.en_keys - self.all_used_keys

        if unused_keys:
            # This is informational. We print but don't fail, as some keys might be
            # set programmatically in ways we don't detect (e.g., dynamically in JS).
            print(f"\nINFO: {len(unused_keys)} keys defined in en but not referenced in templates or JS:")
            for key in sorted(unused_keys):
                print(f"  {key}")


def test_template_key_summary():
    """Print summary statistics about template keys."""
    locales = _load_i18n_js()
    en_keys = set(locales['en'].keys())
    template_keys = _collect_template_keys()
    js_keys = _collect_js_keys()
    all_used = set(template_keys.keys()) | js_keys

    print(f"\n=== i18n Key Summary ===")
    print(f"Total keys in en locale: {len(en_keys)}")
    print(f"Keys in templates: {len(template_keys)}")
    print(f"Keys in JS (via T()): {len(js_keys)}")
    print(f"Unique keys used (templates + JS): {len(all_used)}")
    print(f"Unused keys: {len(en_keys - all_used)}")

    # Show a few examples of each category for diagnostics
    missing_in_en = set(template_keys.keys()) - en_keys
    if missing_in_en:
        print(f"\nMissing in en (templates reference but not defined):")
        for key in sorted(list(missing_in_en)[:5]):
            print(f"  {key}")
        if len(missing_in_en) > 5:
            print(f"  ... and {len(missing_in_en) - 5} more")

    unused = en_keys - all_used
    if unused:
        print(f"\nUnused in en (defined but not referenced):")
        for key in sorted(list(unused)[:5]):
            print(f"  {key}")
        if len(unused) > 5:
            print(f"  ... and {len(unused) - 5} more")


# pytest import for use in test functions
try:
    import pytest
except ImportError:
    # Provide a minimal pytest.fail replacement if pytest not imported yet
    class pytest:
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)
