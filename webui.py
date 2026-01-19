# -*- coding: utf-8 -*-
"""Very small local Web UI for editing STOCK_LIST in .env.

- Local-only by default (127.0.0.1)
- No external dependencies
- Only edits the STOCK_LIST key; other .env lines are preserved

Usage:
  python webui.py
  WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python webui.py
"""

from __future__ import annotations

import html
import os
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
import logging


logger = logging.getLogger(__name__)

_ENV_PATH = os.getenv("ENV_FILE", ".env")


def _read_env_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_env_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


_STOCK_LIST_RE = re.compile(r"^(?P<prefix>\s*STOCK_LIST\s*=\s*)(?P<value>.*?)(?P<suffix>\s*)$")


def _extract_stock_list(env_text: str) -> str:
    for line in env_text.splitlines():
        m = _STOCK_LIST_RE.match(line)
        if m:
            raw = m.group("value").strip()
            # strip surrounding quotes
            if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
            return raw
    return ""


def _normalize_stock_list(value: str) -> str:
    parts = [p.strip() for p in value.replace("\n", ",").split(",")]
    parts = [p for p in parts if p]
    return ",".join(parts)


def _set_stock_list(env_text: str, new_value: str) -> str:
    new_value = _normalize_stock_list(new_value)

    lines = env_text.splitlines(keepends=False)
    out_lines: list[str] = []
    replaced = False

    for line in lines:
        m = _STOCK_LIST_RE.match(line)
        if not m:
            out_lines.append(line)
            continue

        # Preserve prefix spacing; write as plain value (no quotes)
        out_lines.append(f"{m.group('prefix')}{new_value}{m.group('suffix')}")
        replaced = True

    if not replaced:
        # Keep existing text as-is, just append a new key
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        out_lines.append(f"STOCK_LIST={new_value}")

    # Preserve trailing newline if original had one
    trailing_newline = env_text.endswith("\n") if env_text else True
    out = "\n".join(out_lines)
    return out + ("\n" if trailing_newline else "")


def _page(current_value: str, message: str | None = None) -> bytes:
    safe_value = html.escape(current_value)

    # Toast notifications
    toast_html = ""
    if message:
        toast_html = f"""
        <div id="toast" class="toast show">
            <span class="icon">✅</span> {html.escape(message)}
        </div>
        <script>
            setTimeout(() => {{
                document.getElementById('toast').classList.remove('show');
            }}, 3000);
        </script>
        """

    # Modern CSS styling
    css = """
    :root {
        --primary: #2563eb;
        --primary-hover: #1d4ed8;
        --bg: #f8fafc;
        --card: #ffffff;
        --text: #1e293b;
        --text-light: #64748b;
        --border: #e2e8f0;
        --success: #10b981;
    }
    
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background-color: var(--bg);
        color: var(--text);
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        margin: 0;
        padding: 20px;
    }
    
    .container {
        background: var(--card);
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        width: 100%;
        max-width: 500px;
    }
    
    h2 {
        margin-top: 0;
        color: var(--text);
        font-size: 1.5rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .subtitle {
        color: var(--text-light);
        font-size: 0.875rem;
        margin-bottom: 2rem;
        line-height: 1.5;
    }
    
    .code-badge {
        background: #f1f5f9;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        font-family: monospace;
        color: var(--primary);
    }
    
    .form-group {
        margin-bottom: 1.5rem;
    }
    
    label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
        color: var(--text);
    }
    
    textarea {
        width: 100%;
        padding: 0.75rem;
        border: 1px solid var(--border);
        border-radius: 0.5rem;
        font-family: monospace;
        font-size: 0.875rem;
        line-height: 1.5;
        resize: vertical;
        box-sizing: border-box;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    
    textarea:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    
    button {
        background-color: var(--primary);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 0.5rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        width: 100%;
        font-size: 1rem;
    }
    
    button:hover {
        background-color: var(--primary-hover);
        transform: translateY(-1px);
    }
    
    button:active {
        transform: translateY(0);
    }
    
    .footer {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border);
        color: var(--text-light);
        font-size: 0.75rem;
        text-align: center;
    }
    
    /* Toast Notification */
    .toast {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%) translateY(100px);
        background: white;
        border-left: 4px solid var(--success);
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        display: flex;
        align-items: center;
        gap: 0.75rem;
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        opacity: 0;
    }
    
    .toast.show {
        transform: translateX(-50%) translateY(0);
        opacity: 1;
    }
    """

    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>A/H股自选配置 | WebUI</title>
  <style>{css}</style>
</head>
<body>
  <div class="container">
    <h2>📈 A/H股分析配置</h2>
    <div class="subtitle">
        本地配置文件管理 <span class="code-badge">{html.escape(os.path.basename(_ENV_PATH))}</span>
    </div>
    
    <form method="post" action="/update">
      <div class="form-group">
        <label for="stock_list">自选股代码列表</label>
        <textarea 
            id="stock_list" 
            name="stock_list" 
            rows="6" 
            placeholder="例如: 600519, 000001 (支持逗号、换行分隔)"
        >{safe_value}</textarea>
        <div style="font-size: 0.75rem; color: var(--text-light); margin-top: 0.5rem;">
            * 支持输入股票代码，多个代码请用英文逗号或换行分隔
        </div>
      </div>
      <button type="submit">💾 保存配置</button>
    </form>
    
    <div class="footer">
      <p>仅用于本地环境 (127.0.0.1) • 安全修改 .env 配置</p>
    </div>
  </div>
  
  {toast_html}
</body>
</html>"""
    return body.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", ""):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        env_text = _read_env_text(_ENV_PATH)
        current = _extract_stock_list(env_text)
        payload = _page(current)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path != "/update":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw)
        stock_list = form.get("stock_list", [""])[0]

        env_text = _read_env_text(_ENV_PATH)
        updated = _set_stock_list(env_text, stock_list)
        _write_env_text(_ENV_PATH, updated)

        payload = _page(_normalize_stock_list(stock_list), message="已保存")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        # quiet default http.server logging
        return


def run_server_in_thread(host: str = "127.0.0.1", port: int = 8000):
    """Start the WebUI server in a background thread."""

    def serve():
        server = ThreadingHTTPServer((host, port), _Handler)
        logger.info(f"WebUI 已启动: http://{host}:{port}")
        print(f"WebUI 已启动: http://{host}:{port}")
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"WebUI 发生错误: {e}")
        finally:
            server.server_close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return t


def main() -> int:
    host = os.getenv("WEBUI_HOST", "127.0.0.1")
    port = int(os.getenv("WEBUI_PORT", "8000"))

    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"WebUI running: http://{host}:{port}  (env: {_ENV_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
