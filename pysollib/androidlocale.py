"""System language selection for the Android application."""

import logging


def language_for_primary(language):
    primary = (language or "").replace("_", "-").split("-", 1)[0]
    return "zh_CN" if primary.lower() == "zh" else "en"


def system_primary_language():
    from jnius import autoclass, cast

    try:
        version = autoclass("android.os.Build$VERSION").SDK_INT
        if version >= 33:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            manager = activity.getSystemService("locale")
            manager = cast("android.app.LocaleManager", manager)
            locales = manager.getSystemLocales()
        else:
            resources = autoclass("android.content.res.Resources").getSystem()
            configuration = resources.getConfiguration()
            if version < 24:
                return configuration.locale.getLanguage()
            locales = configuration.getLocales()

        if not locales.isEmpty():
            return locales.get(0).toLanguageTag()
    except Exception:
        logging.warning("Unable to read the Android system language",
                        exc_info=True)
    return None
