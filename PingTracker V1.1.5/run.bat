@echo off
title MC Ping Tracker
pythonw main.py
if errorlevel 1 (
    python main.py
    pause
)
