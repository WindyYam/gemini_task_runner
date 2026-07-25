@echo off

echo Start the web chat server
echo Make sure run.bat (main assistant backend) is already running
echo To enable HTTPS, set web_tls_enabled/web_tls_certfile/web_tls_keyfile in config.json

.\.venv\Scripts\python.exe scripts/web_chat_server.py --config config.json --host 0.0.0.0 --port 8000
pause
