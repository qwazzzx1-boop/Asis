#!/usr/bin/env bash
set -e

echo "=== Сборка Voice Assistant APK через Buildozer ==="

python3 --version

echo "Установка совместимого Cython 0.29.33 и Buildozer..."
pip install --upgrade "Cython==0.29.33" virtualenv
pip install --upgrade git+https://github.com/kivy/buildozer.git

echo "Очистка и запуск сборки APK..."
buildozer clean
buildozer -v android debug

echo "=== Готово! Файл APK собран в папке bin/ ==="
ls -lh bin/*.apk
