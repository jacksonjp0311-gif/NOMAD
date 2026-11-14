@echo off
py -3 -B "%~dp0scripts\windows_entry_v18.py" %*
exit /b %errorlevel%
