#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Generates the Paani patch series from a post-Helium Chromium tree.

The input tree must already have the Helium and the Windows patch series
applied, because the Paani patches sit on top of them.  Every rule is checked
against the tree, so a stale rule fails loudly instead of silently producing a
patch that does not apply.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# The module is imported by the watcher script as well, so the arguments are
# optional and the paths fall back to the environment.
TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(
    os.environ.get('PAANI_TREE', '.'))
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(
    os.environ.get('PAANI_OUT', '.'))

FAILURES = []


class Rule:
    """One textual replacement.

    count is the exact number of expected hits, or None when only "at least
    one" is known.  The actual count is always reported, so a rule that fires
    an unexpected number of times shows up in the output.
    """

    def __init__(self, pattern, replacement, count=1, regex=False):
        self.pattern = pattern
        self.replacement = replacement
        self.count = count
        self.regex = regex

    def apply(self, text, where):
        if self.regex:
            new_text, hits = re.subn(self.pattern, self.replacement, text)
        else:
            hits = text.count(self.pattern)
            new_text = text.replace(self.pattern, self.replacement)
        if self.count is None:
            if hits < 1:
                FAILURES.append('%s: %r matched 0 times, expected at least 1'
                                % (where, self.pattern))
        elif hits != self.count:
            FAILURES.append('%s: %r matched %d times, expected %d' %
                            (where, self.pattern, hits, self.count))
        else:
            print('  ok  %s | %-56s x%d' % (where, self.pattern[:56], hits))
        return new_text


class Move:
    """Moves one file to a new path, with optional content edits.

    The patch contains three diffs: the edit of the old file, the deletion of
    the old file and the creation of the new one.  A unified diff cannot
    express a rename on its own, and this form is unambiguous for patch.
    """

    def __init__(self, old_path, new_path, rules=None):
        self.old_path = old_path
        self.new_path = new_path
        self.rules = rules or []


def clsid_rule(label, data1, data2, data3, data4):
    """Replaces a Windows CLSID initializer, keeping the original layout."""
    pattern = (r'(\.' + label + r' = \{)0x[0-9A-Fa-f]+,(\s*)0x[0-9A-Fa-f]+,'
               r'(\s*)0x[0-9A-Fa-f]+,(\s*)\{([^}]*)\}')
    body = ', '.join('0x%02X' % b for b in data4)
    replacement = (r'\g<1>0x%08X,\g<2>0x%04X,\g<3>0x%04X,\g<4>{%s}' %
                   (data1, data2, data3, body))
    return Rule(pattern, replacement, count=1, regex=True)


# ---------------------------------------------------------------------------
# Paani GUIDs.  They are freshly generated for Paani; the Helium ones are not
# reused, so the two browsers never share a registry identity.
# ---------------------------------------------------------------------------
PAANI_APP_GUID = 'E08B87F7-9AF2-4B0E-B705-89EF7FAD4B87'
PAANI_TOAST_CLSID = (0x2C6A9E4B, 0x1F73, 0x4B58,
                     (0x9A, 0x21, 0x7D, 0x0E, 0x5C, 0x8B, 0x3A, 0x64))
PAANI_ELEVATOR_CLSID = (0x7F3B1D08, 0x52A6, 0x4E19,
                        (0x8C, 0x74, 0x0B, 0x6D, 0x2A, 0x9F, 0x5E, 0x13))
PAANI_ELEVATOR_IID = (0x9A4E2C15, 0x7B63, 0x4D80,
                      (0xA2, 0xF1, 0x3C, 0x58, 0xE6, 0xD7, 0x0B, 0x92))


# ---------------------------------------------------------------------------
# Patch 1: branding
# ---------------------------------------------------------------------------
BRANDING = {
    'chrome/install_static/chromium_install_modes.h': [
        Rule('inline constexpr wchar_t kCompanyPathName[] = L"imput";',
             'inline constexpr wchar_t kCompanyPathName[] = L"";'),
        Rule('inline constexpr wchar_t kProductPathName[] = L"Helium";',
             'inline constexpr wchar_t kProductPathName[] = L"Paani";'),
        Rule('inline constexpr char kSafeBrowsingName[] = "helium";',
             'inline constexpr char kSafeBrowsingName[] = "paani";'),
        Rule('L"{FB68A146-637A-48C2-A0C4-1565DE45FEBD}"',
             'L"{%s}"' % PAANI_APP_GUID, count=2),
        Rule('.base_app_name = L"Helium",', '.base_app_name = L"Paani",'),
        Rule('.base_app_id = L"Helium",', '.base_app_id = L"Paani",'),
        Rule('.browser_prog_id_prefix = L"HeliumHTM",',
             '.browser_prog_id_prefix = L"PaaniHTM",'),
        Rule('L"Helium HTML Document",', 'L"Paani HTML Document",'),
        Rule('.direct_launch_url_scheme = "helium",',
             '.direct_launch_url_scheme = "paani",'),
        Rule('.pdf_prog_id_prefix = L"HeliumPDF",',
             '.pdf_prog_id_prefix = L"PaaniPDF",'),
        Rule('L"Helium PDF Document",', 'L"Paani PDF Document",'),
        clsid_rule('toast_activator_clsid', *PAANI_TOAST_CLSID),
        clsid_rule('elevator_clsid', *PAANI_ELEVATOR_CLSID),
        clsid_rule('elevator_iid', *PAANI_ELEVATOR_IID),
        Rule('// {C89A04FF-00C6-4966-94B2-5AFEC6FED93A}.',
             '// {9A4E2C15-7B63-4D80-A2F1-3C58E6D70B92}.'),
    ],
    'chrome/installer/mini_installer/mini_installer_constants.cc': [
        Rule('const wchar_t kChromeArchivePrefix[] = L"helium";',
             'const wchar_t kChromeArchivePrefix[] = L"paani";'),
    ],
    'chrome/installer/setup/installer_crash_reporter_client.cc': [
        Rule('L"SOFTWARE\\\\Policies\\\\Helium"',
             'L"SOFTWARE\\\\Policies\\\\Paani"'),
    ],
    'components/policy/tools/generate_policy_source.py': [
        Rule("CHROMIUM_POLICY_KEY = 'SOFTWARE\\\\\\\\Policies\\\\\\\\Helium'",
             "CHROMIUM_POLICY_KEY = 'SOFTWARE\\\\\\\\Policies\\\\\\\\Paani'"),
    ],
    'chrome/installer/setup/setup_constants.cc': [
        Rule('const wchar_t kChromeArchive[] = L"helium.7z";',
             'const wchar_t kChromeArchive[] = L"paani.7z";'),
        Rule('const wchar_t kChromeCompressedArchive[] = L"helium.packed.7z";',
             'const wchar_t kChromeCompressedArchive[] = L"paani.packed.7z";'),
        Rule('const wchar_t kInstallSourceChromeDir[] = L"Helium-bin";',
             'const wchar_t kInstallSourceChromeDir[] = L"Paani-bin";'),
    ],
    'chrome/installer/util/logging_installer.cc': [
        Rule('FILE_PATH_LITERAL("helium_installer.log")',
             'FILE_PATH_LITERAL("paani_installer.log")'),
    ],
    'chrome/installer/mini_installer/BUILD.gn': [
        Rule('"$root_out_dir/helium.7z"', '"$root_out_dir/paani.7z"'),
        Rule('"$root_out_dir/helium.packed.7z"',
             '"$root_out_dir/paani.packed.7z"'),
    ],
    'chrome/tools/build/win/create_installer_archive.py': [
        Rule('CHROME_DIR = "Helium-bin"', 'CHROME_DIR = "Paani-bin"'),
        Rule("default='helium'", "default='paani'"),
    ],
    'components/policy/tools/template_writers/writer_configuration.py': [
        Rule("'app_name': 'Helium',", "'app_name': 'Paani',"),
        Rule("'reg_mandatory_key_name': 'Software\\\\Policies\\\\Helium',",
             "'reg_mandatory_key_name': 'Software\\\\Policies\\\\Paani',"),
        Rule("'reg_recommended_key_name':\n"
             "                'Software\\\\Policies\\\\Helium\\\\Recommended',",
             "'reg_recommended_key_name':\n"
             "                'Software\\\\Policies\\\\Paani\\\\Recommended',"),
        Rule("'chromium': 'Helium',", "'chromium': 'Paani',"),
        Rule("'chromium_recommended': 'Helium - {doc_recommended}',",
             "'chromium_recommended': 'Paani - {doc_recommended}',"),
        Rule("'namespace': 'Chromium.Policies.Chromium',",
             "'namespace': 'Paani.Policies.Paani',"),
    ],
    'chrome/app/theme/chromium/BRANDING': [
        Rule('COMPANY_FULLNAME=The Helium Authors',
             'COMPANY_FULLNAME=The Paani Authors'),
        Rule('COMPANY_SHORTNAME=The Helium Authors',
             'COMPANY_SHORTNAME=The Paani Authors'),
        Rule('PRODUCT_FULLNAME=Helium\n', 'PRODUCT_FULLNAME=Paani\n'),
        Rule('PRODUCT_SHORTNAME=Helium\n', 'PRODUCT_SHORTNAME=Paani\n'),
        Rule('PRODUCT_INSTALLER_FULLNAME=Helium Installer',
             'PRODUCT_INSTALLER_FULLNAME=Paani Installer'),
        Rule('PRODUCT_INSTALLER_SHORTNAME=Helium Installer',
             'PRODUCT_INSTALLER_SHORTNAME=Paani Installer'),
        Rule('Copyright @LASTCHANGE_YEAR@ The Helium Authors.',
             'Copyright @LASTCHANGE_YEAR@ The Paani Authors.'),
        Rule('MAC_BUNDLE_ID=net.imput.helium', 'MAC_BUNDLE_ID=net.paani.browser'),
        Rule('MAC_TEAM_ID=S4Q33XPHB4', 'MAC_TEAM_ID='),
    ],
    'chrome/app/chrome_crash_reporter_client.cc': [
        Rule('const char* product_name = "Helium";',
             'const char* product_name = "Paani";'),
    ],
}


# ---------------------------------------------------------------------------
# Patch 2: the internal WebUI scheme
#
# Helium registers "helium://" next to Chromium's "chrome://" and rewrites
# navigations from one to the other, so the address bar shows helium:// while
# the WebUI itself is still served by the chrome:// data sources.  Paani does
# the same with "paani://".
# ---------------------------------------------------------------------------
SCHEME = {
    'content/public/common/url_constants.h': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
        Rule('"helium"', '"paani"'),
    ],
    'chrome/browser/profiles/profile_io_data.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'content/common/url_schemes.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', count=5, regex=True),
    ],
    'content/renderer/render_thread_impl.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
        Rule(r'\bhelium_scheme\b', 'paani_scheme', count=4, regex=True),
        Rule('// helium:', '// paani:'),
    ],
    'chrome/browser/history/history_utils.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'chrome/browser/ui/incognito_allowed_url.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'chrome/browser/ui/navigator/browser_navigator.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'chrome/browser/extensions/extension_tab_util.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'chrome/browser/ui/browser_web_contents_delegate/'
    'browser_web_contents_delegate.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'components/omnibox/browser/omnibox_text_util.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'components/url_formatter/url_formatter.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'components/url_formatter/url_fixer.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', count=8, regex=True),
        Rule('"helium"', '"paani"'),
    ],
    'chrome/browser/autocomplete/chrome_autocomplete_provider_client.cc': [
        Rule(r'\bkHeliumUIScheme\b', 'kPaaniUIScheme', regex=True),
    ],
    'components/omnibox/browser/builtin_provider.cc': [
        Rule('u"helium"', 'u"paani"'),
    ],
    'chrome/browser/resources/tab_search/tab_search_item.ts': [
        Rule("'helium:'", "'paani:'"),
        Rule("'helium://'", "'paani://'"),
    ],
}


# ---------------------------------------------------------------------------
# Patch 3: version numbers
# ---------------------------------------------------------------------------
VERSIONING = {
    'build/apple/tweak_info_plist.py': [
        Rule('@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@'),
    ],
    'base/version_info/version_info_values.h.version': [
        Rule('#define HELIUM_PRODUCT_VERSION "@HELIUM_MAJOR@.@HELIUM_MINOR@.'
             '@HELIUM_PATCH@.@HELIUM_PLATFORM@"',
             '#define PAANI_PRODUCT_VERSION "@PAANI_MAJOR@.@PAANI_MINOR@.'
             '@PAANI_PATCH@.@PAANI_PLATFORM@"'),
    ],
    'base/version_info/version_info.h': [
        Rule('GetHeliumVersionNumber()', 'GetPaaniVersionNumber()'),
        Rule('return HELIUM_PRODUCT_VERSION;', 'return PAANI_PRODUCT_VERSION;'),
    ],
    'chrome/browser/ui/webui/version/version_ui.cc': [
        Rule('version_ui::kHeliumVersion', 'version_ui::kPaaniVersion'),
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()', count=2),
    ],
    'components/webui/version/version_ui_constants.cc': [
        Rule('const char kHeliumVersion[] = "helium_version";',
             'const char kPaaniVersion[] = "paani_version";'),
    ],
    'components/webui/version/version_ui_constants.h': [
        Rule('extern const char kHeliumVersion[];',
             'extern const char kPaaniVersion[];'),
    ],
    'components/webui/version/resources/about_version.html': [
        Rule('$i18n{helium_version}', '$i18n{paani_version}'),
        Rule('copy-content-helium', 'copy-content-paani'),
        Rule('copy-to-clipboard-helium', 'copy-to-clipboard-paani'),
    ],
    'components/webui/version/resources/about_version.ts': [
        Rule('copyHeliumVersionToClipboard', 'copyPaaniVersionToClipboard',
             count=2),
        Rule("'copy-content-helium'", "'copy-content-paani'"),
        Rule("'copy-to-clipboard-helium'", "'copy-to-clipboard-paani'"),
    ],
    'chrome/app/chrome_main_delegate.cc': [
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()', count=2),
    ],
    'chrome/app/chrome_crash_reporter_client.cc': [
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()'),
    ],
    'components/crash/core/app/crashpad_win.cc': [
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()'),
    ],
    'components/crash/core/app/crashpad_mac.mm': [
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()'),
    ],
    'chrome/app/chrome_version.rc.version': [
        Rule('@HELIUM_MAJOR@,@HELIUM_MINOR@,@HELIUM_PATCH@,@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@,@PAANI_MINOR@,@PAANI_PATCH@,@PAANI_PLATFORM@'),
        Rule('@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@'),
    ],
    'chrome/app/main_dll_loader_win.cc': [
        Rule('chrome::kHeliumVersion', 'chrome::kPaaniVersion'),
    ],
    'chrome/app/version_assembly/BUILD.gn': [
        Rule('$helium_version_full.manifest', '$paani_version_full.manifest'),
    ],
    'chrome/app/version_assembly/chrome_exe_manifest.template': [
        Rule('@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@',
             count=2),
    ],
    'chrome/app/version_assembly/version_assembly_manifest.template': [
        Rule('@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@',
             count=2),
    ],
    'chrome/browser/chrome_content_browser_client.cc': [
        Rule('chrome::kHeliumVersion', 'chrome::kPaaniVersion'),
    ],
    'chrome/browser/web_applications/chrome_pwa_launcher/'
    'chrome_pwa_launcher_util.cc': [
        Rule('chrome::kHeliumVersion', 'chrome::kPaaniVersion'),
    ],
    'chrome/common/chrome_constants.cc': [
        Rule('const char kHeliumVersion[] = HELIUM_VERSION_STRING;',
             'const char kPaaniVersion[] = PAANI_VERSION_STRING;'),
    ],
    'chrome/common/chrome_constants.h': [
        Rule('extern const char kHeliumVersion[];',
             'extern const char kPaaniVersion[];'),
    ],
    'chrome/common/chrome_version.h.in': [
        Rule('#define HELIUM_VERSION_STRING \\\n'
             '  "@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@"',
             '#define PAANI_VERSION_STRING \\\n'
             '  "@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@"'),
    ],
    'chrome/installer/mini_installer/mini_installer_exe_version.rc.version': [
        Rule('@HELIUM_MAJOR@,@HELIUM_MINOR@,@HELIUM_PATCH@,@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@,@PAANI_MINOR@,@PAANI_PATCH@,@PAANI_PLATFORM@'),
        Rule('@HELIUM_MAJOR@.@HELIUM_MINOR@.@HELIUM_PATCH@.@HELIUM_PLATFORM@',
             '@PAANI_MAJOR@.@PAANI_MINOR@.@PAANI_PATCH@.@PAANI_PLATFORM@'),
    ],
    'chrome/installer/setup/install_worker.cc': [
        Rule('version_info::GetHeliumVersionNumber()',
             'version_info::GetPaaniVersionNumber()', count=2),
    ],
    'chrome/installer/setup/setup_main.cc': [
        Rule('chrome::kHeliumVersion', 'chrome::kPaaniVersion'),
        Rule('IsHeliumVersionSchemeMigration', 'IsPaaniVersionSchemeMigration'),
        Rule('is_helium_version_migration', 'is_paani_version_migration',
             count=2),
    ],
    'chrome/installer/setup/setup_util.cc': [
        Rule('IsHeliumVersionSchemeMigration', 'IsPaaniVersionSchemeMigration',
             count=3),
        Rule('// the Helium version-scheme migration (not a real downgrade).',
             '// the Paani version-scheme migration (not a real downgrade).'),
    ],
    'chrome/installer/setup/setup_util.h': [
        Rule('IsHeliumVersionSchemeMigration', 'IsPaaniVersionSchemeMigration'),
    ],
    'chrome/installer/setup/install.cc': [
        Rule('IsHeliumVersionSchemeMigration', 'IsPaaniVersionSchemeMigration'),
    ],
    'chrome/tools/build/win/create_installer_archive.py': [
        Rule("values.get('HELIUM_MAJOR', '0')", "values.get('PAANI_MAJOR', '0')"),
        Rule("values.get('HELIUM_MINOR', '0')", "values.get('PAANI_MINOR', '0')"),
        Rule("values.get('HELIUM_PATCH', '0')", "values.get('PAANI_PATCH', '0')"),
        Rule("values.get('HELIUM_PLATFORM', '0')",
             "values.get('PAANI_PLATFORM', '0')"),
    ],
    'chrome/version.gni': [
        Rule(r'"helium_full = \"@HELIUM_MAJOR@.@HELIUM_MINOR@"',
             r'"paani_full = \"@PAANI_MAJOR@.@PAANI_MINOR@"'),
        Rule(r'".@HELIUM_PATCH@.@HELIUM_PLATFORM@\" "',
             r'".@PAANI_PATCH@.@PAANI_PLATFORM@\" "'),
        Rule('helium_version_full = _result.helium_full',
             'paani_version_full = _result.paani_full'),
    ],
    'chrome/installer/setup/last_breaking_installer_version.cc': [
        Rule('// Helium uses its own version scheme, which is below every '
             'Chromium\n// "breaking installer version".',
             '// Paani uses its own version scheme, which is below every '
             'Chromium\n// "breaking installer version".'),
    ],
}


# ---------------------------------------------------------------------------
# Patch 4: the remaining Helium identifiers
# ---------------------------------------------------------------------------
BRAND_RENAME = {
    'chrome/common/webui_url_constants.h': [
        Rule('kHeliumSetupHost', 'kPaaniSetupHost'),
        Rule('kHeliumSetupURL', 'kPaaniSetupURL'),
    ],
    'chrome/common/webui_url_constants.cc': [
        Rule('kHeliumSetupHost', 'kPaaniSetupHost'),
    ],
    'chrome/browser/ui/webui/onboarding/onboarding_page_ui.cc': [
        Rule('chrome::kHeliumSetupHost', 'chrome::kPaaniSetupHost'),
    ],
    'chrome/browser/ui/webui/onboarding/onboarding_page_ui.h': [
        Rule('chrome::kHeliumSetupHost', 'chrome::kPaaniSetupHost'),
    ],
    'chrome/browser/ui/incognito_allowed_url.cc': [
        Rule('chrome::kHeliumSetupHost', 'chrome::kPaaniSetupHost'),
    ],
}


# ---------------------------------------------------------------------------
# Patch 5: the Paani binary names
#
# Chromium ships chrome.exe, chrome.dll and chrome_proxy.exe, and Helium kept
# those names, so the Paani build has to carry the Paani name down to the
# file names: the taskbar entry, the Start menu shortcut, the installer
# manifest and the update helper all address the executable by name.
#
# The helper binaries keep their names on purpose.  chrome_elf.dll,
# chrome_child.dll, chrome_renderer.dll, chrome_wer.dll and
# chrome_pwa_launcher.exe are loaded by the loader or by the sandbox, and
# their names are part of the Chromium contract; renaming them buys nothing
# and would break the helper process lookup.
# ---------------------------------------------------------------------------
BINARY_RENAME = {
    'chrome/BUILD.gn': [
        Rule('_chrome_output_name = "chrome"',
             '_chrome_output_name = "paani"'),
        Rule('    output_name = "chrome"\n',
             '    output_name = "paani"\n'),
        Rule('"$root_out_dir/chrome.dll.pdb"',
             '"$root_out_dir/paani.dll.pdb"'),
    ],
    'chrome/common/chrome_constants.cc': [
        Rule('FPL("chrome.exe")', 'FPL("paani.exe")', count=4),
    ],
    'chrome/common/chrome_constants.h': [
        Rule('FILE_PATH_LITERAL("chrome.dll")',
             'FILE_PATH_LITERAL("paani.dll")'),
    ],
    'chrome/installer/util/util_constants.h': [
        Rule('kChromeDll[] = L"chrome.dll"', 'kChromeDll[] = L"paani.dll"'),
        Rule('kChromeExe[] = L"chrome.exe"', 'kChromeExe[] = L"paani.exe"'),
        Rule('kChromeNewExe[] = L"new_chrome.exe"',
             'kChromeNewExe[] = L"new_paani.exe"'),
        Rule('kChromeOldExe[] = L"old_chrome.exe"',
             'kChromeOldExe[] = L"old_paani.exe"'),
        Rule('kChromeProxyExe[] = L"chrome_proxy.exe"',
             'kChromeProxyExe[] = L"paani_proxy.exe"'),
        Rule('kChromeProxyNewExe[] = L"new_chrome_proxy.exe"',
             'kChromeProxyNewExe[] = L"new_paani_proxy.exe"'),
        Rule('kChromeProxyOldExe[] = L"old_chrome_proxy.exe"',
             'kChromeProxyOldExe[] = L"old_paani_proxy.exe"'),
    ],
    'chrome/chrome_proxy/BUILD.gn': [
        Rule('executable("chrome_proxy") {\n  deps = [',
             'executable("chrome_proxy") {\n'
             '  output_name = "paani_proxy"\n\n'
             '  deps = ['),
    ],
    'chrome/chrome_proxy/chrome_proxy_main_win.cc': [
        Rule('FILE_PATH_LITERAL("chrome.exe")',
             'FILE_PATH_LITERAL("paani.exe")'),
        Rule('FILE_PATH_LITERAL("chrome_proxy.exe")',
             'FILE_PATH_LITERAL("paani_proxy.exe")'),
    ],
    'chrome/chrome_proxy/chrome_proxy.ver': [
        Rule('INTERNAL_NAME=chrome_proxy\n', 'INTERNAL_NAME=paani_proxy\n'),
        Rule('ORIGINAL_FILENAME=chrome_proxy.exe',
             'ORIGINAL_FILENAME=paani_proxy.exe'),
    ],
    'chrome/installer/launcher_support/chrome_launcher_support.cc': [
        Rule('const wchar_t kChromeExe[] = L"chrome.exe";',
             'const wchar_t kChromeExe[] = L"paani.exe";'),
    ],
    'chrome/installer/helium_update_helper/update_installer.cc': [
        Rule('FILE_PATH_LITERAL("chrome.exe")',
             'FILE_PATH_LITERAL("paani.exe")'),
    ],
    'chrome/installer/mini_installer/BUILD.gn': [
        Rule('"$root_out_dir/chrome.dll"', '"$root_out_dir/paani.dll"'),
        Rule('"$root_out_dir/chrome.exe"', '"$root_out_dir/paani.exe"'),
    ],
    'chrome/installer/mini_installer/chrome.release': [
        Rule('chrome.exe: %(ChromeDir)s\\', 'paani.exe: %(ChromeDir)s\\'),
        Rule('chrome_proxy.exe: %(ChromeDir)s\\',
             'paani_proxy.exe: %(ChromeDir)s\\'),
        Rule('chrome.dll: %(VersionDir)s\\', 'paani.dll: %(VersionDir)s\\'),
    ],
    'chrome/app/chrome_exe.ver': [
        Rule('ORIGINAL_FILENAME=chrome.exe', 'ORIGINAL_FILENAME=paani.exe'),
        Rule('INTERNAL_NAME=chrome_exe', 'INTERNAL_NAME=paani_exe'),
    ],
    'chrome/app/chrome_dll.ver': [
        Rule('ORIGINAL_FILENAME=chrome.dll', 'ORIGINAL_FILENAME=paani.dll'),
        Rule('INTERNAL_NAME=chrome_dll', 'INTERNAL_NAME=paani_dll'),
    ],
    'chrome/app/chrome_exe.vsprops': [
        Rule('OutputFile="$(OutDir)\\chrome.exe"',
             'OutputFile="$(OutDir)\\paani.exe"'),
    ],
    'build/win/reorder-imports.py': [
        Rule('chrome.exe', 'paani.exe', count=6),
    ],
    'chrome/tools/build/win/FILES.cfg': [
        Rule("'chrome.exe'", "'paani.exe'"),
        Rule("'chrome.exe.pdb'", "'paani.exe.pdb'"),
        Rule("'chrome.dll'", "'paani.dll'"),
        Rule("'chrome.dll.pdb'", "'paani.dll.pdb'"),
        Rule("'chrome_proxy.exe'", "'paani_proxy.exe'"),
        Rule("'chrome_proxy.exe.pdb'", "'paani_proxy.exe.pdb'"),
    ],
    'chrome/tools/build/win/create_installer_archive.py': [
        Rule("'Chrome-bin/*/chrome.dll'", "'Paani-bin/*/paani.dll'"),
        Rule("'Chrome-bin', '*', 'chrome.dll'",
             "'Paani-bin', '*', 'paani.dll'"),
    ],
    'chrome/browser/profiles/profile_shortcut_manager_win.cc': [
        Rule('const int kCurrentProfileIconVersion = 10;',
             'const int kCurrentProfileIconVersion = 11;'),
    ],
}


# ---------------------------------------------------------------------------
# Patch 6: the native window materials
#
# Chromium already asks the DWM for the Windows 11 backdrop, but the browser
# chrome paints an opaque frame on top of it, so the backdrop never shows
# through.  This patch lets the chrome stay unpainted where the native
# material is used and keeps the window itself opaque, because the DWM only
# applies the backdrop to a window that has no redirection bitmap and that is
# not translucent.
#
# The window is only made translucent on macOS.  A translucent window disables
# the DWM backdrop on Windows, so doing that would remove the very effect
# this patch is after.
# ---------------------------------------------------------------------------
NATIVE_FRAME = {
    'chrome/browser/ui/ui_features.h': [
        Rule('BASE_DECLARE_FEATURE(kHeliumNativeFrameMaterials);\n'
             'bool HeliumNativeFrameAvailable();',
             'BASE_DECLARE_FEATURE(kPaaniNativeFrameMaterials);\n'
             'bool PaaniNativeFrameAvailable();\n'
             '\n'
             '// Returns true when the running system is able to render the\n'
             '// browser chrome with native window materials.\n'
             'bool PaaniNativeFrameMaterialsSupported();'),
    ],
    'chrome/browser/ui/ui_features.cc': [
        Rule('#include "extensions/buildflags/buildflags.h"\n'
             '#include "ui/base/ui_base_features.h"\n',
             '#include "extensions/buildflags/buildflags.h"\n'
             '#include "ui/base/ui_base_features.h"\n'
             '\n'
             '#if BUILDFLAG(IS_WIN)\n'
             '#include "base/win/windows_version.h"\n'
             '#endif  // BUILDFLAG(IS_WIN)\n'),
        Rule('BASE_FEATURE(kHeliumNativeFrameMaterials, '
             'base::FEATURE_DISABLED_BY_DEFAULT);',
             '#if BUILDFLAG(IS_WIN)\n'
             'BASE_FEATURE(kPaaniNativeFrameMaterials, '
             'base::FEATURE_ENABLED_BY_DEFAULT);\n'
             '#else\n'
             'BASE_FEATURE(kPaaniNativeFrameMaterials, '
             'base::FEATURE_DISABLED_BY_DEFAULT);\n'
             '#endif  // BUILDFLAG(IS_WIN)'),
        Rule('bool HeliumNativeFrameAvailable() {\n'
             '#if BUILDFLAG(IS_MAC)\n'
             '  return base::FeatureList::IsEnabled(kHeliumNativeFrameMaterials);\n'
             '#else\n'
             '  return false;\n'
             '#endif\n'
             '}',
             'bool PaaniNativeFrameAvailable() {\n'
             '#if BUILDFLAG(IS_MAC) || BUILDFLAG(IS_WIN)\n'
             '  return base::FeatureList::IsEnabled(kPaaniNativeFrameMaterials);\n'
             '#else\n'
             '  return false;\n'
             '#endif\n'
             '}\n'
             '\n'
             'bool PaaniNativeFrameMaterialsSupported() {\n'
             '#if BUILDFLAG(IS_WIN)\n'
             '  // The system backdrop needs Windows 11 22H2 or newer.\n'
             '  return base::win::GetVersion() >= base::win::Version::WIN11_22H2;\n'
             '#else\n'
             '  return true;\n'
             '#endif\n'
             '}'),
    ],
    'chrome/common/pref_names.h': [
        Rule('inline constexpr char kHeliumNativeFrameMaterials[] =\n'
             '    "helium.browser.native_frame_materials";',
             'inline constexpr char kPaaniNativeFrameMaterials[] =\n'
             '    "paani.browser.native_frame_materials";'),
    ],
    'chrome/browser/ui/browser_ui_prefs.cc': [
        Rule('registry->RegisterBooleanPref(prefs::kHeliumNativeFrameMaterials, '
             'false);',
             'registry->RegisterBooleanPref(prefs::kPaaniNativeFrameMaterials, '
             'true);'),
    ],
    'chrome/browser/extensions/api/settings_private/prefs_util.cc': [
        Rule('(*s_allowlist)[::prefs::kHeliumNativeFrameMaterials] =',
             '(*s_allowlist)[::prefs::kPaaniNativeFrameMaterials] ='),
    ],
    'chrome/browser/ui/webui/settings/settings_localized_strings_provider.cc': [
        Rule('  html_source->AddBoolean("showNativeFrameMaterialsOption",\n'
             '                          features::HeliumNativeFrameAvailable());',
             '  html_source->AddBoolean("showNativeFrameMaterialsOption",\n'
             '                          features::PaaniNativeFrameAvailable() &&\n'
             '                              features::'
             'PaaniNativeFrameMaterialsSupported());'),
    ],
    'chrome/browser/resources/settings/appearance_page/appearance_page.html.ts': [
        Rule('pref-key="helium.browser.native_frame_materials"',
             'pref-key="paani.browser.native_frame_materials"'),
    ],
    'chrome/app/settings_strings.grdp': [
        Rule(r'(?m)^(\s*)Use native frame materials \(experimental\)\r?$',
             r'\g<1>Use native window materials', regex=True),
        Rule(r'(?m)^(\s*)Applies native materials to the browser frame surfaces\. '
             r'May cause UI clarity issues\.\r?$',
             r'\g<1>Draws the browser frame with the native Windows 11 backdrop. '
             r'Web pages stay opaque. Falls back to a solid background when '
             r'Windows reduces transparency or forces high contrast.',
             regex=True),
    ],
    'chrome/browser/ui/views/frame/browser_widget.cc': [
        Rule('  if (features::HeliumNativeFrameAvailable()) {\n'
             '    params.opacity = views::Widget::InitParams::WindowOpacity::'
             'kTranslucent;\n'
             '  }',
             '#if BUILDFLAG(IS_MAC)\n'
             '  // macOS composites the browser frame with the native materials,\n'
             '  // which needs a translucent window.  Windows applies the\n'
             '  // backdrop to an opaque window through the DWM, so the window\n'
             '  // has to stay opaque there.\n'
             '  if (features::PaaniNativeFrameAvailable()) {\n'
             '    params.opacity = views::Widget::InitParams::WindowOpacity::'
             'kTranslucent;\n'
             '  }\n'
             '#endif  // BUILDFLAG(IS_MAC)'),
    ],
    'chrome/browser/ui/views/frame/browser_frame_view_win.cc': [
        Rule('#include "chrome/browser/ui/views/frame/tab_strip_region_view.h"\n'
             '#include "chrome/browser/ui/views/tabs/new_tab_button.h"',
             '#include "chrome/browser/ui/views/frame/tab_strip_region_view.h"\n'
             '#include "chrome/browser/ui/views/helium/native_frame_materials.h"\n'
             '#include "chrome/browser/ui/views/tabs/new_tab_button.h"'),
        Rule('void BrowserFrameViewWin::PaintTitlebar(gfx::Canvas* canvas) '
             'const {\n'
             '  TRACE_EVENT0("views.frame", '
             '"BrowserFrameViewWin::PaintTitlebar");\n',
             'void BrowserFrameViewWin::PaintTitlebar(gfx::Canvas* canvas) '
             'const {\n'
             '  TRACE_EVENT0("views.frame", '
             '"BrowserFrameViewWin::PaintTitlebar");\n'
             '\n'
             '  // The native backdrop is drawn by the DWM behind the client\n'
             '  // area, so the titlebar must not be painted opaquely on top\n'
             '  // of it.\n'
             '  if (helium::ShouldUseNativeFrameMaterials(GetBrowserView())) {\n'
             '    return;\n'
             '  }\n'),
    ],
    'chrome/browser/ui/views/helium/native_frame_materials.cc': [
        Rule('#include "components/prefs/pref_service.h"\n'
             '#include "ui/views/view.h"',
             '#include "components/prefs/pref_service.h"\n'
             '#if BUILDFLAG(IS_WIN)\n'
             '#include "ui/native_theme/os_settings_provider.h"\n'
             '#endif  // BUILDFLAG(IS_WIN)\n'
             '#include "ui/views/view.h"'),
        Rule('bool ShouldUseNativeFrameMaterials(const BrowserView* browser_view) '
             '{\n'
             '#if BUILDFLAG(IS_MAC)\n'
             '  if (!features::HeliumNativeFrameAvailable() || !browser_view) {\n'
             '    return false;\n'
             '  }\n'
             '\n'
             '  // Web app windows use their app-defined frame appearance.\n'
             '  if (browser_view->GetIsWebAppType()) {\n'
             '    return false;\n'
             '  }\n'
             '\n'
             '  const Profile* profile = browser_view->GetProfile();\n'
             '  return profile &&\n'
             '         profile->GetPrefs()->GetBoolean('
             'prefs::kHeliumNativeFrameMaterials);\n'
             '#else\n'
             '  return false;\n'
             '#endif\n'
             '}',
             'bool ShouldUseNativeFrameMaterials(const BrowserView* browser_view) '
             '{\n'
             '#if BUILDFLAG(IS_MAC) || BUILDFLAG(IS_WIN)\n'
             '  if (!features::PaaniNativeFrameAvailable() || !browser_view) {\n'
             '    return false;\n'
             '  }\n'
             '\n'
             '  // Web app windows use their app-defined frame appearance.\n'
             '  if (browser_view->GetIsWebAppType()) {\n'
             '    return false;\n'
             '  }\n'
             '\n'
             '#if BUILDFLAG(IS_WIN)\n'
             '  // Windows asks for a solid background when the user turned\n'
             '  // transparency off or when the system is in a forced colors\n'
             '  // mode.\n'
             '  const ui::OsSettingsProvider& os_settings = '
             'ui::OsSettingsProvider::Get();\n'
             '  if (os_settings.PrefersReducedTransparency() ||\n'
             '      os_settings.ForcedColorsActive()) {\n'
             '    return false;\n'
             '  }\n'
             '#endif  // BUILDFLAG(IS_WIN)\n'
             '\n'
             '  const Profile* profile = browser_view->GetProfile();\n'
             '  return profile &&\n'
             '         profile->GetPrefs()->GetBoolean('
             'prefs::kPaaniNativeFrameMaterials);\n'
             '#else\n'
             '  return false;\n'
             '#endif\n'
             '}'),
    ],
    'chrome/browser/ui/views/frame/browser_native_widget_mac.mm': [
        Rule('      prefs::kHeliumNativeFrameMaterials,',
             '      prefs::kPaaniNativeFrameMaterials,'),
    ],
    'chrome/browser/helium_flag_choices.h': [
        Rule('constexpr const char kHeliumNativeFrameMaterialsCommandLine[] =\n'
             '    "helium-native-frame-materials";',
             'constexpr const char kPaaniNativeFrameMaterialsCommandLine[] =\n'
             '    "paani-native-frame-materials";'),
    ],
    'chrome/browser/helium_flag_entries.h': [
        Rule('    {helium::kHeliumNativeFrameMaterialsCommandLine, '
             '"Native frame materials",\n'
             '     "Enables an option to apply native materials to the browser '
             'frame "\n'
             '     "surfaces. May cause UI clarity issues. Helium flag.",\n'
             '     kOsMac, '
             'FEATURE_VALUE_TYPE(features::kHeliumNativeFrameMaterials)},',
             '    {helium::kPaaniNativeFrameMaterialsCommandLine, '
             '"Native frame materials",\n'
             '     "Enables an option to apply native materials to the browser '
             'frame "\n'
             '     "surfaces. May cause UI clarity issues. Paani flag.",\n'
             '     kOsMac | kOsWin, '
             'FEATURE_VALUE_TYPE(features::kPaaniNativeFrameMaterials)},'),
    ],
}


# ---------------------------------------------------------------------------
# Patch 6: the Paani mark in the WebUI
#
# The "chrome-product" symbol is the Chromium logo that the WebUI pages draw.
# Helium replaced it with its own mark, so the Paani build replaces it with
# the Paani mark.  The mark is the white droplet of the application icon,
# scaled into the 56x56 box that the symbol uses.
# ---------------------------------------------------------------------------
HELIUM_WEBUI_MARK = (
    'M33.3232 52.0297L28 56L22.6768 52.0297L25.0958 33.0855L10.0649 44.6731L4 42'
    'L4.74054 35.3577L22.1898 28L4.74054 20.6423L4 14L10.0649 11.3269L25.0958 '
    '22.9145L22.6768 3.97031L28 0L33.3232 3.97031L30.9042 22.9145L45.9351 '
    '11.3269L52 14L51.2595 20.6423L33.8102 28L51.2595 35.3577L52 42L45.9351 '
    '44.6731L30.9042 33.0855L33.3232 52.0297Z')

PAANI_WEBUI_MARK = (
    'M 28 4 C 27.294 27.294 4.706 30.824 4.706 47.765 Q 28 56.235 '
    '51.294 47.765 C 51.294 30.824 28.706 27.294 28 4 Z')

WEBUI_LOGO = {
    'ui/webui/resources/cr_elements/icons.html.ts': [
        Rule('<path d="%s"/>' % HELIUM_WEBUI_MARK,
             '<path d="%s"/>' % PAANI_WEBUI_MARK,
             count=2),
    ],
}


# ---------------------------------------------------------------------------
# Patch 7: the Paani mark in the onboarding
#
# The onboarding page is a separate web application that is built by vite.  It
# draws the Helium mark from the "@imput/helium-prism" package, so the Paani
# build ships its own mark instead.  The privacy and terms links pointed at
# the upstream project; a personal build has no such documents, so the note
# states what the build actually is instead of linking away.
# ---------------------------------------------------------------------------
PAANI_LOGO_COMPONENT = '''<script lang="ts">
    import type { ClassValue } from "svelte/elements";

    type Props = {
        height?: string;
        class?: ClassValue;
    };

    let {
        height = "28px",
        class: className,
    }: Props = $props();
</script>

<span class={["paani-logo", className]} style:height aria-hidden="true">
    <svg
        width="56"
        height="56"
        viewBox="0 0 56 56"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
    >
        <path
            d="M 28 4 C 27.294 27.294 4.706 30.824 4.706 47.765 Q 28 56.235 51.294 47.765 C 51.294 30.824 28.706 27.294 28 4 Z"
            fill="currentColor"
        />
    </svg>
</span>

<style>
    .paani-logo {
        display: inline-flex;
        color: currentColor;
        flex: 0 0 auto;
        width: auto;
    }

    .paani-logo :global(svg) {
        display: block;
        width: auto;
        height: 100%;
    }
</style>
'''

PAANI_ICON = '''<svg width="256" height="256" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="paani" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="256">
      <stop offset="0" stop-color="#35C5D8"/>
      <stop offset="1" stop-color="#0B5F92"/>
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="67" fill="url(#paani)"/>
  <path d="M 128 26 C 126 92 62 102 62 150 Q 128 174 194 150 C 194 102 130 92 128 26 Z" fill="#FFFFFF"/>
</svg>
'''

ONBOARDING_BRAND = {
    'components/helium_onboarding/index.html': [
        Rule('<title>Helium Setup</title>', '<title>Paani Setup</title>'),
    ],
    'components/helium_onboarding/helium_onboarding_strings.grdp': [
        Rule('  By continuing, you agree to the <ph name="BEGIN_LINK_PRIVACY">$1'
             '</ph>privacy policy<ph name="END_LINK_PRIVACY">$2</ph> and <ph '
             'name="BEGIN_LINK_TERMS">$3</ph>terms of use<ph '
             'name="END_LINK_TERMS">$4</ph>.\n',
             '  This is a personal build of Paani. It sends no telemetry and no '
             'usage data, and the pages you visit are only contacted when you '
             'ask for them.\n'),
    ],
    'components/helium_onboarding/src/pages/Welcome.svelte': [
        Rule('    import {\n'
             '        Button,\n'
             '        HeliumLogo,\n'
             '        IconArrowRight,\n'
             '        IconCheck,\n'
             '        Link,\n'
             '    } from "@imput/helium-prism";\n',
             '    import {\n'
             '        Button,\n'
             '        IconArrowRight,\n'
             '        IconCheck,\n'
             '    } from "@imput/helium-prism";\n'
             '    import PaaniLogo from "../components/PaaniLogo.svelte";\n'),
        Rule('    import { parseLocalizedString } from "../lib/i18n";\n', ''),
        Rule('    const privacyUrl = "https://helium.computer/privacy";\n'
             '    const termsUrl = "https://helium.computer/terms";\n', ''),
        Rule('    const termsParts = parseLocalizedString(s.welcome.terms);\n',
             ''),
        Rule('<HeliumLogo height="84px" />', '<PaaniLogo height="84px" />'),
        Rule('<HeliumLogo height="48px" />', '<PaaniLogo height="48px" />'),
        Rule('                <p>\n'
             '                    {#each termsParts as part}\n'
             '                        {#if part.kind === "linkPrivacy"}\n'
             '                            <Link href={privacyUrl}>{part.text}</Link>\n'
             '                        {:else if part.kind === "linkTerms"}\n'
             '                            <Link href={termsUrl}>{part.text}</Link>\n'
             '                        {:else}\n'
             '                            {part.text}\n'
             '                        {/if}\n'
             '                    {/each}\n'
             '                </p>\n',
             '                <p>{s.welcome.terms}</p>\n'),
    ],
    'components/helium_onboarding/src/pages/Finish.svelte': [
        Rule('    import {\n'
             '        Button,\n'
             '        HeliumLogo,\n'
             '        IconArrowLeft,\n'
             '        IconCheck,\n'
             '    } from "@imput/helium-prism";\n',
             '    import {\n'
             '        Button,\n'
             '        IconArrowLeft,\n'
             '        IconCheck,\n'
             '    } from "@imput/helium-prism";\n'
             '    import PaaniLogo from "../components/PaaniLogo.svelte";\n'),
        Rule('<HeliumLogo height="64px" />', '<PaaniLogo height="64px" />'),
    ],
    'components/helium_onboarding/src/pages/HeliumServices.svelte': [
        Rule('    import { CardLink, HeliumLogo } from "@imput/helium-prism";\n',
             '    import { CardLink } from "@imput/helium-prism";\n'
             '    import PaaniLogo from "../components/PaaniLogo.svelte";\n'),
        Rule('            Icon={HeliumLogo}\n', '            Icon={PaaniLogo}\n'),
    ],
    'components/helium_onboarding/src/components/BrowserImportGraphic.svelte': [
        Rule('    import { browserIcons } from "../lib/nonfree-icons";\n'
             '    import { platform } from "../lib/platform";\n',
             '    import { browserIcons } from "../lib/nonfree-icons";\n'
             '    import { platform } from "../lib/platform";\n'
             '    import paaniIcon from "../icons/paani.svg";\n'),
        Rule('            class="browser-icon helium-icon"\n'
             '            src={browserIcons.helium}\n',
             '            class="browser-icon paani-icon"\n'
             '            src={paaniIcon}\n'),
        Rule('    .helium-icon {\n', '    .paani-icon {\n'),
    ],
}


# ---------------------------------------------------------------------------
# There is deliberately no toolchain patch.
#
# An earlier revision of this generator emitted patches/toolchain/windows/
# paani-windows-sdk.patch, which made SDK_VERSION in build/vs_toolchain.py and
# build/toolchain/win/setup_toolchain.py overridable and lowered NTDDI_VERSION
# to NTDDI_WIN10_NI so that Chromium could be built against the 10.0.22621 SDK.
# That was the wrong fix and it is kept out on purpose: crypto/ really does
# call KeyCredentialStatus_AlgorithmNotSupported, which 10.0.22621 does not
# declare, and 10.0.22621 predates the WINCRYPT_USE_SYMBOL_PREFIX guard in
# wincrypt.h, so its X509_NAME macros collide with BoringSSL's openssl/base.h.
# The machine is expected to provide the SDK that upstream pins instead, which
# keeps build/ and base/ pristine for the next upstream update.  build.py
# checks for it and names the missing component.  See README.md.
# ---------------------------------------------------------------------------


PATCH_FILES = [
    ('windows/change-branding.patch',
     'Renames the Helium brand to Paani in the install paths, the registry\n'
     'keys, the policy templates and the Windows version resources.\n',
     BRANDING),
    ('windows/paani-scheme.patch',
     'Renames the internal WebUI scheme from helium:// to paani://.\n',
     SCHEME),
    ('windows/paani-versioning.patch',
     'Reports the Paani version instead of the Helium version.\n',
     VERSIONING),
    ('windows/paani-brand-rename.patch',
     'Renames the remaining Helium identifiers to Paani.\n',
     BRAND_RENAME),
    ('windows/paani-binary-rename.patch',
     'Renames the browser binaries from chrome.exe, chrome.dll and\n'
     'chrome_proxy.exe to paani.exe, paani.dll and paani_proxy.exe.\n',
     BINARY_RENAME),
    ('windows/paani-native-frame.patch',
     'Draws the browser chrome with the native window materials of the\n'
     'running system.\n',
     NATIVE_FRAME),
    ('windows/paani-webui-logo.patch',
     'Draws the Paani mark where the WebUI pages draw the browser logo.\n',
     WEBUI_LOGO),
    ('windows/paani-onboarding-brand.patch',
     'Draws the Paani mark in the onboarding page.\n',
     ONBOARDING_BRAND,
     {
         'components/helium_onboarding/src/components/PaaniLogo.svelte':
             PAANI_LOGO_COMPONENT,
         'components/helium_onboarding/src/icons/paani.svg': PAANI_ICON,
     }),
]


def referenced_paths():
    """Returns every source file that the rules touch."""
    paths = set()
    for entry in PATCH_FILES:
        paths.update(entry[2].keys())
        for path in (entry[3] if len(entry) > 3 and entry[3] else {}):
            paths.add(path)
    return sorted(paths)


def report_residual(text, path):
    """Prints the Helium tokens that survive in a rewritten file."""
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r'helium', line, re.IGNORECASE):
            print('  !! %s:%d: %s' % (path, number, line.strip()[:100]))


def unified_diff(old_label, new_label, before, after, tmp, where=''):
    """Returns the unified diff between two file contents."""
    before_path = Path(tmp) / 'before'
    after_path = Path(tmp) / 'after'
    before_path.write_text(before, encoding='utf-8', newline='')
    after_path.write_text(after, encoding='utf-8', newline='')
    proc = subprocess.run(
        ['diff', '-u', '--label', old_label, '--label', new_label,
         str(before_path), str(after_path)],
        capture_output=True, text=True, errors='replace')
    if proc.returncode not in (0, 1):
        FAILURES.append('diff failed for %s: %s' % (where or old_label,
                                                    proc.stderr))
        return None
    return proc.stdout


def build_move(move, overlay, tmp):
    """Returns the diffs that move one file to another path."""
    src = TREE / move.old_path
    if move.old_path not in overlay and not src.exists():
        FAILURES.append('missing source file: %s' % move.old_path)
        return None
    if move.new_path in overlay or (TREE / move.new_path).exists():
        FAILURES.append('move target already exists: %s' % move.new_path)
        return None
    if move.old_path in overlay:
        text = overlay[move.old_path]
    else:
        text = src.read_text(encoding='utf-8', newline='')
    new_text = text
    for rule in move.rules:
        new_text = rule.apply(new_text, move.old_path)
    report_residual(new_text, move.new_path)

    chunks = []
    edit = unified_diff('a/' + move.old_path, 'b/' + move.old_path, text,
                        new_text, tmp, move.old_path)
    if edit:
        chunks.append(edit)
    delete = unified_diff('a/' + move.old_path, '/dev/null', new_text, '',
                          tmp, move.old_path)
    if delete:
        chunks.append(delete)
    create = unified_diff('/dev/null', 'b/' + move.new_path, '', new_text,
                           tmp, move.new_path)
    if create:
        chunks.append(create)
    overlay.pop(move.old_path, None)
    overlay[move.new_path] = new_text
    return ''.join(chunks)


def build_patch(rel_path, rules, new_files=None, overlay=None):
    """Returns the unified diff for one patch file, or None if nothing changed.

    The overlay holds the contents that the earlier patches of the same series
    produced.  Two patches of one series can touch the same file, and the
    second one has to be generated against the state that the first one left
    behind, otherwise its context does not match the tree anymore.
    """
    chunks = []
    overlay = overlay if overlay is not None else {}
    with tempfile.TemporaryDirectory() as tmp:
        for path, path_rules in rules.items():
            if isinstance(path_rules, Move):
                chunk = build_move(path_rules, overlay, tmp)
                if chunk:
                    chunks.append(chunk)
                continue
            src = TREE / path
            if not src.exists():
                FAILURES.append('missing source file: %s' % path)
                continue
            if path in overlay:
                text = overlay[path]
            else:
                text = src.read_text(encoding='utf-8', newline='')
            new_text = text
            for rule in path_rules:
                new_text = rule.apply(new_text, path)
            report_residual(new_text, path)
            if new_text == text:
                continue
            chunk = unified_diff('a/' + path, 'b/' + path, text, new_text, tmp,
                                 path)
            if chunk:
                chunks.append(chunk)
            overlay[path] = new_text

        for path, content in (new_files or {}).items():
            if path in overlay or (TREE / path).exists():
                FAILURES.append('new file already exists: %s' % path)
                continue
            chunk = unified_diff('/dev/null', 'b/' + path, '', content, tmp,
                                 path)
            if chunk:
                chunks.append(chunk)
            overlay[path] = content

    if not chunks:
        return None
    return ''.join(chunks)


def emit(entries, out_dir):
    """Writes the patches of one series and the series file next to them."""
    out_dir = Path(out_dir)
    names = []
    overlay = {}
    for entry in entries:
        rel_path, header, rules = entry[0], entry[1], entry[2]
        new_files = entry[3] if len(entry) > 3 else None
        body = build_patch(rel_path, rules, new_files, overlay)
        if body is None:
            FAILURES.append('patch %s is empty' % rel_path)
            continue
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(header + body, encoding='utf-8', newline='')
        print('wrote %s' % dest)
        names.append(rel_path)
    series = out_dir / 'series'
    if not names:
        # The rules did not match, so no patch was written.  The series file of
        # a directory that already holds a valid patch must not be emptied.
        print('wrote no patch into %s, kept the existing series' % out_dir)
        return
    series.parent.mkdir(parents=True, exist_ok=True)
    series.write_text('\n'.join(names) + '\n', encoding='utf-8', newline='\n')
    print('wrote %s' % series)


def main():
    emit(PATCH_FILES, OUT)

    if FAILURES:
        print('\nFAILURES (%d):' % len(FAILURES))
        for failure in FAILURES:
            print('  ' + failure)
        return 1
    print('\nall rules matched')
    return 0


if __name__ == '__main__':
    sys.exit(main())
