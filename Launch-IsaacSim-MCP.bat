@echo off
title Isaac Sim + MCP Extension
echo ============================================================
echo  Launching NVIDIA Isaac Sim with the MCP extension enabled
echo  Extension: omni.mcp_extension  (WebSocket on localhost:8766)
echo  Keep this window OPEN - closing it will close Isaac Sim.
echo ============================================================
echo.
call "C:\isaacsim\isaac-sim.bat" --ext-folder "C:\Users\icets\omniverse-exts" --enable omni.mcp_extension
echo.
echo Isaac Sim has exited.
pause
