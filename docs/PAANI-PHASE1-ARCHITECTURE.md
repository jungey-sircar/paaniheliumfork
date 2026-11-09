# Paani Browser — Phase 1 架构审计报告

审计日期：2026-10-31
审计范围：`imputnet/helium`、`imputnet/helium-windows`、Chromium `156.0.8078.79` 源码树、本机构建环境
结论：采用 **Helium** 作为上游基座，Paani 以「独立补丁层 + 独立品牌资源层」的方式改造。

---

## 1. 结论与推荐路径

| 项目 | 结论 |
|---|---|
| 上游基座 | `imputnet/helium`（核心补丁集） + `imputnet/helium-windows`（Windows 构建/打包） |
| Chromium 版本 | **156.0.8078.79**（`helium-chromium/chromium_version.txt`） |
| 上游浏览器版本 | Helium **0.20.3.1**（2026-10-30 发布） |
| 构建工具 | GN + Ninja/Siso（上游自带），`build.py` / `package.py` |
| 本机可构建性 | **可以**，但内存是唯一实质性风险（见 §7） |
| 改造方式 | 保持 helium 子模块**完全干净**，Paani 改动全部落在 `paani-windows/` 内 |

推荐路径一句话概括：
> 把 `helium-windows` 变成 `paani-windows`，用 Helium 现成的品牌替换管线把 "Helium" 换成 "Paani"，
> 用 Paani 自己的补丁层补上 **Windows 原生材质（Mica/Acrylic）**（Helium 只做了 macOS），
> 再用 Paani 自己的品牌资源替换全部图标/About/安装器。

---

## 2. 上游仓库事实清单

### 2.1 `imputnet/helium`（核心补丁集仓库）

- 许可证：**GPL-3.0**（Helium 自有代码）；导入自 ungoogled-chromium 的部分保留 **BSD-3-Clause**（`LICENSE.ungoogled_chromium`）；Chromium 本体为混合 BSD/Apache/MIT 等。
- 活跃度：最后推送 2026-10-30（审计前一天），22k stars，未归档。
- 结构：

  | 路径 | 内容 |
  |---|---|
  | `patches/series` | **370 条补丁**，来源合并了 brave / bromite / debian / helium / inox-patchset / iridium-browser / ungoogled-chromium / upstream-fixes |
  | `patches/helium/{core,ui,settings}/` | Helium 自有 UI / 核心 / 设置页补丁 |
  | `utils/name_substitution.py` + `name_substitution_utils.py` | **品牌替换引擎**：扫描 `.grd/.grdp/.xtb`，正则把 `Chrome`/`Chromium` → `Helium`，`chrome://` → `helium://` |
  | `utils/domain_substitution.py` | 域名替换（去 Google 端点） |
  | `utils/prune_binaries.py` | 依据 `pruning.list` 裁剪二进制 |
  | `utils/helium_version.py` | 版本号计算 |
  | `resources/branding/` | **全部品牌资源**：app_icon、product_logo（png/svg/icon/白底/单色） |
  | `resources/helium_resources.txt` | 资源拷贝清单（把品牌资源铺到 Chromium 主题目录） |
  | `resources/generate_resources.txt` | 图标缩放规则（raw.png → 16/24/32/48/64/128/256） |
  | `deps.ini` | 额外依赖：搜索图标、onboarding 页、**uBlock Origin 1.75.0** |
  | `flags.gn` | `safe_browsing_mode=0`、`enable_reporting=false`、`enable_widevine=true`、`google_api_key=""` |

### 2.2 `imputnet/helium-windows`（Windows 构建与打包）

- 许可证：**GPL-3.0** + BSD-3-Clause（同上结构）。
- `helium-chromium` 是指向 `imputnet/helium` 的 **git submodule**（当前固定在 `2f81b9ca`）。
- `patches/series`：**31 条** Windows 专属补丁，分四组：
  - `ungoogled-chromium/windows/*`（12 条）：关闭机器 ID / RLZ / 加密 / 事件日志等
  - `helium/windows/*`（6 条）：`change-branding.patch`（安装模式、注册表键、ProgID、7z 包名）、`helium-versioning.patch`、提权服务、WinSparkle 更新器
  - `helium/windows/drm/*`（4 条）：PlayReady / MF 修复
  - `helium/windows/updater/*`（9 条）：WinSparkle 自动更新
- `installer/helium.nsi`：NSIS 安装器脚本；`package.py` 产出 zip + installer + mini-installer。
- `flags.windows.gn`：`chrome_pgo_phase=2`、`is_clang=true`、`use_siso=true`、`proprietary_codecs=true`、`enable_rust=true`、`blink_symbol_level=0`、`symbol_level=1`。

### 2.3 `build.py` 实际做了什么（逐段核对过源码）

1. `build/src` ← 解压 Chromium 源码；`build/download_cache` ← 下载缓存
2. 下载源（x64 默认 **tarball 模式**）：
   - `helium-chromium/downloads.ini` + `downloads.x64.ini` → `chromium-156.0.8078.79-base.tar.zst`（**1.84 GiB**，含已同步的第三方依赖与 depot_tools）
   - `downloads.ini` → NSIS 3.11、WinSparkle 0.9.3、PortableGit 2.52.0
   - `helium-chromium/deps.ini` → uBlock、onboarding、搜索图标
   - ARM64 走 `--clone`：用 depot_tools `gclient sync`（checkout_configuration=small）
3. `prune_binaries.prune_dirs / prune_files` → 按 `pruning.list` 裁剪
4. **打补丁（关键顺序）**：
   1. `helium-chromium/patches`（370 条）
   2. `paani-windows/patches`（31 条）← **Paani 补丁应插在这里之后**
5. `domain_substitution` → `name_substitution`（Helium 品牌）→ `i18n_apply`
6. 写 `chrome/VERSION`（追加 Helium 版本段）
7. 生成并铺品牌资源（`generate_resources.py` → `replace_resources.py`）
8. 拼装 `out/Default/args.gn` = `flags.gn` + `flags.windows.gn` + `is_official_build=true`
9. `gn gen out/Default` → `autoninja.py -C out/Default chrome chromedriver setup mini_installer`

---

## 3. 品牌替换机制（Paani 改造的落点）

Helium 的品牌替换分三层，Paani 需要逐层接管：

| 层 | 上游实现 | Paani 需要的改动 |
|---|---|---|
| **A. 字符串** | `utils/name_substitution.py` 扫 `.grd/.xtb`，`Chrome/Chromium → Helium`，`chrome:// → helium://` | 追加一次 `Helium → Paani`、`helium:// → paani://` 替换 |
| **B. 资源** | `resources/branding/*` + `generate_resources.txt` + `helium_resources.txt` + `resources/platform_resources.txt`（→ `chromium.ico`） | 用 Paani 图标替换 raw.png 与 product_logo.*，改 `platform_resources.txt` 指向 Paani 资源 |
| **C. 编译期常量** | 补丁 `helium/core/change-chromium-branding.patch`（BRANDING 文件、崩溃上报 product_name）、`helium/windows/change-branding.patch`（安装模式、注册表键、ProgID、`Helium-bin`、`helium.packed.7z`）、`helium/core/override-chrome-protocol.patch`（`helium://` 协议注册，涉 25 个文件） | 新增 Paani 补丁覆盖以上全部 |

### 3.1 关键决策：保持 helium 子模块干净

`name_substitution.py` 位于 helium 子模块内。若直接改子模块，会破坏 `git submodule update` 的上游同步能力，
违背「Paani 改动必须可与上游分离」的要求。

**采用方案**：在 `paani-windows` 侧新增 `utils/paani_name_substitution.py`，
复用 helium 子模块的 `name_substitution_utils`（作为库导入），但使用 **Paani 自己的正则表**，
在 `build.py` 中 helium 替换完成之后追加一次替换。

这样：
- `helium-chromium` 子模块保持 pristine → 上游升级只需 `git submodule update && git checkout <new-tag>`
- Paani 的全部差异集中在 `paani-windows/patches/paani/`、`paani-windows/utils/paani_*.py`、`paani-windows/resources/paani/`
- `git diff paani/main..main` 即可完整审阅 Paani 的全部改动

---

## 4. 广告与隐私拦截现状

**Helium 已内置真实广告拦截，无需引入第二套引擎。**

- 引擎：**uBlock Origin**（Helium 专用分支 `imputnet/uBlock`，v1.75.0）
- 集成方式：以 **component extension** 形式内置（`helium/core/ublock-install-as-component.patch`、`ublock-setup-sources.patch`、`ublock-reconfigure-defaults.patch`、`ublock-helium-services.patch`、`ublock-dns-uncloaking.patch`）
- 过滤器列表：由 Helium 自建服务托管（`imputnet/helium-services`，可自托管）
- 设置页入口：`helium/ui/ublock-show-in-settings.patch`
- 无 Brave `adblock-rust`：**不需要**。引入第二套引擎会产生重复解析开销，违反"避免重复引擎"要求

已具备的隐私措施（无需重复实现）：
- `safe_browsing_mode=0`（`flags.gn`）+ `fix-building-without-safebrowsing.patch`
- `enable_reporting=false`、`google_api_key=""`、`use_official_google_api_keys=false`
- `windows-disable-machine-id.patch`、`windows-disable-encryption.patch`、`windows-disable-rlz.patch`
- `helium/core/crash-reporter-privacy-tweaks.patch` + `disable-outdated-build-detector.patch`
- `remove-google-promotional-resources.patch`、`disable-ad-topics-and-etc.patch`

Paani 需要**验证**（而非重写）的项：拦截计数器可见性、按站点例外（allowlist）、第三方请求过滤、过滤器列表更新、赞助内容缺席。

---

## 5. UI 主题与透明化技术可行性（最关键的技术结论）

### 5.1 现状

Helium 已有相当完整的 UI 补丁体系（`patches/helium/ui/` 共 **100+** 条），包括：
`default-theme.patch`（新 profile 默认灰度主题）、`helium-color-scheme.patch`（配色体系）、
`helium-color-mixers.patch`、`rounded-frame-corners.patch`（窗口圆角）、`tabs.patch`、`toolbar.patch`、
`omnibox.patch`、`location-bar.patch`、`clean-new-tab-page.patch`、`restyle-ntp-tiles.patch`、
`infobar.patch`、`progress-bar.patch`、`find-bar.patch`、`toast.patch`、`frame-background.patch` 等。

### 5.2 决定性发现：Chromium 156 **已经内置** DWM 背景（Mica）支持

`ui/views/widget/desktop_aura/desktop_window_tree_host_win.cc`：

```cpp
if (ShouldAddDWMBackdrop()) {
  DWM_SYSTEMBACKDROP_TYPE backdrop = DWMSBT_MAINWINDOW;
  HRESULT hr = DwmSetWindowAttribute(GetHWND(), DWMWA_SYSTEMBACKDROP_TYPE,
                                     &backdrop, sizeof(backdrop));
  ...
}
UpdateBackdropColorMode();   // DWMWA_USE_IMMERSIVE_DARK_MODE，跟随系统深色模式

bool DesktopWindowTreeHostWin::ShouldAddDWMBackdrop() {
  return ((message_handler_->window_ex_style() & WS_EX_NOREDIRECTIONBITMAP) ==
          WS_EX_NOREDIRECTIONBITMAP) &&
         !message_handler_->is_translucent() &&
         (GetHWND() == GetAncestor(GetHWND(), GA_ROOT));
}
```

`WS_EX_NOREDIRECTIONBITMAP` 由 `ui/views/widget/widget_hwnd_utils.cc` 设置，条件是
`components/viz/common/features.cc` 中 `kRemoveRedirectionBitmap`（**默认开启**）：

```cpp
BASE_FEATURE(kRemoveRedirectionBitmap, base::FEATURE_ENABLED_BY_DEFAULT);
```

**结论**：
1. Chrome/Chromium 在 Windows 11 上**本来就会**对顶层窗口应用 Mica（`DWMSBT_MAINWINDOW`）。
2. 用户看不到 Mica，**不是**因为缺 DWM 调用，而是因为浏览器 frame 自己绘制了**不透明背景**，把底下的 backdrop 盖住了。
3. 因此 Paani 的透明化工作 = **让 frame 区域不绘制不透明背景**，而不是新造一套透明 API。
   这与用户要求中"Do not assume that changing CSS alone can make the native Chromium window transparent"的
   精神一致——我们要改的是原生绘制路径（`OnPaint` / `background_paint_brush_` / frame 背景视图）。

> 旁证：Chromium 156 已**移除**旧的 `Windows11MicaTitlebar` 实验项
> （`chrome/browser/ui/ui_features.cc`、`chrome/browser/ui/features.cc` 中均无 Mica 相关 feature；
> 全仓库 `kWindows11MicaTitlebar` 零命中）。所以**不能**依赖 `chrome://flags` 开关，只能走上面这条原生路径。

### 5.3 Helium 的 `native-frame-materials` 只有 macOS 实现 —— 这正是 Paani 要补的洞

`patches/helium/ui/native-frame-materials.patch`（72.9 KB）新增了跨平台抽象层：

```
chrome/browser/ui/views/helium/native_frame_materials.h
chrome/browser/ui/views/helium/native_frame_materials.cc      ← 跨平台入口
chrome/browser/ui/views/helium/native_frame_materials_mac.h    ← 仅 macOS
chrome/browser/ui/views/helium/native_frame_materials_mac.mm   ← NSVisualEffect 实现
```

入口签名：
```cpp
namespace helium {
bool ShouldUseNativeFrameMaterials(const BrowserView* browser_view);
}
```
配套开关：命令行开关 `helium-native-frame-materials`、pref `helium.browser.native_frame_materials`、
设置页开关「Use native frame materials (experimental)」。

**但 BUILD.gn 中只有 macOS 的实现文件，没有 `native_frame_materials_win.cc`。**
也就是说：Helium 在 Windows 上这个开关是空转的。Paani 要做的正是补上 Windows 实现。

### 5.4 Paani 的 Windows 材质实现方案

新增 `patches/paani/ui/native-frame-materials-win.patch`，包含：

```
chrome/browser/ui/views/helium/native_frame_materials_win.h
chrome/browser/ui/views/helium/native_frame_materials_win.cc
```

职责划分：
- **DWM 侧**：Chromium 已自动调用 `DWMWA_SYSTEMBACKDROP_TYPE`（Mica）。Paani 需要**升级为 Acrylic**
  （`DWMSBT_TRANSIENTWINDOW`）或保持 Mica，二选一；并需要**在 frame 绘制路径上停止画不透明底色**，
  让 Mica 透出来。
- **降级路径**：Windows 10 无 `DWMWA_SYSTEMBACKDROP_TYPE` → 自动退回不透明实色（Chromium 现有行为即满足）。
- **无障碍**：检测系统「Transparency effects」（Windows 11 22H2+ 的
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\EnableTransparency` / `UISettings3`），
  用户关闭效果时强制实色。
- **深色模式**：Chromium 的 `UpdateBackdropColorMode()` 已处理 `DWMWA_USE_IMMERSIVE_DARK_MODE`，
  只需保证 Paani 的主题切换能触发 `SetBackgroundColor` → `UpdateBackdropColorMode()`。

需要让"不绘制不透明背景"生效的关键位置（均已被 Helium 改过，属于同一条绘制链）：

| 文件 | 作用 |
|---|---|
| `chrome/browser/ui/views/frame/browser_frame_view.cc` | 非客户区/frame 绘制入口 |
| `chrome/browser/ui/views/frame/themed_background.cc` | frame 主题背景（Helium 已改） |
| `chrome/browser/ui/views/frame/custom_corners_background.cc` | Helium 新增的圆角背景视图 |
| `chrome/browser/ui/views/frame/horizontal_tab_strip_region_view.cc` | 标签栏背景（Helium 已改） |
| `chrome/browser/ui/views/frame/tab_strip.cc` | 标签条绘制（Helium 已改） |
| `chrome/browser/ui/views/frame/layout/browser_view_layout_impl.cc` | frame 布局与背景归属（Helium 已改） |
| `chrome/browser/ui/views/tabs/common/tab_view.cc` / `horizontal_tab_style_views.cc` | 单个标签背景 |
| `chrome/browser/ui/views/toolbar/toolbar_view.cc` | 工具栏背景 |

### 5.5 网页内容区必须保持不透明

- Chromium 的内容视图（`WebContentsView` / `ContentsContainerView`）绘制不透明底色，与 frame 背景是不同层。
- Helium 的 `rounded-frame-corners.patch` 只改 `ContentsContainerView` / `MultiContentsView` 的**圆角与边距**，
  不改变内容底色的不透明性。
- Chromium 提供 `BrowserDesktopWindowTreeHostWin::ShouldWindowContentsBeTransparent()`，
  **Paani 必须保持其关闭**，确保网页内容 100% 不透明（用户明确要求）。
- 自检方式：Phase 4 验收时对普通网页截图，确认内容区无透出桌面的情况。

---

## 6. 替代基线对比

| 方案 | 评价 |
|---|---|
| **Helium（选用）** | 完整 Chromium 156；已有 uBlock 内置广告拦截、WinSparkle 更新、PlayReady/Widevine、品牌替换管线、Windows 构建脚本成熟、上游活跃。**唯一缺口是 Windows 原生材质，正好是 Paani 的差异化价值。** |
| ungoogled-chromium | 与 Helium 同源（Helium 大量复用其补丁与脚本），但**没有** uBlock 广告拦截、没有 WinSparkle、没有 Helium 的 UI/配色体系，等于要重做 §4 和 §5 的全部工作。 |
| 直接 fork Chromium | 需要从零实现：品牌替换、去 Google 化、下载器、更新器、安装器、广告拦截。除非要做 Chromium 之外的深度架构创新，否则成本最高、风险最大。 |

结论：Helium 是"最小可靠路径"。

---

## 7. 本机环境审计

| 项目 | 实测值 | 判定 |
|---|---|---|
| 操作系统 | Windows 11 Pro 10.0.26200 (Build 26200) | ✅ |
| CPU | Intel Core i5-12450H，8 核 12 线程 | ⚠️ 构建耗时长（预估 6–12 小时） |
| 内存 | **16.0 GB 总量**，审计时仅剩 **1.4 GB 可用** | 🔴 **唯一实质性风险** |
| C: 盘可用 | 97.8 GB | ❌ 不足以放 Chromium 源码+产物 |
| E: 盘可用 | **268.2 GB** | ✅ 全部构建放在 E: |
| Visual Studio | **Build Tools 2022 17.13.3**（非 IDE），含 LLVM | ✅ `vcvars64.bat` 存在，`vswhere` 可发现 |
| MSVC | 14.43.34808（v143） | ✅ 满足 Chromium 要求 |
| Windows SDK | 10.0.22621.0 | ✅ 满足 Chromium 最低要求（需 ≥ 10.0.22621） |
| Python | **3.13.7**（`C:\Python313`） | ✅ `requests` 2.32.4 / `Pillow` 12.2.0 / `pywin32` 311 / `psutil` 7.0.0 全部就绪 |
| ⚠️ PATH 陷阱 | `python3` 指向 `C:\msys64\ucrt64\bin\python3.exe`（**无 pip**） | 必须使用 `python` 而非 `python3` |
| Git | 2.51.2 | ✅ |
| 7-Zip | `C:\Program Files\7-Zip\7z.exe` | ✅ |
| 长路径 | `LongPathsEnabled = 1` | ✅ |
| 开发者模式 | `AllowDevelopmentWithoutDevLicense = 1` | ✅（构建需创建符号链接） |
| 网络 | GitHub / tarballs.imput.net 均可达 | ✅ |

### 7.1 磁盘预算

| 项目 | 预估 |
|---|---|
| `build/download_cache`（源码 tarball 1.84 GiB + NSIS + WinSparkle + PortableGit） | ~2 GB |
| `build/src`（解压后的 Chromium 源码 + 已同步依赖 + .git） | 30–45 GB |
| `build/src/out/Default`（is_official_build + symbol_level=1，含 PDB） | 25–45 GB |
| **合计** | **60–90 GB**（E: 可用 268 GB ✅） |

### 7.2 内存风险与对策

Chromium 在 Windows 上链接 `chrome.dll` 使用 MSVC 增量 LTCG，是内存峰值最高的步骤，
在 16 GB 机器上有失败可能（错误表现为 `LNK1102: out of memory` 或链接器被终止）。

对策（按优先级）：
1. 构建前**关闭占用内存的应用**（审计时仅剩 1.4 GB 可用，必须先腾出空间）。
2. `symbol_level=1` + `blink_symbol_level=0`（上游 `flags.windows.gn` 已设置）—— 保留。
3. 若链接 OOM：改 `symbol_level=0` 重建（省下大量 PDB 的内存与磁盘）。
4. 若仍 OOM：退化为 `is_component_build=true`（开发版，编译产物小、链接快，但**不是**发布产物，
   仅用于验证 UI/品牌改动可用；发布仍需回到 official build）。
5. 使用 `siso`（上游已启用 `use_siso=true`），其调度器按内存自动限流。

---

## 8. 许可证义务

| 组成 | 许可证 | Paani 的义务 |
|---|---|---|
| Helium 自有代码与补丁 | GPL-3.0 | 修改并分发二进制时，**必须**以 GPL-3.0 发布**完整对应源码**；保留版权声明与许可证正文 |
| ungoogled-chromium 导入部分 | BSD-3-Clause | 保留版权声明与免责声明 |
| Chromium 本体 | 混合（BSD-3-Clause / Apache-2.0 / MIT / ISC / 等） | 保留 `LICENSES/` 与 `THIRD_PARTY_LICENSES`；Chromium 的官方页面使用的表述是"混合开源许可"，**不能宣称单一许可证** |
| 导入的第三方组件 | 各不相同 | 维护第三方声明文件，保留上游 NOTICE |

**个人使用**（仅自用、不分发）：GPL-3.0 §2 的"发布"义务不触发，但仍需保留上游版权与许可声明
（Helium 的 `LICENSE`、`LICENSE.ungoogled_chromium` 不得删除）。

**若将来分发 Paani**：必须
1. 以 GPL-3.0 提供完整对应源代码（含 Paani 补丁、构建脚本、资源、修改后的源码树获取方式）；
2. 保留所有上游版权声明、许可证正文与 NOTICE；
3. 不得对 Paani 附加额外限制；
4. 提供 `THIRD_PARTY_NOTICES`，涵盖 Chromium、Helium、ungoogled-chromium、uBlock Origin、NSIS、WinSparkle 等。

---

## 9. 仓库结构与 Git 策略

```
E:\eric\PaaniBrowserChromiumFork\
├── docs\                        ← 报告与变更日志
├── logs\                        ← 构建日志
└── paani-windows\               ← ★ 主仓库（fork of imputnet/helium-windows）
    ├── helium-chromium\         ← git submodule，保持 pristine，指向上游 tag
    ├── patches\paani\           ← ★ Paani 专属补丁（新增）
    ├── utils\paani_*.py         ← ★ Paani 品牌替换（新增）
    ├── resources\paani\         ← ★ Paani 品牌资源（新增）
    └── build\                   ← 构建产物（不入库）
```

分支策略：
- `paani-windows`：`main` = 上游原样（只用于 rebase），`paani/main` = Paani 开发分支
- `helium-chromium` 子模块：保持 detached 在上游 tag，**不建立 Paani 分支**
- 提交粒度：按主题拆分（品牌 / UI / 隐私 / 性能），每次提交只做一件事

上游同步流程：
```
git -C paani-windows fetch origin main && git rebase origin/main
git -C paani-windows submodule update --init --recursive
git -C paani-windows/build/src ... 重新走 build.py
```

---

## 10. 阶段执行计划

| Phase | 内容 | 验收 | 状态 |
|---|---|---|---|
| 1 | 上游审计 + 环境审计 + 本报告 | 报告交付 | ✅ 完成 |
| 2 | 原样构建 Helium 基线 | `out/Default/chrome.exe` 可启动并正常访问网站 | 🔄 进行中 |
| 3 | Paani 品牌化 | 图标/标题/About/安装器/新标签页/NTP 全为 Paani | ⬜ |
| 4 | Paani 界面 + Windows 原生材质 | 浅色/深色主题、标签栏+工具栏半透明、网页内容不透明、降级路径可用 | ⬜ |
| 5 | 隐私与广告拦截验证 | 拦截计数、例外、过滤器更新、无赞助内容、无遥测 | ⬜ |
| 6 | 性能基线与对比 | §11 全量指标，与上游 Helium 同机对比 | ⬜ |
| 7 | 个人使用版发布 | 可用 Windows 构建 + 安装/升级文档 + 已知限制 + 精确版本记录 | ⬜ |

---

## 11. 性能验收指标（Phase 6 采集）

测量对象：**整个浏览器进程树**（browser + renderer + gpu + utility + network service），非仅主进程。

- 冷启动 / 热启动耗时
- 启动稳定后的空闲内存
- 5 / 10 / 20 个标签页时的内存
- 空闲浏览 CPU 占用
- 加载网页期间 CPU 占用
- 关闭标签页后的内存回收
- 导航响应延迟
- 广告拦截引入的额外开销

对照组：同一台机器上的上游 Helium 0.20.3.1（相同网站、相同设置、相同负载）。
本机已装 `psutil` 7.0.0，可直接用于进程树采样。

---

## 12. 风险登记

| 风险 | 等级 | 对策 |
|---|---|---|
| 16 GB 内存链接 OOM | 🔴 高 | 见 §7.2 的五级降级方案 |
| 首次构建 6–12 小时 | 🟠 中 | 构建期间并行准备 Phase 3/4 补丁；后续走增量编译 |
| Chromium 156 源码大幅重构（`ui/base/ui/base_types.h` → `ui/base/ui_base_types.h`；`ui/base/win/hwnd_util.h` 已移除；`ui/views/window/native_window_win.*` → `ui/platform_window/win/win_window.cc`；`chrome/browser/ui/ui_features.cc` → `chrome/browser/ui/features.cc`） | 🟠 中 | 写补丁前先在 `build/src` 里 grep 确认当前路径，不要沿用旧版 Chromium 路径 |
| `helium://` → `paani://` 需改动 25 个文件 | 🟡 低 | 由 override-chrome-protocol 的镜像补丁一次性完成 |
| 上游 Helium 频繁更新（几乎每日推送） | 🟡 低 | 子模块保持 pristine；Paani 改动集中，rebase 冲突面小 |
| 构建期间磁盘被其他应用占用 | 🟡 低 | 全部落在 E:，定期 `df -h /e` |

---

## 13. 变更日志（Paani 差异）

见 `docs/CHANGELOG-PAANI.md`（随各 Phase 推进补充）。
