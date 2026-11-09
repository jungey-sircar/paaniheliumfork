"""Points Chromium's Visual Studio detection at the real installation.

build/vs_toolchain.py looks for Visual Studio 2022 and newer under
"%ProgramFiles%", but the 2022 build tools install into
"%ProgramFiles(x86)%".  Without vs2022_install the build aborts with
"No supported Visual Studio can be found".
"""
import pathlib

BUILD_PY = pathlib.Path('E:/eric/PaaniBrowserChromiumFork/paani-windows/build.py')

HELPER = '''

def _get_visual_studio_path():
    """
    Returns the installation path of the newest Visual Studio.

    Chromium's vs_toolchain.py only looks for Visual Studio 2022 and newer
    under "%ProgramFiles%", but the 2022 build tools install into
    "%ProgramFiles(x86)%".  The vs2022_install variable tells the build
    system where the installation actually is.
    """
    vswhere_exe = '%ProgramFiles(x86)%\\\\Microsoft Visual Studio\\\\Installer\\\\vswhere.exe'
    result = subprocess.run(
        '"{}" -products * -prerelease -latest -property installationPath'.format(vswhere_exe),
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True)
    installation_path = Path(result.stdout.strip())
    if not installation_path.exists():
        raise RuntimeError(
            'Visual Studio installation not found: {}'.format(installation_path))
    return installation_path
'''

REPLACEMENTS = [
    (
        "    vcvars_path = Path(result.stdout.strip(), 'VC/Auxiliary/Build/vcvars{}.bat'.format(name))",
        "    vcvars_path = Path(result.stdout.strip(), 'VC/Auxiliary/Build/vcvars{}.bat'.format(name))",
    ),
    (
        "    cmd_input = ['call \"%s\" >nul' % _get_vcvars_path()]\n"
        "    cmd_input.append('set DEPOT_TOOLS_WIN_TOOLCHAIN=0')\n"
        "    cmd_input.append(' '.join(map('\"{}\"'.format, args)))\n"
        "    cmd_input.append('exit\\n')\n"
        "    subprocess.run(('cmd.exe', '/k'),",
        "    cmd_input = ['call \"%s\" >nul' % _get_vcvars_path()]\n"
        "    cmd_input.append('set DEPOT_TOOLS_WIN_TOOLCHAIN=0')\n"
        "    cmd_input.append('set \"vs2022_install=%s\"' % _get_visual_studio_path())\n"
        "    cmd_input.append('set \"GYP_MSVS_OVERRIDE_PATH=%s\"' % _get_visual_studio_path())\n"
        "    cmd_input.append(' '.join(map('\"{}\"'.format, args)))\n"
        "    cmd_input.append('exit\\n')\n"
        "    subprocess.run(('cmd.exe', '/k'),",
    ),
    (
        "    cmd_input = ['call \"%s\" >nul' % _get_vcvars_path()]\n"
        "    cmd_input.append('set DEPOT_TOOLS_WIN_TOOLCHAIN=0')\n"
        "    cmd_input.append(' '.join(map('\"{}\"'.format, args)))\n"
        "    cmd_input.append('exit\\n')\n"
        "    with subprocess.Popen(('cmd.exe', '/k'), encoding=ENCODING,",
        "    cmd_input = ['call \"%s\" >nul' % _get_vcvars_path()]\n"
        "    cmd_input.append('set DEPOT_TOOLS_WIN_TOOLCHAIN=0')\n"
        "    cmd_input.append('set \"vs2022_install=%s\"' % _get_visual_studio_path())\n"
        "    cmd_input.append('set \"GYP_MSVS_OVERRIDE_PATH=%s\"' % _get_visual_studio_path())\n"
        "    cmd_input.append(' '.join(map('\"{}\"'.format, args)))\n"
        "    cmd_input.append('exit\\n')\n"
        "    with subprocess.Popen(('cmd.exe', '/k'), encoding=ENCODING,",
    ),
]


def main():
    raw = BUILD_PY.read_bytes()
    crlf = b'\r\n' in raw
    text = raw.decode('utf-8')
    if crlf:
        text = text.replace('\r\n', '\n')

    if '_get_visual_studio_path' not in text:
        anchor = "\n\ndef _run_build_process(*args, **kwargs):"
        assert anchor in text, 'anchor for the helper not found'
        text = text.replace(anchor, HELPER + anchor, 1)

    applied = 0
    for old, new in REPLACEMENTS:
        if old == new:
            continue
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
        elif new not in text:
            raise SystemExit('pattern not found:\n%s' % old)

    out = text.replace('\n', '\r\n') if crlf else text
    BUILD_PY.write_bytes(out.encode('utf-8'))
    print('build.py patched (%d replacements, crlf=%s)' % (applied, crlf))


if __name__ == '__main__':
    main()
