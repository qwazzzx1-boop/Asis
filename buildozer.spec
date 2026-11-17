[app]

# Title of your application
title = Voice Assistant

# Package name
package.name = voiceassistant

# Package domain (needed for Android)
package.domain = com.voiceassistant

# Source directory where main.py is located
source.dir = .

# Source files to include
source.include_exts = py,png,jpg,kv,atlas,json,toml

# Application versioning
version = 1.0.0

# Application requirements
# NOTE: pyjnius is included automatically for android
requirements = python3,kivy,openssl

# Supported orientations (portrait, landscape, all)
orientation = portrait

# Android permissions
android.permissions = INTERNET,RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE

# Android API to use for the build
android.api = 33

# Minimum API your APK will support
android.minapi = 24

# Android NDK version
android.ndk = 25b

# Android SDK version  
android.sdk = 33

# Architecture to build for (arm64-v8a for modern 64-bit devices, prevents 32-bit build failures)
android.archs = arm64-v8a

# Use develop branch of python-for-android for latest compatibility fixes
p4a.branch = develop

# Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# Android app theme
android.apptheme = "@android:style/Theme.NoTitleBar"

# Fullscreen mode (0 = no, 1 = yes)
fullscreen = 0

# Icon of the application
#icon.filename = %(source.dir)s/icon.png

# Presplash of the application
#presplash.filename = %(source.dir)s/presplash.png

# Presplash color
android.presplash_color = #1a1a24

# (list) List of Java .jar files to add to the libs so that pyjnius can access
# their classes. Don't add jars that you do not need, since extra jars can slow
# down the build process. Allows wildcards matching, for example:
# OUYA-ODK/libs/*.jar
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# Gradle dependencies
#android.gradle_dependencies =

# Enable AndroidX support
android.enable_androidx = True

# (bool) If True, then skip trying to update the Android sdk
# This can be useful to avoid excess Internet downloads or save time
# when an update is due and you just want to test/build your package
# android.skip_update = False

# (bool) If True, then automatically accept SDK license
# agreements. This is intended for automation only. If set to False,
# the default, you will be shown the license when first running
# buildozer.
android.accept_sdk_license = True

# Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (str) Path to a custom kivy-ios folder
#ios.kivy_ios_dir = ../kivy-ios

# (str) If you want to use a different version of the same framework 
#ios.kivy_ios_branch = master

[buildozer]
# Default is to warn about the kivy version. Set to 0 to suppress.
warn_on_root = 1
