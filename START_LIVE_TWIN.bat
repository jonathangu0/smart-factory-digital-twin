@echo off
title Training Factory - LIVE Digital Twin
REM ===========================================================================
REM  ONE-CLICK LAUNCHER
REM   * starts NVIDIA Isaac Sim
REM   * opens scene\TrainingFactoryDigitalTwin.usd
REM   * enables the MCP server (localhost:8766)
REM   * auto-runs every station driver -> the LIVE twin
REM  Keep THIS window open. Closing it closes Isaac Sim.
REM ===========================================================================

REM repo folder = where this .bat lives (portable, keeps trailing backslash)
set "TWIN_REPO=%~dp0"

echo ===========================================================================
echo   TRAINING FACTORY - LIVE DIGITAL TWIN
echo   repo: %TWIN_REPO%
echo   Launching Isaac Sim... (first load of the 400 MB scene can take a minute)
echo ===========================================================================
echo.

call "C:\isaacsim\isaac-sim.bat" ^
  --ext-folder "C:\Users\icets\omniverse-exts" ^
  --enable omni.mcp_extension ^
  --exec "%TWIN_REPO%drivers\start_twin.py"

echo.
echo Isaac Sim has exited.
pause
