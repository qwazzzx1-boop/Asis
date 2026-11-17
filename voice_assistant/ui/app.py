"""
Voice Assistant — Kivy/Android UI
Chat interface with voice input, settings, and theme support.
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.utils import platform

from voice_assistant.config import Settings
from voice_assistant.runtime import create_service


# ---------------------------------------------------------------------------
# KV language layout
# ---------------------------------------------------------------------------
KV = '''
#:import dp kivy.metrics.dp

<ChatBubble@BoxLayout>:
    size_hint_y: None
    height: self.minimum_height
    padding: dp(8), dp(4)

<MessageLabel@Label>:
    size_hint_y: None
    text_size: self.width - dp(24), None
    height: self.texture_size[1] + dp(16)
    padding: dp(12), dp(8)
    markup: True
    halign: 'left'
    valign: 'top'

<RootWidget>:
    orientation: 'vertical'

    # Header bar
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        padding: dp(12), dp(8)
        canvas.before:
            Color:
                rgba: 0.15, 0.15, 0.22, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: '🤖 Voice Assistant'
            font_size: sp(20)
            bold: True
            color: 0.78, 0.82, 1, 1
            halign: 'left'
            text_size: self.size
            valign: 'center'

        Label:
            id: status_label
            text: root.status_text
            font_size: sp(13)
            color: 0.5, 0.75, 0.5, 1
            size_hint_x: 0.4
            halign: 'right'
            text_size: self.size
            valign: 'center'

        Button:
            text: '⚙'
            font_size: sp(22)
            size_hint_x: None
            width: dp(48)
            background_color: 0, 0, 0, 0
            color: 0.7, 0.7, 0.85, 1
            on_release: root.open_settings()

    # Chat area
    ScrollView:
        id: scroll_view
        do_scroll_x: False
        bar_width: dp(4)
        bar_color: 0.4, 0.4, 0.6, 0.6

        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(8)
            spacing: dp(6)

    # Input area
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        padding: dp(8), dp(4)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 0.12, 0.12, 0.18, 1
            Rectangle:
                pos: self.pos
                size: self.size

        TextInput:
            id: text_input
            hint_text: 'Введите запрос...'
            multiline: False
            font_size: sp(16)
            background_color: 0.2, 0.2, 0.28, 1
            foreground_color: 0.9, 0.9, 0.95, 1
            hint_text_color: 0.5, 0.5, 0.6, 1
            cursor_color: 0.6, 0.65, 1, 1
            padding: dp(12), dp(10)
            on_text_validate: root.send_message()

        Button:
            text: '🎤'
            font_size: sp(22)
            size_hint_x: None
            width: dp(48)
            background_color: 0.25, 0.25, 0.4, 1
            on_press: root.start_voice()
            on_release: root.stop_voice()

        Button:
            text: '➤'
            font_size: sp(22)
            size_hint_x: None
            width: dp(48)
            background_color: 0.3, 0.35, 0.65, 1
            on_release: root.send_message()
'''


# ---------------------------------------------------------------------------
# Async worker thread
# ---------------------------------------------------------------------------
class AsyncWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Root widget
# ---------------------------------------------------------------------------
class RootWidget(BoxLayout):
    status_text = StringProperty('Готов')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = Settings.load()
        self.worker = AsyncWorker()
        self.service = None
        self._recording = False
        Clock.schedule_once(self._init_service, 0.5)

    def _init_service(self, dt=None):
        try:
            async def approve(action: str) -> bool:
                # На Android пока автоподтверждение для SAFE/CONFIRM
                return True
            self.service = create_service(self.settings, approve)
            self._update_status('Подключено ✓')
            self._add_system_message('Ассистент готов к работе! Введите запрос или нажмите 🎤')
        except Exception as e:
            self._update_status('Ошибка подключения')
            self._add_system_message(f'Ошибка инициализации: {e}\n\nОткройте настройки (⚙) и проверьте провайдера, модель и API-ключ.')

    @mainthread
    def _update_status(self, text: str):
        self.status_text = text

    @mainthread
    def _add_message(self, text: str, is_user: bool = False):
        chat_box = self.ids.chat_box
        scroll = self.ids.scroll_view

        lbl = Label(
            text=text,
            markup=True,
            size_hint_y=None,
            halign='right' if is_user else 'left',
            valign='top',
            padding=(16, 10),
        )
        lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val - 24, None)))
        lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1] + 20))

        if is_user:
            lbl.color = (0.85, 0.9, 1, 1)
        else:
            lbl.color = (0.8, 0.85, 0.75, 1)

        chat_box.add_widget(lbl)
        Clock.schedule_once(lambda dt: setattr(scroll, 'scroll_y', 0), 0.1)

    @mainthread
    def _add_system_message(self, text: str):
        chat_box = self.ids.chat_box
        scroll = self.ids.scroll_view

        lbl = Label(
            text=f'[color=8888aa]{text}[/color]',
            markup=True,
            size_hint_y=None,
            halign='center',
            valign='top',
            padding=(16, 10),
            font_size='13sp',
        )
        lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val - 24, None)))
        lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1] + 16))

        chat_box.add_widget(lbl)
        Clock.schedule_once(lambda dt: setattr(scroll, 'scroll_y', 0), 0.1)

    @mainthread
    def _add_error(self, text: str):
        self._add_message(f'[color=ff5555]⚠ {text}[/color]')

    def send_message(self):
        text_input = self.ids.text_input
        text = text_input.text.strip()
        if not text:
            return
        text_input.text = ''

        self._add_message(f'[b]Вы:[/b] {text}', is_user=True)

        if not self.service:
            self._add_error('Сервис не подключён. Проверьте настройки (⚙)')
            return

        self._update_status('Думаю...')
        future = self.worker.submit(self.service.handle_text(text))
        future.add_done_callback(self._on_response)

    def _on_response(self, future: Future):
        try:
            result = future.result()
            self._add_message(f'[b]Ассистент:[/b] {result}')
            self._update_status('Готов')
        except Exception as e:
            self._add_error(str(e) or type(e).__name__)
            self._update_status('Ошибка')

    # ----- Voice Input -----
    def start_voice(self):
        self._recording = True
        self._update_status('Слушаю... 🎤')

        if platform == 'android':
            self._start_android_speech()
        else:
            self._add_system_message('Голосовой ввод доступен только на Android. Используйте текстовый ввод.')
            self._update_status('Готов')

    def stop_voice(self):
        self._recording = False

    def _start_android_speech(self):
        """Use Android SpeechRecognizer via Intent."""
        try:
            from jnius import autoclass  # type: ignore[import]
            Intent = autoclass('android.content.Intent')
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'ru-RU')
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, 'Говорите...')

            activity.startActivityForResult(intent, 1001)

            # We'll handle the result via the activity callback
            from android.activity import bind as activity_bind  # type: ignore[import]
            activity_bind(on_activity_result=self._on_speech_result)
        except Exception as e:
            self._add_error(f'Ошибка распознавания речи: {e}')
            self._update_status('Готов')

    def _on_speech_result(self, request_code, result_code, intent):
        if request_code != 1001 or intent is None:
            self._update_status('Готов')
            return
        try:
            from jnius import autoclass  # type: ignore[import]
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')
            results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)  # type: ignore
            if results and results.size() > 0:
                text = results.get(0)
                if text:
                    self._add_message(f'[b]Вы (голос):[/b] {text}', is_user=True)
                    if self.service:
                        self._update_status('Думаю...')
                        future = self.worker.submit(self.service.handle_text(text))
                        future.add_done_callback(self._on_response)
                    return
            self._add_system_message('Речь не распознана')
        except Exception as e:
            self._add_error(f'Ошибка: {e}')
        self._update_status('Готов')

    # ----- Settings -----
    def open_settings(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Provider
        content.add_widget(Label(text='Провайдер:', size_hint_y=None, height=30, halign='left'))
        provider_input = TextInput(text=self.settings.provider, multiline=False, size_hint_y=None, height=40)
        content.add_widget(provider_input)

        # Model
        content.add_widget(Label(text='Модель:', size_hint_y=None, height=30, halign='left'))
        model_input = TextInput(text=self.settings.model, multiline=False, size_hint_y=None, height=40)
        content.add_widget(model_input)

        # Ollama URL
        content.add_widget(Label(text='Ollama URL (IP вашего ПК):', size_hint_y=None, height=30, halign='left'))
        url_input = TextInput(text=self.settings.ollama_url, multiline=False, size_hint_y=None, height=40)
        content.add_widget(url_input)

        # API Key
        content.add_widget(Label(text='API ключ (для OpenRouter или Anthropic):', size_hint_y=None, height=30, halign='left'))
        api_key_input = TextInput(text='', multiline=False, password=True, size_hint_y=None, height=40, hint_text='Вставьте ключ выбранного провайдера')
        content.add_widget(api_key_input)

        # Spacer
        content.add_widget(BoxLayout())

        # Save button
        save_btn = Button(text='💾 Сохранить', size_hint_y=None, height=50,
                         background_color=(0.3, 0.5, 0.3, 1))

        popup = Popup(title='⚙ Настройки', content=BoxLayout(orientation='vertical'),
                     size_hint=(0.9, 0.8))
        popup.content.add_widget(content)
        popup.content.add_widget(save_btn)

        def on_save(instance):
            self.settings.provider = provider_input.text.strip() or 'ollama'
            self.settings.model = model_input.text.strip() or 'qwen2.5:7b'
            self.settings.ollama_url = url_input.text.strip() or 'http://192.168.0.100:11434'
            self.settings.save()

            # Save API key if provided
            api_key = api_key_input.text.strip()
            if api_key:
                from voice_assistant.security.credentials import CredentialStore
                if self.settings.provider == 'openrouter':
                    CredentialStore().set('openrouter-api-key', api_key)
                elif self.settings.provider == 'anthropic':
                    CredentialStore().set('anthropic-api-key', api_key)

            # Reinitialize service
            self._init_service()
            popup.dismiss()
            self._add_system_message('Настройки сохранены ✓')

        save_btn.bind(on_release=on_save)
        popup.open()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class VoiceAssistantApp(App):
    def build(self):
        Builder.load_string(KV)
        Window.clearcolor = (0.1, 0.1, 0.15, 1)

        # Request Android permissions
        if platform == 'android':
            self._request_permissions()

        return RootWidget()

    def _request_permissions(self):
        try:
            from android.permissions import request_permissions, Permission  # type: ignore[import]
            request_permissions([
                Permission.INTERNET,
                Permission.RECORD_AUDIO,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        except ImportError:
            pass

    def on_stop(self):
        root = self.root
        if root and hasattr(root, 'worker'):
            root.worker.close()


if __name__ == '__main__':
    VoiceAssistantApp().run()
