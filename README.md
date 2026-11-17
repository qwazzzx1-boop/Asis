# Voice Assistant — Android

Мобильная версия голосового ассистента на Kivy для Android.

## Что работает

- 💬 Чат-интерфейс с ассистентом (Ollama / Anthropic / OpenRouter)
- 🎤 Голосовой ввод через встроенный Android SpeechRecognizer
- 📱 Запуск Android-приложений по русским сокращениям (тг, дс, ют, вк...)
- 🌐 Открытие сайтов + автоматический фоллбэк на веб-версию
- 📨 Отправка сообщений в Telegram/Discord через ботов
- ⚙ Настройки (провайдер, модель, URL Ollama, API-ключи)

## Как собрать APK

### Вариант 1: Linux / WSL (рекомендуется)

```bash
# 1. Установите зависимости
sudo apt update
sudo apt install python3-pip python3-venv git zip unzip openjdk-17-jdk autoconf automake libtool pkg-config
pip install buildozer cython

# 2. Скопируйте папку voice-assistant-android на Linux/WSL

# 3. Перейдите в папку проекта
cd voice-assistant-android

# 4. Соберите APK (первая сборка скачает Android SDK/NDK — ~2GB)
buildozer android debug

# 5. APK будет в bin/voiceassistant-1.0.0-arm64-v8a_armeabi-v7a-debug.apk
```

### Вариант 2: Google Colab (без установки)

```python
# В новом Colab notebook:
!pip install buildozer cython
!sudo apt install -y git zip unzip openjdk-17-jdk autoconf automake libtool pkg-config

# Загрузите ZIP с проектом через Files panel, затем:
!unzip voice-assistant-android.zip -d /content/project
%cd /content/project
!buildozer android debug

# Скачайте APK из bin/
```

## Настройка Ollama для работы с телефоном

Ассистент подключается к **Ollama на вашем ПК** по сети.

1. На **ПК** запустите Ollama с доступом из сети:
   ```
   set OLLAMA_HOST=0.0.0.0
   ollama serve
   ```

2. Узнайте **IP адрес ПК** в локальной сети:
   ```
   ipconfig
   ```
   Пример: `192.168.0.100`

3. В приложении на телефоне откройте **⚙ Настройки** и укажите:
   ```
   Ollama URL: http://192.168.0.100:11434
   ```

4. ПК и телефон должны быть **в одной Wi-Fi сети**

## Поддерживаемые сокращения

| Сокращение | Приложение |
|-----------|-----------|
| тг, телега | Telegram |
| дс, дискорд | Discord |
| ют, ютуб | YouTube |
| вк | VKontakte |
| инста | Instagram |
| тикток | TikTok |
| хром | Chrome |
| стим | Steam |
| спотифай | Spotify |
| майн | Minecraft |
| роблокс | Roblox |
| бравл | Brawl Stars |
| чатгпт | ChatGPT |
| + ещё 90+ | ... |


## Работа через OpenRouter (без включённого ПК)

1. Создайте API-ключ в личном кабинете OpenRouter: https://openrouter.ai/keys
2. Откройте настройки приложения на телефоне.
3. В поле «Провайдер» укажите `openrouter`.
4. В поле «Модель» укажите идентификатор модели из каталога OpenRouter, например `openai/gpt-4o-mini`.
5. Вставьте свой OpenRouter API-ключ и сохраните настройки.

После этого запросы отправляются напрямую из приложения в OpenRouter. Компьютер и Ollama для этого не нужны. Для Tool Calling выбирайте модель, которая поддерживает вызов инструментов. Использование OpenRouter может тарифицироваться по токенам согласно цене выбранной модели.

API-ключ сохраняется в приватной папке данных приложения. В текущей реализации файл credentials.json не шифруется отдельно, поэтому не распространяйте APK с уже сохранённым личным ключом.
