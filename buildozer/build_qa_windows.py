"""Assemble a QA or release APK on Windows from the pinned F-Droid runtime.

The PySolFC application payload is built from this checkout. The pinned
F-Droid runtime is reused with a startup fix in its Android bootstrap.
Each build uses the signing identity supplied for its own package.
"""

import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import polib


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_HASH = (
    "5b8ba9abc4c11ba0ebcc75d663f2b472704c00840ab564631feb0c84feb45664"
)
PACKAGE = "org.lufebe16.pysolfc"
QA_PACKAGE = PACKAGE + ".qa"
VERSION_NAME = "3.6.1-qa.8"
VERSION_CODE = "102130610"
RELEASE_PACKAGE = "org.haoke.pysolfc"
RELEASE_VERSION = "3.6.1-haoke.2"
RELEASE_VERSION_CODE = "102130610"
STORE_PASS_ENV = "PYSOLFC_RELEASE_STORE_PASS"
KEY_PASS_ENV = "PYSOLFC_RELEASE_KEY_PASS"
ANDROID = "{http://schemas.android.com/apk/res/android}"
PRIVATE_TAR = "assets/private.tar"
FONT_FILES = ("NotoSansSC-Regular.ttf", "OFL-NotoSansSC.txt")
ICON_DIR = ROOT / "data/android-icon"
HEADER_ICON = "data/images/icons/48x48/pysol.png"


def run(*command, signing=False):
    args = list(map(str, command))
    if args[0].endswith(".bat"):
        args = ["cmd.exe", "/d", "/c", *args]
    env = os.environ.copy()
    if not signing:
        env.pop(STORE_PASS_ENV, None)
        env.pop(KEY_PASS_ENV, None)
    subprocess.run(args, check=True, env=env)


def application_tar(original, formal=False):
    additions = {
        "main.py": (ROOT / "buildozer/main.py").read_bytes(),
        "locale/zh_CN/LC_MESSAGES/pysol.mo":
            polib.pofile(ROOT / "po/zh_CN_pysol.po").to_binary(),
        "locale/zh_CN/LC_MESSAGES/pysol-games.mo":
            polib.pofile(ROOT / "po/zh_CN_games.po").to_binary(),
        **{
            p.relative_to(ROOT).as_posix(): p.read_bytes()
            for p in (ROOT / "pysollib").rglob("*.py")
        },
        **{
            p.relative_to(ROOT).as_posix(): p.read_bytes()
            for p in (ROOT / "data/html-zh").rglob("*") if p.is_file()
        },
        "data/tiles/Pine_Felt.png": (ROOT / "data/tiles/Pine_Felt.png").read_bytes(),
        **{
            p.relative_to(ROOT).as_posix(): p.read_bytes()
            for p in (ROOT / "data/cardset-standard-png").iterdir() if p.is_file()
        },
        **{f"data/fonts/{n}": (ROOT / "data/fonts" / n).read_bytes()
           for n in FONT_FILES},
    }
    if formal:
        additions[HEADER_ICON] = (ROOT / HEADER_ICON).read_bytes()
    added_directories = {
        parent.as_posix()
        for name in additions
        for parent in PurePosixPath(name).parents
        if parent.parts
    }
    out = io.BytesIO()
    mode = "w:gz" if original.startswith(b"\x1f\x8b") else "w"
    with tarfile.open(fileobj=io.BytesIO(original)) as template:
        with tarfile.open(fileobj=out, mode=mode, format=tarfile.USTAR_FORMAT) as tar:
            for old in template:
                name = old.name.removeprefix("./")
                if name in additions or name.removesuffix("c") in additions:
                    continue
                if old.isdir():
                    added_directories.discard(name)
                tar.addfile(old, template.extractfile(old) if old.isfile() else None)
            # Android's asset extractor creates directories only from directory entries.
            for name in sorted(added_directories):
                entry = tarfile.TarInfo(name)
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o755
                tar.addfile(entry)
            for name, payload in sorted(additions.items()):
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                tar.addfile(entry, io.BytesIO(payload))
    return out.getvalue()


def set_resource_value(path, name, value):
    root = ET.parse(path).getroot() if path.exists() else ET.Element("resources")
    entry = root.find(f"./string[@name='{name}']")
    if entry is None:
        entry = ET.SubElement(root, "string", name=name)
    entry.text = value
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def defer_sdl_resume_until_surface_exists(decoded):
    path = decoded / "smali/org/libsdl/app/SDLActivity.smali"
    source = path.read_text(encoding="utf-8")
    header = ".method public static handleNativeState()V\n"
    before, _, remainder = source.partition(header)
    method, end, after = remainder.partition(".end method\n")
    surface_lookup = (
        "    sget-object v0, Lorg/libsdl/app/SDLActivity;"
        "->mSurface:Lorg/libsdl/app/SDLSurface;\n\n"
    )
    readiness_check = "    iget-boolean v0, v0, Lorg/libsdl/app/SDLSurface;->mIsSurfaceReady:Z"
    surface_read = surface_lookup + readiness_check
    if method.count(surface_read) != 1 or ":cond_6\n    :goto_1\n    return-void" not in method:
        raise ValueError("Unexpected SDL native-state handler in the pinned runtime")

    # onStart can request RESUMED while PythonActivity is still unpacking assets.
    # Keep the transition pending so surfaceChanged can retry after initialization.
    surface_guard = surface_lookup + "    if-eqz v0, :cond_6\n\n" + readiness_check
    path.write_text(before + header + method.replace(surface_read, surface_guard)
                    + end + after, encoding="utf-8")


def add_release_icon(res):
    from PIL import Image

    icon = Image.open(ICON_DIR / 'launcher.png').convert('RGBA')
    for density, pixels in (('mdpi', 48), ('hdpi', 72), ('xhdpi', 96),
                            ('xxhdpi', 144), ('xxxhdpi', 192)):
        target = res / f'mipmap-{density}'
        target.mkdir(exist_ok=True)
        icon.resize((pixels, pixels), Image.Resampling.LANCZOS).save(target / 'haoke_launcher.png')

    layers = res / 'drawable-nodpi'
    layers.mkdir(exist_ok=True)
    for name in ('foreground', 'background'):
        shutil.copyfile(ICON_DIR / f'{name}.png', layers / f'haoke_icon_{name}.png')

    adaptive = res / 'mipmap-anydpi-v26'
    adaptive.mkdir(exist_ok=True)
    root = ET.Element('adaptive-icon')
    ET.SubElement(root, 'background', {ANDROID + 'drawable': '@drawable/haoke_icon_background'})
    ET.SubElement(root, 'foreground', {ANDROID + 'drawable': '@drawable/haoke_icon_foreground'})
    ET.register_namespace('android', ANDROID[1:-1])
    ET.ElementTree(root).write(adaptive / 'haoke_launcher.xml', encoding='utf-8', xml_declaration=True)

    presplash = res / 'drawable' / 'presplash.jpg'
    if not presplash.is_file():
        raise ValueError('Missing pre-splash image in the pinned Android resources')
    art = Image.open(ICON_DIR / 'presplash.png').convert('RGBA')
    splash = Image.new('RGB', art.size, '#102F27')
    splash.paste(art, (0, 0), art.getchannel('A'))
    splash.save(presplash, quality=95, subsampling=0)
    set_resource_value(res / 'values/strings.xml', 'presplash_color', '#102F27')


def configure_resources(decoded, digest, formal=False):
    package = RELEASE_PACKAGE if formal else QA_PACKAGE
    version_name = RELEASE_VERSION if formal else VERSION_NAME
    version_code = RELEASE_VERSION_CODE if formal else VERSION_CODE
    manifest_path = decoded / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace(f'package="{PACKAGE}"', f'package="{package}"')
    manifest = manifest.replace(f'{PACKAGE}.androidx-startup', f'{package}.androidx-startup')
    manifest = manifest.replace('android:allowBackup="true"', 'android:allowBackup="false"')
    # Signed version checks only; no storage or installation permissions.
    if 'android.permission.INTERNET' not in manifest:
        manifest = manifest.replace('<application ',
                                    '<uses-permission android:name="android.permission.INTERNET" />\n    <application ', 1)
    if not formal:
        # Permit adb run-as for synthetic configuration/recovery QA only.
        manifest = re.sub(r' android:debuggable="[^"]*"', '', manifest)
        manifest = manifest.replace('<application ',
                                    '<application android:debuggable="true" ', 1)
    manifest = re.sub(
        r'^\s*<uses-permission android:name="android.permission.'
        r'(?:WRITE_EXTERNAL_STORAGE|MANAGE_EXTERNAL_STORAGE)"\s*/>\n',
        '', manifest, flags=re.MULTILINE,
    )
    if formal:
        manifest = manifest.replace(' android:requestLegacyExternalStorage="true"', '')
        manifest, edited = re.subn(
            r'(<application\b[^>]*?\bandroid:icon=")[^"]+',
            r'\1@mipmap/haoke_launcher', manifest, count=1,
        )
        if edited != 1:
            raise ValueError('Missing application icon in the pinned Android manifest')
    manifest_path.write_text(manifest, encoding="utf-8")
    spec_path = decoded / "apktool.yml"
    spec = spec_path.read_text(encoding="utf-8")
    spec = spec.replace("versionCode: 102130601", f"versionCode: {version_code}")
    spec = spec.replace("versionName: 3.6.1", f"versionName: {version_name}")
    spec_path.write_text(spec, encoding="utf-8")

    res = decoded / "res"
    set_resource_value(res / "values/strings.xml", "private_version", digest)
    chinese = {
        "zh", "zh-rCN", "zh-rSG", "zh-rHK", "zh-rTW", "zh-rMO",
        "b+zh+Hans", "b+zh+Hant",
    }
    locales = {"en", *chinese}
    for path in res.glob("values-*"):
        locale = path.name.removeprefix("values-")
        if re.fullmatch(r"(?:[a-z]{2,3})(?:-r[A-Z]{2})?|b\+[A-Za-z0-9+]+", locale):
            locales.add(locale)
    for locale in sorted(locales):
        title = "皮索尔纸牌合集" if locale in chinese else "PySolFC"
        set_resource_value(res / f"values-{locale}/app_name.xml", "app_name", title)
    if formal:
        add_release_icon(res)


def signing_options(args, keystore):
    if not args.formal:
        return ('--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android',
                '--key-pass', 'pass:android')
    expected = args.signer_sha256.lower().replace(':', '') if args.signer_sha256 else ''
    if not args.key_alias or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Release signing requires the registered alias and certificate SHA-256')
    if not os.environ.get(STORE_PASS_ENV) or not os.environ.get(KEY_PASS_ENV):
        raise ValueError('Release credential environment is missing')
    cert = subprocess.check_output([
        'keytool', '-exportcert', '-keystore', str(keystore), '-alias', args.key_alias,
        '-storepass:env', STORE_PASS_ENV,
    ])
    if hashlib.sha256(cert).hexdigest() != expected:
        raise ValueError('The keystore certificate does not match the registered release identity')
    return ('--ks-key-alias', args.key_alias, '--ks-pass', f'env:{STORE_PASS_ENV}',
            '--key-pass', f'env:{KEY_PASS_ENV}')


def build(args):
    base = args.upstream.resolve(strict=True)
    apktool = args.apktool.resolve(strict=True)
    sdk = args.build_tools.resolve(strict=True)
    keystore = args.keystore.resolve(strict=True)
    if hashlib.sha256(base.read_bytes()).hexdigest() != UPSTREAM_HASH:
        raise ValueError("Upstream APK checksum did not match F-Droid 3.6.1")

    signer = signing_options(args, keystore)
    work = Path(tempfile.mkdtemp(prefix="pysolfc-release-" if args.formal else "pysolfc-qa-"))
    print(f"Working directory: {work}", flush=True)
    decoded = work / "decoded"
    framework = work / "framework"
    run("java", "-jar", apktool, "d", "--no-assets", base,
        "-p", framework, "-o", decoded)
    defer_sdl_resume_until_surface_exists(decoded)
    with ZipFile(base) as original:
        payload = application_tar(original.read(PRIVATE_TAR), formal=args.formal)
    configure_resources(decoded, hashlib.sha256(payload).hexdigest(), formal=args.formal)

    assets = decoded / "assets"
    assets.mkdir(exist_ok=True)
    with ZipFile(base) as original:
        for name in original.namelist():
            if not name.startswith("assets/") or name == PRIVATE_TAR or name.endswith("/"):
                continue
            target = decoded / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read(name))
    (decoded / PRIVATE_TAR).write_bytes(payload)

    unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
    run("java", "-jar", apktool, "b", "-p", framework,
        "--aapt", sdk / "aapt2.exe", "-o", unsigned, decoded)
    run(sdk / "zipalign.exe", "-P", "16", "4", unsigned, aligned)
    run(sdk / "apksigner.bat", "sign", "--ks", keystore, *signer,
        "--v4-signing-enabled", "false",
        "--out", args.output.resolve(), aligned, signing=args.formal)
    run(sdk / "apksigner.bat", "verify", "--print-certs", args.output.resolve())
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("upstream", "apktool", "build-tools", "keystore", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument('--formal', action='store_true')
    parser.add_argument('--key-alias')
    parser.add_argument('--signer-sha256')
    build(parser.parse_args())
