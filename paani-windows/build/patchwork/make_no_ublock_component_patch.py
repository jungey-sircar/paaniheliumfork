"""Records the removal of the uBlock Origin component extension as a quilt patch.

Paani blocks ads with its own filter engine, so the uBlock Origin component
extension that Helium installs is not installed in Paani either.  The filter
lists and the redirect stubs stay where they are, in resources.pak, where
Paani's engine reads them, so nothing is lost by not installing it.

The original text is recovered by reversing the replacement rather than by
copying the file aside, so the diff always contains exactly this hunk and
nothing another patch in the series already contributed.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-no-ublock-component.patch'

RELATIVE = 'chrome/browser/extensions/component_loader.cc'

OLD = (
    'void ComponentLoader::AddUBlock() {\n'
    '  Add(IDR_UBLOCK_MANIFEST_JSON, base::FilePath(FILE_PATH_LITERAL("ublock")));\n'
    '\n'
    '  using namespace extension_l10n_util;\n'
    '  ComponentExtensionInfo& info = component_extensions_.back();\n'
    '  std::string error;\n'
    '  bool localized = LocalizeExtension(info.root_directory, &info.manifest,\n'
    '                      GzippedMessagesPermission::kAllowForTrustedSource,\n'
    '                      &error, true);\n'
    '\n'
    '  if (!localized) {\n'
    '    LOG(ERROR) << "Failed to localize uBlock: " << error;\n'
    '  }\n'
    '}\n'
)

NEW = (
    'void ComponentLoader::AddUBlock() {\n'
    '  // Paani blocks ads with its own filter engine, so the uBlock Origin\n'
    '  // component extension is not installed. Its filter lists and its\n'
    '  // redirect stubs stay in resources.pak, where Paani\'s engine reads them.\n'
    '}\n'
)

DESCRIPTION = '''Does not install the uBlock Origin component extension.

Paani blocks ads with its own filter engine, so the uBlock Origin component
extension that Helium ships is not installed in Paani. The extension would be
a second blocker next to the first one, and its own popup would show a count
that has nothing to do with the one Paani shows. The filter lists and the
redirect stubs are pak resources, not extension files, so they stay available
and Paani's engine keeps reading them.
'''


def main():
    path = SOURCE / RELATIVE
    current = path.read_text(encoding='utf-8')

    # The tree is either pristine or already patched, and the replacement text
    # is not a substring of the original, so the state can be decided by
    # looking for either one.
    if NEW in current:
        original = current.replace(NEW, OLD, 1)
        updated = current
    elif OLD in current:
        original = current
        updated = current.replace(OLD, NEW, 1)
        path.write_text(updated, encoding='utf-8', newline='\n')
        print(f'{RELATIVE}: patched in the tree')
    else:
        raise SystemExit(f'{RELATIVE}: neither the original nor the patched '
                         'text is in the tree')

    diff = ''.join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile='a/' + RELATIVE,
        tofile='b/' + RELATIVE,
        n=3,
    ))
    if not diff:
        raise SystemExit(f'{RELATIVE}: produced no diff')

    PATCH.write_text(DESCRIPTION + diff, encoding='utf-8', newline='\n')
    print(f'patch written to {PATCH}')


if __name__ == '__main__':
    main()
