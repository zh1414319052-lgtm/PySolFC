<p align="center"><img src="data/android-icon/launcher.png" alt="皮索尔纸牌合集 Android 图标" width="112"></p>

# 皮索尔纸牌合集 · PySolFC Android

这里是 PySolFC 的浩科 Android 分支。当前浩科版本 **3.6.1-haoke.2** 基于 F-Droid Android 3.6.1，支持 Android 5.0 及以上、`arm64-v8a` 和 `armeabi-v7a`，包名为 `org.haoke.pysolfc`。保留简中界面、玩法名称与规则、象牙色标准扑克牌、绿金牌背、启动图标及 SDL 冷启动保护。

本次修复花札切换闪退、缺失默认牌组及历史保存状态中牌组与玩法不匹配的问题；有效的用户牌组选择继续读取。新增签名更新检查：在主菜单或帮助页安全检查，帮助菜单提供手动入口。游戏本身可离线使用；检查更新需要联网，不发送牌局数据，不自动下载或安装 APK。

The Haoke Android edition **3.6.1-haoke.2**, based on F-Droid Android 3.6.1, fixes Hanafuda switching crashes, missing default decks, and incompatible persisted decks on startup or saved-game restoration. Compatible user choices remain intact. It retains the Chinese interface and rules, redesigned standard deck, launcher icon, and SDL cold-start protection. Signed update checks run in the foreground on safe menu pages, with a manual Help entry. Games work offline; update checks use the network, send no game data, and never download or install an APK automatically.

| Android 3.6.1-haoke.2 | 校验信息 · Verification |
| --- | --- |
| 版本号 · Version code | `102130610` |
| APK 大小 · APK size | 83,663,517 bytes |
| APK SHA-256 | `6d1271fbbd51cfe41a1581252ca5c95150797de1048685a90d61d7b0c9d25459` |
| 签名证书 · Certificate SHA-256 | `13ea44b975c48845883d171e8f642d3c00d59fd54b2f17ca50ef05e57bcf2a69` |

[下载 Android 正式版 · Download the Haoke Android edition](https://www.haoke.org/software/51c7e11a1f8d6559)

[构建与对应源码 · Build and corresponding source](buildozer/README-haoke.md) · [更新检查与隐私 · Updates and privacy](docs/haoke-client-updates.md) · [本版源码 Release · Source release](https://github.com/zh1414319052-lgtm/PySolFC/releases/tag/android-3.6.1-haoke.2)

已通过上游 18 项和本次 37 项聚焦测试（14 项牌组恢复、23 项更新检查）。USB 真机 QA 已逐屏验证用户要求的花札、塔罗克、圆牌、将牌、记忆、3×3 至 10×10 拼图、石道、麻将与连连看，以及经典接龙操作、错乱配置恢复和冷启动持久化；新增更新检查也已在同一手机读取并验签真实服务响应。正式签名包已在同一 USB 手机保留数据、同签升级，并通过实际版本显示、签名更新检查、麻将→花札→经典接龙、移牌、撤销重做、提示、演示、后台切回及两次冷启动恢复；手机安装文件哈希与本页一致。

18 upstream tests and 37 focused tests pass (14 deck/recovery, 23 updater tests). Physical-device QA covers the requested deck families, all puzzle sizes from 3×3 through 10×10, Klondike interactions, corrupted-state recovery, persistence, and the real signed update service. The formal artifact also passed an in-place same-signature upgrade on that phone, version/update checks, Mahjong-to-Hanafuda-to-Klondike switching, move/undo/redo/hint/demo, background return, and two cold-start restorations. The installed APK hash matches this page. QA-device and formal-device evidence are recorded separately.

横屏仍使用上游保持比例的纵向牌桌，宽屏利用不足；本版未修改横屏布局，用户自行实测。未声明覆盖所有玩法或其他 Android 机型。Landscape retains the existing proportional portrait-board layout and can leave unused space. No landscape-layout fix is claimed; physical landscape acceptance is assigned to the user. Other devices and every individual game are outside the verified scope.

## 上游说明 · Upstream documentation

<p align="center"><img src="html-src/images/high_res/logo_horizontal.png" alt="PySol FC logo" height="180px"></p>

# PySol Fan Club edition

This is an open source and portable (Windows, Linux and Mac OS X) collection
of Card Solitaire/Patience games written in Python. Its homepage is
https://pysolfc.sourceforge.io/.

The maintenance branch of PySol FC on GitHub by [Shlomi
Fish](https://www.shlomifish.org/) and by some other
people, has gained official status, ported the code to Python 3,
and implemented some other enhancements.

- [![CI tests at GitHub](https://github.com/shlomif/PySolFC/actions/workflows/ci.yml/badge.svg)](https://github.com/shlomif/PySolFC/actions/workflows/ci.yml)
[![AppVeyor Build status](https://ci.appveyor.com/api/projects/status/04re7umgl3yuukmh?svg=true)](https://ci.appveyor.com/project/shlomif/pysolfc)

## Call for Contributors

[Shlomi Fish](https://github.com/shlomif), who adopted PySol FC, and maintained
it for several years, has stepped down as its primary maintainer
due to the fact he no longer plays PySol, or other computer card games too
much and that it has been a time sink for him. (Also see
[this Twitter discussion](https://twitter.com/bagder/status/1336793880709238786)
). We are looking for other contributors and there are still
[some large-scale features](https://github.com/shlomif/PySolFC/issues) that
can be implemented.

# Screenshots

![Screenshot of PySol FC](https://i.imgur.com/jQkTGwf.jpg)

## Requirements.

- Python (3.7 or later)
- Tkinter (Tcl/Tk 8.4 or later)

- For sound support (optional)
  - PySol-Sound-Server fork: https://github.com/shlomif/pysol-sound-server (mp3, wav, tracker music)
  - (or: ) PyGame (or PyGame CE): https://www.pygame.org/ (mp3, ogg, wav, midi, tracker music)

- Other packages (optional):
  - Pillow (Python Imaging Library): https://pillow.readthedocs.io/
  - TTKThemes: https://ttkthemes.readthedocs.io/
  - Accessible Output 2: https://accessible-output2.readthedocs.io/
  - Freecell Solver: https://fc-solve.shlomifish.org/
  - [Black Hole Solitaire Solver](https://www.shlomifish.org/open-source/projects/black-hole-solitaire-solver/)

## Installation.

We provide an [installer for Windows](https://sourceforge.net/projects/pysolfc/files/PySolFC/)
(requires Windows XP SP3 or higher) as well as an
[Android package on F-droid](https://f-droid.org/packages/org.lufebe16.pysolfc/).

### Running from source without installation.

You can run from the source directory:

```
python pysol.py
```

After following steps similar to these (on
[Mageia Linux](http://www.mageia.org/) ):


#### Step 1 - install the dependencies

On Fedora you can do:

```
sudo dnf builddep PySolFC
```

On Mageia you can do:

```
sudo urpmi git make pygtk2 pygtk2.0-libglade gnome-python-canvas tkinter
```

On Debian / Ubuntu / etc. you can do:

```
sudo apt-get install cpanminus make perl python3-setuptools python3-tk
```

#### Step 2 - build PySol.

You can try running:

```
python3 scripts/linux-install.py
```

```
git clone https://github.com/shlomif/PySolFC.git
cd PySolFC
# Now make sure you have installed the dependencies.
gmake test
gmake rules
ln -s data/images images
tar -xvf PySolFC-Cardsets-3.0.tar.bz2 # Needs to be downloaded from sourceforge
mkdir -p ~/.PySolFC
rmdir ~/.PySolFC/cardsets
ln -s "`pwd`/PySolFC-Cardsets-3.0" ~/.PySolFC/cardsets
python pysol.py
```

<b>Note!</b> If you are using a Debian derivative (e.g: Debian, Ubuntu, or
Linux Mint) and you are getting an error of "No cardsets were found !!! Main
data directory is `[insert dir here]` Please check your PySol installation.",
then you likely installed the cardsets package which has removed some files
that are needed by pysol from source (without the debian modifications).

Please uninstall that package and use the cardsets archive from sourceforge.net
per the instructions above.

### Installing from source and running in a python venv (virtual environment)

At the moment, this only works on POSIX (Linux, FreeBSD and similar) systems.
Windows and Mac users - you'll need to chip in with a script for your system.

#### 1 - Install build prerequisite: pysol-cards

This is kind of stupid and maybe it can be fixed in the future, but for now:

```
pip install pysol-cards
```

You may want to use your OS distribution package system instead, for example:

```
sudo apt-get install python3-pysol-cards
```

For Pillow compilation, libjpeg headers and libraries need to be available:

```
sudo apt-get install libjpeg-dev
```

#### 2 - Clone the source from version control

```
git clone git://github.com/shlomif/PySolFC.git
cd PySolFC
```

#### 3 - Create your virtual environment.

```
PKGTREE=/usr/local/packages/PySolFC # or whatever
export PKGTREE
mkdir -p "$PKGTREE"
( cd "$PKGTREE" && python -m venv ./env )
```

#### 4 - Run the install script

```
./contrib/install-pysolfc.sh
```

#### 5 - Put cardsets into place as above.

#### 6 - Enjoy playing

```
"$PKGTREE"/env/bin/pysol.py
```

### Alternate toolkit.

- Kivy
- Features:
  - Sound support integrated.
  - Android apk build support.
- Running from source without installation:

```
python pysol.py --kivy
```

### Android App

On the basis of Kivy an Android App is also available. You may build
your own using appropriate build instructions in README.android and
in Directory buildozer.

Some versions will also be published on F-droid.

[<img src="https://fdroid.gitlab.io/artwork/badge/get-it-on.png"
     alt="Get it on F-Droid"
     height="80">](https://f-droid.org/packages/org.lufebe16.pysolfc/)


### Configuring Freecell Solver

If you want to use the solver, you should configure freecell-solver
( https://fc-solve.shlomifish.org/ ) by passing the following options
to its CMake-based build-system:
`-DMAX_NUM_FREECELLS=8 -DMAX_NUM_STACKS=20 -DMAX_NUM_INITIAL_CARDS_IN_A_STACK=60`.

## Install Extras.

- Music
 - Copy some music files (in mp3 format for example) to ~/.PySolFC/music/

 - Original PySol music can be downloaded from:
     https://sourceforge.net/projects/pysolfc/files/PySol-Music/

- Cardsets
 - Copy cardsets to ~/.PySolFC/cardsets

 - Additional cardsets can be downloaded from the PySolFC project page:
     https://sourceforge.net/projects/pysolfc/files/

## Related repositories and links

- [PySol-Sound-Server fork](https://github.com/shlomif/pysol-sound-server)
- [Sources for the PySolFC web site](https://github.com/shlomif/pysolfc-website)
- [PySolFC Announcements Drafts](https://github.com/shlomif/pysolfc-announcements)
- [PySolFC-Cardsets tarballs sources repo](https://github.com/shlomif/PySolFC-Cardsets)
- [Extra mahjongg cardsets for PySolFC - originally for flowersol](https://github.com/shlomif/PySol-Extra-Mahjongg-Cardsets)
- [The old "pysol-music" distribution](https://github.com/shlomif/pysol-music)

Related:

- [Freecell Solver](https://github.com/shlomif/fc-solve)
- [Black Hole Solver](https://github.com/shlomif/black-hole-solitaire)

Other open source solitaires:

- [solitaire.gg](https://github.com/KyleU/solitaire.gg) - web-based and written in Scala
- [Solitairey](https://github.com/shlomif/Solitairey/branches) - web-based written in JavaScript
- [KPat](https://games.kde.org/game.php?game=kpat) - desktop-based for KDE.
- [Aisleriot](https://wiki.gnome.org/Apps/Aisleriot) - desktop-based by the GNOME project with relatively limited functionality.

Screencasts:

- [Black Hole solving](https://github.com/shlomif/pysolfc-black-hole-solver--screencast)
- [Freecell solving using the qualified-seed-improved preset](https://bitbucket.org/shlomif/pysolfc-qualified-seed-improved-screencast)

## Chat

To facilitate coordination about contributing to PySol, please join us for a
real time Internet chat on
the <a href="irc://irc.freenode.net/##pysol">##pysol</a> chat room on
[Freenode](http://freenode.net/) (note the double
octothorpe/hash-sign/pound-sign).  We may set up
chat rooms on different services in the future.

In addition, we set up a
[Google Group for discussing open source card games](https://groups.google.com/forum/#!forum/foss-card-games)
which will also be used for discussing PySol. Feel free to subscribe or post!
