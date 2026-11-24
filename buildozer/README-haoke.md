# PySolFC Android 浩科版构建

本目录对应浩科 Android 3.6.1-haoke.2（上游 Android 3.6.1），应用 ID 为 `org.haoke.pysolfc`，版本号为 `102130610`。应用使用 Android 5.0（API 21）或更高版本，安装包提供 `arm64-v8a` 和 `armeabi-v7a`。本仓库保留 PySolFC 上游历史、作者及 GPL-3.0 许可证。

## 构建输入

| 输入 | 来源与版本 | SHA-256 |
| --- | --- | --- |
| 基础 Android APK | [F-Droid PySolFC 3.6.1](https://f-droid.org/en/packages/org.lufebe16.pysolfc/) 的 `org.lufebe16.pysolfc_102130601.apk` | `5b8ba9abc4c11ba0ebcc75d663f2b472704c00840ab564631feb0c84feb45664` |
| 该 APK 的上游对应源码 | [F-Droid 源码归档](https://f-droid.org/repo/org.lufebe16.pysolfc_102130601_src.tar.gz)，也可从本仓库的同版源码 Release 附件取得 | `c9ef0bb171e90a62e248050b8a86fa3c2f0d68d2c393f83b57b2d004556198ff` |
| 运行时构建清单 | [F-Droid 构建元数据](https://gitlab.com/fdroid/fdroiddata/-/blob/master/metadata/org.lufebe16.pysolfc.yml) 与 [python-for-android 固定提交](https://github.com/kivy/python-for-android/tree/5f5a46dae0b9c9a986ef90842396a0ef9e7b95d1) 的 recipes | 版本及下载校验值见对应 recipes |

本版从 [PySolFC android-3.6.1](https://github.com/shlomif/PySolFC/tree/fb039c53386b2dc2758848b110433c4534c3f55e) 派生。F-Droid 归档包含上游发行源码、牌组和准备脚本。运行时依赖使用归档对应的 F-Droid 构建记录及固定 python-for-android recipes。相关 Python 与本机组件各自的许可证随上游来源分发。

## Windows 打包

实际交付 APK 使用 JDK 21、Python 3.12、Apktool 3.0.2、Android SDK Build Tools 36.0.0，以及 `polib==1.2.0` 和 `Pillow==12.2.0`。打包入口校验上游 APK，复用其中的原生库与 Python 运行时，并从当前源码生成应用内容、简中文件、资源和安装身份。

在项目根目录安装 `polib` 和 `Pillow`，使用当前产品的签名凭据设置仅对打包进程可见的 `PYSOLFC_RELEASE_STORE_PASS` 和 `PYSOLFC_RELEASE_KEY_PASS`。示例中的尖括号需替换为本机路径或已有签名信息。

```powershell
python buildozer/build_qa_windows.py --formal `
  --upstream '<F-Droid APK 路径>' --apktool '<Apktool JAR 路径>' `
  --build-tools '<Android SDK build-tools/36.0.0 的路径>' `
  --keystore '<该产品的正式签名文件路径>' --key-alias '<别名>' `
  --signer-sha256 '<正式证书 SHA-256>' --output 'PySolFC-3.6.1-haoke.2.apk'
```

当前 Windows 打包器在固定 SDL2 字节码中应用启动保护。`sdl2-surface-ready.patch` 保存该改动在 SDL2 2.30.11 中的 Java 等效补丁，可在用上游 recipes 重建运行时时应用到 SDL2 源码树。补丁等待绘图 surface 创建后再进入恢复流程。实际验收的是上面的 Windows 打包产物。

## 资源来源与再生成

- `design/图标/playing-cards-master.png` 为新图标的透明原稿。执行 `python buildozer/render_release_icon.py` 可重新生成启动器、自适应前景与背景、预启动图和应用内图标。
- `design/纸牌` 含自制牌组原画、生成脚本与 DejaVu 字体许可证。`data/cardset-standard-png` 为实际使用的牌组。
- `po/zh_CN_*.po` 和 `data/html-zh` 为界面及游戏规则的简中资源。Noto Sans SC 使用 SIL OFL 1.1。其余上游资源的归属和许可随原有目录保留。

Release 中的证书指纹只供核验。官方签名私钥和密码由维护者保管。独立签名的重建包需要单独的安装身份或卸载同名旧包后安装。


## 本版验证与更新检查

当前正式包沿用原产品证书，versionCode 从 102130608 提升为 102130610；QA 使用隔离包名 `org.lufebe16.pysolfc.qa`、3.6.1-qa.8 和既有 Debug 证书。正式包没有 debuggable。上游版本文件保持 3.6.1，Android 实际浩科版本由构建器写入，关于页从安装身份读取。

```powershell
python -m unittest discover -s tests/lib/pysol_tests -t tests/lib -v
$env:PYSOLFC_CARDSET_APK = '<本版实际 APK 路径>'
python -m unittest buildozer.test_cardset_qa buildozer.test_haoke_updates -v
```

测试共 18 + 14 + 23 项通过。更新器测试使用本机已有 `cryptography` 生成隔离测试签名，它不是 APK 运行依赖。`tests/fixtures/haoke-updates-none.json` 是真实服务公开签名响应；测试以固定的签发时刻验证，不把固定时间用于运行时。客户端通过既有 OpenSSL EVP 验证 Ed25519，Android 通过原生 HTTPS 使用系统信任库，没有升级或增加运行时依赖。仅新增普通网络权限 INTERNET，无存储、安装包安装或后台服务权限。

请参阅 [更新检查维护与隐私](../docs/haoke-client-updates.md)。正式 APK 大小、SHA-256、证书及已验证边界见默认分支 README。F-Droid 对应源码归档仍为上表固定内容，供重建运行时/资源使用；本版本 Release 链接其已核验的公开附件。
