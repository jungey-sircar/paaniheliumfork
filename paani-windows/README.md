# Paani Browser (Windows)

Paani is a personal fork of [Helium](https://github.com/imputnet/helium) for
Windows 11: a translucent, ad-free browser with a built-in network-level
blocker on Brave's `adblock-rust` engine and a blocked-request counter at
`chrome://paani`. Everything Paani adds lives in this directory — the
`helium-chromium` submodule stays pristine, and Paani never contributes code
back to the imputnet repositories.

* [Phase 1 architecture and module map](../docs/PAANI-PHASE1-ARCHITECTURE.md)
* [Licensing, third-party notices and the upstream-update strategy](../docs/PAANI-LICENSING-AND-UPSTREAM.md)
* [Building, iterating and verifying Paani](../docs/PAANI-BUILD.md)

The upstream packaging instructions that Paani reuses are the ones below,
which are Helium's and remain accurate for the shared parts of the build.
This README keeps Helium's credits and licence notices intact on purpose.

---

# helium-windows

Windows packaging for [Helium](https://github.com/imputnet/helium).

## Credits

This repo is based on
[ungoogled-chromium-windows](https://github.com/ungoogled-software/ungoogled-chromium-windows),
but is pretty heavily modified for Helium. Huge shout-out to everyone behind ungoogled-chromium,
they made working with Chromium infinitely easier.

A huge thank you to [Depot](https://depot.dev/) for sponsoring our runners, which handle the Windows
builds of Helium. Their high-performance infrastructure lets us compile and package Helium at least
8 times faster than with GitHub-hosted runners, allowing us to release new builds within hours, not days.

## License
All code, patches, modified portions of imported code or patches, and
any other content that is unique to Helium and not imported from other
repositories is licensed under GPL-3.0. See [LICENSE](LICENSE).

Any content imported from other projects retains its original license (for
example, any original unmodified code imported from ungoogled-chromium remains
licensed under their [BSD 3-Clause license](LICENSE.ungoogled_chromium)).

## Building

#### Setting up Visual Studio

[Follow the "Visual Studio" section of the official Windows build instructions](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/windows_build_instructions.md#visual-studio).

* Make sure to read through the entire section and install/configure all the required components.
* Chromium 156 compiles `base/win/atl_throw.cc` unconditionally and that file includes `<atldef.h>`, so the
  **"C++ ATL for latest v143 build tools (x86 & x64)"** component (`Microsoft.VisualStudio.Component.VC.ATL`)
  has to be present. It is *not* part of the default Build Tools workload and the build fails with
  `fatal error: 'atldef.h' file not found` without it. Add it with:
	* `"C:\Program Files (x86)\Microsoft Visual Studio\Installer\setup.exe" modify --installPath "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools" --add Microsoft.VisualStudio.Component.VC.ATL --quiet --norestart`
* Chromium 156 pins the **Windows SDK 10.0.28000.0** (`build/vs_toolchain.py` refuses anything older, and
  `base/win/windows_version.cc` requires `NTDDI_WIN11_BR`). The older 10.0.22621 SDK is not a workable
  substitute: its headers really do lack APIs this version of Chromium calls, for example
  `crypto/user_verifying_key_win.cc` needs `KeyCredentialStatus_AlgorithmNotSupported`, and its
  `wincrypt.h` predates `WINCRYPT_USE_SYMBOL_PREFIX`, which is the only thing that keeps the
  `X509_NAME` macros of `wincrypt.h` from colliding with BoringSSL's `openssl/base.h`.
  10.0.22621 is also out of support since 2025-11-12. Install 10.0.28000 from
  <https://learn.microsoft.com/en-us/windows/apps/windows-sdk/downloads> and tick
  *Debugging Tools for Windows*, which `build/vs_toolchain.py` looks for.
  Paani deliberately carries **no** toolchain patch: the upstream build system is used as shipped.
* If your Visual Studio is installed in a directory other than the default, you'll need to set a few environment variables to point the toolchains to your installation path. (Copied from [instructions for Electron](https://electronjs.org/docs/development/build-instructions-windows))
	* `vs2019_install = DRIVE:\path\to\Microsoft Visual Studio\2019\Community` (replace `2019` and `Community` with your installed versions)
	* `WINDOWSSDKDIR = DRIVE:\path\to\Windows Kits\10`
	* `GYP_MSVS_VERSION = 2019` (replace 2019 with your installed version's year)

#### Other build requirements

**IMPORTANT**: Currently, the `MAX_PATH` path length restriction (which is 260 characters by default)
must be lifted in for our Python build scripts. This can be lifted in Windows 10 (v1607 or newer) with
the official installer for Python 3.6 or newer (you will see a button at the end of installation to do
this). See [Issue #345](https://github.com/ungoogled-software/ungoogled-chromium/issues/345) for other
methods for older Windows versions.

1. Setup the following:
    * 7-Zip
    * Windows Developer Mode enabled (for creating symbolic links).
    * Python 3.11 or above
		* Can be installed using WinGet or the Microsoft Store.
		* If you don't plan on using the Microsoft Store version of Python:
			* Check "Add python.exe to PATH" before install.
			* At the end of the Python installer, click the button to lift the `MAX_PATH` length restriction.
			* Disable the `python3.exe` and `python.exe` aliases in `Settings > Apps > Advanced app settings > App execution aliases`. They will typically be referred to as "App Installer". See [this question on stackoverflow.com](https://stackoverflow.com/questions/57485491/python-python3-executes-in-command-prompt-but-does-not-run-correctly) to understand why.
			* Ensure that your Python directory either has a copy of Python named "python3.exe" or a symlink linking to the Python executable.
			* `build.py` does this for you: it copies the interpreter that runs it to `build\pybin\python3.exe` and puts that directory first on the `PATH` of every build command. Without it, `python3` resolves to any other Python on the machine (MSYS2's, for example) and the code generation actions break.
			* Note that `gn gen` writes the absolute path of `python3` into `out\Default\toolchain.ninja`, so changing which Python builds Paani means re-running `gn gen`; the compiled objects are not invalidated by it, only the actions.
		* `requests` and `Pillow`. Install with `python -m pip install requests Pillow`; ensure Python's Scripts directory is on `PATH`.
    * Make sure to lift the `MAX_PATH` length restriction, either by clicking the button at the end of the Python installer or by [following these instructions](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry#:~:text=Enable,Later).
    * Git (to fetch all required ungoogled-chromium scripts)
        * During setup, make sure "Git from the command line and also from 3rd-party software" is selected. This is usually the recommended option.

### Building

Run in `Developer Command Prompt for VS` (as administrator):

```cmd
git clone --recurse-submodules https://github.com/imputnet/helium-windows.git
cd helium-windows
# Replace TAG_OR_BRANCH_HERE with a tag or branch name
git checkout --recurse-submodules TAG_OR_BRANCH_HERE
python3 build.py
python3 package.py
```

A zip archive and an installer will be created under `build`.

**NOTE**: If the build fails, you must take additional steps before re-running the build:

* If the build fails while downloading the Chromium source code (which is during `build.py`), it can be fixed by removing `build\download_cache` and re-running the build instructions.
* If the build fails at any other point during `build.py`, it can be fixed by removing everything under `build` other than `build\download_cache` and re-running the build instructions. This will clear out all the code used by the build, and any files generated by the build.

An efficient way to delete large amounts of files is using `Remove-Item PATH -Recurse -Force`. Be careful however, files deleted by that command will be permanently lost.

* If the build fails in `//chrome/updater/...` or another MIDL action with
  `AssertionError` at `build\toolchain\win\midl.py`'s
  `assert contents[0:8] == b'MSFT\x02\x00\x01\x00'`, a pregenerated `.tlb` under
  `build\src\third_party\win_build_output\midl` is an empty file. Helium ships the tree
  with those binary blobs pruned, so the first `midl.py` run in a tree creates a 0-byte
  placeholder there, generates the real output into `out\Default\gen`, and leaves the
  placeholder behind; a *later* run in the same tree then finds the file present, skips the
  regeneration branch and asserts on the empty copy. Delete the empty files and rebuild:
  `Get-ChildItem build\src\third_party\win_build_output -Recurse -File | Where-Object Length -eq 0 | Remove-Item`

## Developer info

### First-time setup

1. [Setup MSYS2](http://www.msys2.org/)
2. Run the following in a "MSYS2 MSYS" shell:

```sh
pacman -S quilt python3 vim tar
# By default, there doesn't seem to be a vi command for less, quilt edit, etc.
ln -s /usr/bin/vim /usr/bin/vi
```

### Updating patches and pruning list

1. Start `Developer Command Prompt for VS` and `MSYS2 MSYS` shell and navigate to source folder
	1. `Developer Command Prompt for VS`
		* `cd c:\path\to\repo\helium-windows`
	1. `MSYS2 MSYS`
		* `cd /path/to/repo/helium-windows`
		* You can use Git Bash to determine the path to this repo
		* Or, you can find it yourself via `/<drive letter>/<path with forward slashes>`
1. Clone sources
	**`Developer Command Prompt for VS`**
	* `python3 helium-chromium\utils\clone.py -o build\src`
1. Update pruning list
	**`Developer Command Prompt for VS`**
	* `python3 helium-chromium\devutils\update_lists.py -t build\src --domain-regex helium-chromium\domain_regex.list`
1. Update patches
	**`MSYS2 MSYS`**
	1. Setup patches and shell to update patches
		* `./devutils/update_patches.sh merge`
		* `source devutils/set_quilt_vars.sh`
	1. Go into the source tree
		* `cd build/src`
	1. Use quilt to refresh patches. See ungoogled-chromium's [docs/developing.md](https://github.com/ungoogled-software/ungoogled-chromium/blob/master/docs/developing.md#updating-patches) section "Updating patches" for more details
	1. Go back to repo root
		* `cd ../..`
	1. Remove all patches introduced by helium-chromium
		* `./devutils/update_patches.sh unmerge`
	1. Sanity checking for consistency in series file
		* `./devutils/check_patch_files.sh`
1. Use Git to add changes and commit
