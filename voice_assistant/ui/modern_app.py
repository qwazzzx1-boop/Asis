"""Modern, Android-friendly Kivy interface for ЭХО.

Uses text labels instead of emoji/icon-font glyphs so controls render on
Android devices without depending on a particular emoji font.
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from voice_assistant.config import Settings
from voice_assistant.runtime import create_service


BG = (0.035, 0.047, 0.075, 1)
PANEL = (0.075, 0.09, 0.13, 1)
CARD = (0.10, 0.12, 0.17, 1)
ACCENT = (0.42, 0.48, 0.98, 1)
TEXT = (0.92, 0.94, 0.99, 1)
MUTED = (0.56, 0.61, 0.72, 1)
GREEN = (0.34, 0.78, 0.59, 1)
RED = (0.95, 0.38, 0.40, 1)


class AsyncWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.closed = False
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine) -> Future:
        if self.closed:
            coroutine.close()
            raise RuntimeError("Фоновый обработчик остановлен")
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
        if not self.thread.is_alive():
            self.loop.close()


class Surface(BoxLayout):
    def __init__(self, color=CARD, radius=18, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*color)
            self._shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._sync_shape, size=self._sync_shape)

    def _sync_shape(self, *_):
        self._shape.pos = self.pos
        self._shape.size = self.size


class ChatMessage(Surface):
    def __init__(self, text, user=False, **kwargs):
        super().__init__(
            color=(0.16, 0.19, 0.31, 1) if user else CARD,
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(14), dp(10)),
            spacing=dp(5),
            radius=16,
            **kwargs,
        )
        self.user = user
        self.sender = Label(
            text="ВЫ" if user else "ЭХО",
            color=(0.73, 0.78, 1, 1) if user else GREEN,
            bold=True,
            font_size="11sp",
            halign="left",
            size_hint_y=None,
            height=dp(18),
        )
        self.body = Label(
            text=str(text),
            color=TEXT,
            font_size="15sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            text_size=(Window.width - dp(76), None),
        )
        self.body.bind(texture_size=self._resize_body)
        self.add_widget(self.sender)
        self.add_widget(self.body)
        self._resize_body(self.body, self.body.texture_size)

    def _resize_body(self, label, size):
        label.height = max(dp(22), size[1] + dp(3))
        self.height = label.height + dp(43)


class RootWidget(BoxLayout):
    status_text = StringProperty("ЗАПУСК")

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(10), padding=(dp(16), dp(12)), **kwargs)
        self.settings = Settings.load()
        self.worker = AsyncWorker()
        self.service = None
        self._build()
        Clock.schedule_once(self._init_service, 0.25)

    def _build(self):
        self.clear_widgets()
        self.add_widget(self._header())

        welcome = Surface(
            orientation="vertical",
            size_hint_y=None,
            height=dp(106),
            padding=dp(16),
            spacing=dp(5),
            color=PANEL,
        )
        welcome.add_widget(Label(
            text="ТВОЙ ЛИЧНЫЙ AI-АССИСТЕНТ",
            color=ACCENT,
            bold=True,
            font_size="11sp",
            halign="left",
            size_hint_y=None,
            height=dp(18),
        ))
        welcome.add_widget(Label(
            text="Чем займёмся?",
            color=TEXT,
            bold=True,
            font_size="23sp",
            halign="left",
            valign="middle",
        ))
        welcome.add_widget(Label(
            text="Напиши сообщение или используй голосовой ввод",
            color=MUTED,
            font_size="12sp",
            halign="left",
            size_hint_y=None,
            height=dp(20),
        ))
        self.add_widget(welcome)

        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), scroll_type=["bars", "content"])
        self.chat = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(9), padding=(0, dp(4)))
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)
        self.add_widget(self.scroll)

        composer = Surface(
            orientation="vertical",
            size_hint_y=None,
            height=dp(112),
            padding=dp(10),
            spacing=dp(8),
            color=PANEL,
        )
        self.input = TextInput(
            hint_text="Сообщение для ЭХО...",
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            padding=(dp(12), dp(12)),
            font_size="15sp",
            background_normal="",
            background_active="",
            background_color=CARD,
            foreground_color=TEXT,
            hint_text_color=MUTED,
            cursor_color=ACCENT,
        )
        self.input.bind(on_text_validate=lambda *_: self.send_message())
        composer.add_widget(self.input)

        actions = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
        voice = self._button("ГОЛОС", CARD, self.start_voice)
        send = self._button("ОТПРАВИТЬ", ACCENT, self.send_message)
        actions.add_widget(voice)
        actions.add_widget(send)
        composer.add_widget(actions)
        self.add_widget(composer)

        self._system("ЭХО готовится к работе. Подключи OpenRouter в настройках, если он ещё не выбран.")

    def _header(self):
        header = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        brand = BoxLayout(orientation="vertical", spacing=0)
        brand.add_widget(Label(text="ЭХО", color=TEXT, bold=True, font_size="23sp", halign="left", size_hint_y=None, height=dp(29)))
        brand.add_widget(Label(text="VOICE ASSISTANT", color=MUTED, font_size="9sp", halign="left", size_hint_y=None, height=dp(14)))
        header.add_widget(brand)
        header.add_widget(Label(text=self.status_text, color=GREEN, font_size="10sp", bold=True, halign="right"))
        header.add_widget(self._button("НАСТРОЙКИ", CARD, self.open_settings, width=dp(112)))
        return header

    def _button(self, text, color, callback, width=None):
        button = Button(
            text=text,
            size_hint_x=None if width else 1,
            width=width or 0,
            background_normal="",
            background_down="",
            background_color=color,
            color=TEXT,
            bold=True,
            font_size="11sp",
        )
        button.bind(on_release=lambda *_: callback())
        return button

    def _init_service(self, *_):
        try:
            async def approve(action):
                result = {"approved": False}
                done = threading.Event()

                def show(_dt):
                    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
                    label = Label(text="ЭХО запрашивает разрешение:\n\n" + str(action)[:600], color=TEXT)
                    box.add_widget(label)
                    buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
                    popup = Popup(title="Подтверждение", content=box, size_hint=(0.9, 0.42))
                    def finish(value):
                        result["approved"] = value
                        done.set()
                        popup.dismiss()
                    no = self._button("ОТКЛОНИТЬ", CARD, lambda: finish(False))
                    yes = self._button("РАЗРЕШИТЬ", ACCENT, lambda: finish(True))
                    buttons.add_widget(no)
                    buttons.add_widget(yes)
                    box.add_widget(buttons)
                    popup.bind(on_dismiss=lambda *_: (done.set() if not done.is_set() else None))
                    popup.open()

                Clock.schedule_once(show, 0)
                await asyncio.to_thread(done.wait, 120)
                return result["approved"]

            self.service = create_service(self.settings, approve)
            self.status_text = self.settings.provider.upper() + " • ГОТОВ"
        except Exception as exc:
            self.service = None
            self.status_text = "НЕТ ПОДКЛЮЧЕНИЯ"
            self._system("Не удалось запустить ассистента: " + str(exc))

    @mainthread
    def _system(self, text):
        item = Label(
            text=str(text),
            color=MUTED,
            font_size="12sp",
            halign="center",
            valign="middle",
            size_hint_y=None,
            text_size=(Window.width - dp(48), None),
        )
        item.bind(texture_size=lambda w, size: setattr(w, "height", size[1] + dp(14)))
        self.chat.add_widget(item)
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.08)

    @mainthread
    def _message(self, text, user=False):
        self.chat.add_widget(ChatMessage(text, user=user))
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.08)

    def send_message(self):
        text = self.input.text.strip()
        if not text:
            return
        self.input.text = ""
        self._message(text, user=True)
        if not self.service:
            self._system("Нет активного провайдера. Открой настройки и выбери OpenRouter.")
            return
        self.status_text = "ОТВЕЧАЮ..."
        future = self.worker.submit(self.service.handle_text(text))
        future.add_done_callback(self._response_done)

    def _response_done(self, future: Future):
        try:
            answer = future.result()
            self._message(answer or "Модель вернула пустой ответ.")
            self.status_text = self.settings.provider.upper() + " • ГОТОВ"
        except Exception as exc:
            self._message("Ошибка запроса: " + str(exc))
            self.status_text = "ОШИБКА СЕТИ"

    def open_settings(self):
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(9))
        body.add_widget(Label(text="ПРОВАЙДЕР", color=MUTED, size_hint_y=None, height=dp(20), halign="left"))
        provider = Spinner(
            text=self.settings.provider,
            values=("openrouter", "ollama", "anthropic"),
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=CARD,
            color=TEXT,
        )
        body.add_widget(provider)

        body.add_widget(Label(text="МОДЕЛЬ", color=MUTED, size_hint_y=None, height=dp(20), halign="left"))
        model = TextInput(
            text=self.settings.model,
            multiline=False,
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=CARD,
            foreground_color=TEXT,
            cursor_color=ACCENT,
        )
        body.add_widget(model)

        body.add_widget(Label(text="OPENROUTER API KEY (оставь пустым, чтобы не менять)", color=MUTED, size_hint_y=None, height=dp(20), halign="left"))
        key = TextInput(
            text="",
            hint_text="sk-or-...",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=CARD,
            foreground_color=TEXT,
            cursor_color=ACCENT,
        )
        body.add_widget(key)

        body.add_widget(Label(text="OLLAMA URL (нужно только для Ollama)", color=MUTED, size_hint_y=None, height=dp(20), halign="left"))
        ollama_url = TextInput(
            text=self.settings.ollama_url,
            multiline=False,
            size_hint_y=None,
            height=dp(42),
            background_normal="",
            background_color=CARD,
            foreground_color=TEXT,
        )
        body.add_widget(ollama_url)

        save = Button(
            text="СОХРАНИТЬ И ПОДКЛЮЧИТЬ",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=ACCENT,
            color=TEXT,
            bold=True,
        )
        popup = Popup(title="Настройки ЭХО", content=body, size_hint=(0.92, 0.88), auto_dismiss=True)

        def on_save(*_):
            selected = provider.text.strip().lower()
            self.settings.provider = selected
            self.settings.model = model.text.strip() or ("openai/gpt-4o-mini" if selected == "openrouter" else "qwen2.5:7b")
            self.settings.ollama_url = ollama_url.text.strip() or "http://192.168.0.100:11434"
            self.settings.save()
            if key.text.strip():
                from voice_assistant.security.credentials import CredentialStore
                CredentialStore().set("openrouter-api-key", key.text.strip())
            self.service = None
            self._init_service()
            popup.dismiss()
            self._system("Настройки сохранены. Провайдер: " + selected.upper())

        save.bind(on_release=on_save)
        body.add_widget(save)
        popup.open()

    def start_voice(self):
        if platform != "android":
            self._system("Голосовой ввод доступен в Android-версии. Пока используй текст.")
            return
        try:
            from jnius import autoclass
            from android.activity import bind
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            Activity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
            bind(on_activity_result=self._speech_result)
            Activity.mActivity.startActivityForResult(intent, 1001)
        except Exception as exc:
            self._system("Голосовой ввод недоступен: " + str(exc))

    def _speech_result(self, request_code, result_code, intent):
        if request_code != 1001 or intent is None:
            return
        try:
            from jnius import autoclass
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if results and results.size():
                text = results.get(0)
                if text:
                    self.input.text = text
                    self.send_message()
        except Exception as exc:
            self._system("Не удалось распознать речь: " + str(exc))


class VoiceAssistantApp(App):
    def build(self):
        Window.clearcolor = BG
        if platform == "android":
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.INTERNET, Permission.RECORD_AUDIO])
            except Exception:
                pass
        return RootWidget()

    def on_stop(self):
        if self.root and getattr(self.root, "worker", None):
            self.root.worker.close()


if __name__ == "__main__":
    VoiceAssistantApp().run()
