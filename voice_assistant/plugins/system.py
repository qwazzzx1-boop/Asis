from __future__ import annotations
import asyncio
import webbrowser
from pathlib import Path
from voice_assistant.security.policy import ApprovalGate, RiskLevel

# ---------------------------------------------------------------------------
# Словарь Android-пакетов для русских сокращений
# ---------------------------------------------------------------------------
_ANDROID_PACKAGES: dict[str, str] = {
    # Мессенджеры
    "тг": "org.telegram.messenger",
    "телега": "org.telegram.messenger",
    "телеграм": "org.telegram.messenger",
    "телеграмм": "org.telegram.messenger",
    "telegram": "org.telegram.messenger",
    "дс": "com.discord",
    "дискорд": "com.discord",
    "discord": "com.discord",
    "вотсап": "com.whatsapp",
    "ватсап": "com.whatsapp",
    "whatsapp": "com.whatsapp",
    "вайбер": "com.viber.voip",
    "viber": "com.viber.voip",
    "скайп": "com.skype.raider",
    "skype": "com.skype.raider",
    "зум": "us.zoom.videomeetings",
    "zoom": "us.zoom.videomeetings",
    "слак": "com.Slack",
    "slack": "com.Slack",
    "сигнал": "org.thoughtcrime.securesms",
    "signal": "org.thoughtcrime.securesms",

    # Соцсети
    "вк": "com.vkontakte.android",
    "вконтакте": "com.vkontakte.android",
    "vk": "com.vkontakte.android",
    "инста": "com.instagram.android",
    "инстаграм": "com.instagram.android",
    "instagram": "com.instagram.android",
    "тикток": "com.zhiliaoapp.musically",
    "tiktok": "com.zhiliaoapp.musically",
    "твиттер": "com.twitter.android",
    "twitter": "com.twitter.android",
    "х": "com.twitter.android",
    "фб": "com.facebook.katana",
    "фейсбук": "com.facebook.katana",
    "facebook": "com.facebook.katana",
    "реддит": "com.reddit.frontpage",
    "reddit": "com.reddit.frontpage",
    "пинтерест": "com.pinterest",
    "pinterest": "com.pinterest",

    # Видео / Музыка
    "ют": "com.google.android.youtube",
    "ютуб": "com.google.android.youtube",
    "youtube": "com.google.android.youtube",
    "ютуб музыка": "com.google.android.apps.youtube.music",
    "youtube music": "com.google.android.apps.youtube.music",
    "спотифай": "com.spotify.music",
    "spotify": "com.spotify.music",
    "яндекс музыка": "com.yandex.music",
    "я музыка": "com.yandex.music",
    "звук": "com.zvooq.openplay",

    # Браузеры
    "хром": "com.android.chrome",
    "chrome": "com.android.chrome",
    "гугл": "com.android.chrome",
    "фф": "org.mozilla.firefox",
    "фаерфокс": "org.mozilla.firefox",
    "firefox": "org.mozilla.firefox",
    "опера": "com.opera.browser",
    "opera": "com.opera.browser",
    "яб": "com.yandex.browser",
    "яндекс браузер": "com.yandex.browser",
    "эдж": "com.microsoft.emmx",
    "edge": "com.microsoft.emmx",

    # Google apps
    "гугл карты": "com.google.android.apps.maps",
    "карты": "com.google.android.apps.maps",
    "maps": "com.google.android.apps.maps",
    "гмейл": "com.google.android.gm",
    "gmail": "com.google.android.gm",
    "почта": "com.google.android.gm",
    "гугл диск": "com.google.android.apps.docs",
    "drive": "com.google.android.apps.docs",
    "фото": "com.google.android.apps.photos",
    "photos": "com.google.android.apps.photos",
    "переводчик": "com.google.android.apps.translate",
    "translate": "com.google.android.apps.translate",

    # Игры / Платформы
    "стим": "com.valvesoftware.android.steam.community",
    "steam": "com.valvesoftware.android.steam.community",
    "майнкрафт": "com.mojang.minecraftpe",
    "майн": "com.mojang.minecraftpe",
    "minecraft": "com.mojang.minecraftpe",
    "роблокс": "com.roblox.client",
    "roblox": "com.roblox.client",
    "бравл старс": "com.supercell.brawlstars",
    "бравл": "com.supercell.brawlstars",
    "клеш рояль": "com.supercell.clashroyale",
    "клеш": "com.supercell.clashroyale",
    "геншин": "com.miHoYo.GenshinImpact",
    "genshin": "com.miHoYo.GenshinImpact",

    # Утилиты
    "калькулятор": "com.google.android.calculator",
    "calculator": "com.google.android.calculator",
    "камера": "com.android.camera",
    "camera": "com.android.camera",
    "часы": "com.google.android.deskclock",
    "clock": "com.google.android.deskclock",
    "настройки": "com.android.settings",
    "settings": "com.android.settings",
    "файлы": "com.google.android.documentsui",
    "files": "com.google.android.documentsui",

    # Другое
    "обс": "com.obsproject.obs",
    "obs": "com.obsproject.obs",
    "чатгпт": "com.openai.chatgpt",
    "chatgpt": "com.openai.chatgpt",
    "notion": "notion.id",
    "notion": "notion.id",
}

# Веб-фоллбэки для приложений
_WEB_FALLBACK: dict[str, str] = {
    "тг": "https://web.telegram.org",
    "телеграм": "https://web.telegram.org",
    "дс": "https://discord.com/app",
    "дискорд": "https://discord.com/app",
    "ют": "https://youtube.com",
    "ютуб": "https://youtube.com",
    "вк": "https://vk.com",
    "вконтакте": "https://vk.com",
    "инста": "https://instagram.com",
    "инстаграм": "https://instagram.com",
    "тикток": "https://tiktok.com",
    "спотифай": "https://open.spotify.com",
    "реддит": "https://reddit.com",
    "гугл": "https://google.com",
    "гитхаб": "https://github.com",
    "github": "https://github.com",
    "твич": "https://twitch.tv",
    "twitch": "https://twitch.tv",
    "чатгпт": "https://chat.openai.com",
    "chatgpt": "https://chat.openai.com",
}


def _is_android() -> bool:
    try:
        import android  # type: ignore[import]
        return True
    except ImportError:
        return False


def _launch_android_package(package: str) -> bool:
    """Launch an Android app by package name using an intent."""
    try:
        from jnius import autoclass  # type: ignore[import]
        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        pm = context.getPackageManager()
        launch_intent = pm.getLaunchIntentForPackage(package)
        if launch_intent is None:
            return False
        launch_intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(launch_intent)
        return True
    except Exception:
        return False


def _open_url_android(url: str) -> bool:
    """Open a URL using Android intent."""
    try:
        from jnius import autoclass  # type: ignore[import]
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return True
    except Exception:
        return False


class SystemTools:
    def __init__(self, gate: ApprovalGate):
        self.gate = gate

    async def launch(self, executable: str, args: list[str] | tuple[str, ...] = ()) -> str:
        """Запуск приложения по имени/сокращению."""
        query = " ".join(executable.casefold().split())

        # Ищем Android-пакет по алиасу
        package = _ANDROID_PACKAGES.get(query)

        if package and _is_android():
            await self.gate.check(f"Запустить {executable} ({package})", RiskLevel.CONFIRM)
            if _launch_android_package(package):
                return f"Запущено: {executable}"
            # Пакет не установлен — пробуем веб-версию
            url = _WEB_FALLBACK.get(query)
            if url:
                _open_url_android(url)
                return f"Приложение не установлено, открыта веб-версия: {url}"
            return f"Приложение {executable} ({package}) не установлено на устройстве"

        # Не Android или нет пакета — пробуем веб
        url = _WEB_FALLBACK.get(query)
        if url:
            await self.gate.check(f"Открыть {url}", RiskLevel.SAFE)
            if _is_android():
                _open_url_android(url)
            else:
                await asyncio.to_thread(webbrowser.open, url)
            return f"Открыто: {url}"

        return f"Не могу найти приложение '{executable}'. Попробуйте уточнить название."

    async def open_website(self, url: str) -> str:
        """Открыть URL в браузере."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Допускаются только HTTP(S) адреса")
        await self.gate.check(f"Открыть сайт {parsed.netloc}", RiskLevel.SAFE)
        if _is_android():
            _open_url_android(url)
        else:
            await asyncio.to_thread(webbrowser.open, url)
        return f"Открыт сайт: {parsed.netloc}"

    async def open_app_or_website(self, name: str) -> str:
        """Универсальный запуск: пробует приложение, затем веб."""
        return await self.launch(name)

    def list_available_apps(self) -> str:
        """Список доступных сокращений."""
        categories = {
            "Мессенджеры": ["тг", "дс", "вотсап", "вайбер", "скайп", "зум", "слак"],
            "Соцсети": ["вк", "инста", "тикток", "фб", "реддит"],
            "Видео/Музыка": ["ют", "спотифай", "я музыка"],
            "Браузеры": ["хром", "фф", "опера", "яб", "эдж"],
            "Игры": ["стим", "майн", "роблокс", "бравл", "геншин"],
        }
        lines = []
        for cat, aliases in categories.items():
            lines.append(f"{cat}: {', '.join(aliases)}")
        return "\n".join(lines)
