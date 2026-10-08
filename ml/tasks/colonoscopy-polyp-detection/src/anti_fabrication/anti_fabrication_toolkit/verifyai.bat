@echo off
REM verifyai.bat — lets you type "verifyai" from ANY folder, for ANY project.
REM This file must sit in the same folder as verifyai.py.
python "%~dp0verifyai.py" %*
