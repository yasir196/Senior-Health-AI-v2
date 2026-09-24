from __future__ import annotations
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from .settings import get_dashboard_settings, save_dashboard_settings

def _page(message: str="")->bytes:
    s=get_dashboard_settings()
    notice=f'<div class="notice">{html.escape(message)}</div>' if message else ""
    body=f"""<!doctype html><html><head><meta charset="utf-8"><title>Thumbnail Pipeline Settings</title>
<style>
body{{font-family:Arial,sans-serif;background:#0d1420;color:#f4f7fb;margin:0}} .wrap{{max-width:760px;margin:48px auto;padding:28px}}
.card{{background:#151f2e;border:1px solid #2c3a50;border-radius:14px;padding:26px}} h1{{margin-top:0}}
label{{display:block;font-weight:700;margin:22px 0 8px}} input{{width:100%;box-sizing:border-box;padding:12px;border-radius:8px;border:1px solid #53647c;background:#0d1420;color:white;font-size:18px}}
small{{color:#aebbd0}} button{{margin-top:26px;padding:12px 22px;border:0;border-radius:8px;font-weight:700;cursor:pointer}}
.notice{{padding:12px;margin-bottom:16px;border-radius:8px;background:#173224}} .source{{margin-top:20px;color:#8fa0b7;font-size:13px}}
</style></head><body><div class="wrap"><h1>Thumbnail Intelligence Settings</h1>{notice}<div class="card">
<form method="post" action="/settings/save">
<label>Minimum Eligible Impressions</label>
<input name="min_impressions" type="number" min="1" step="1" value="{s['min_impressions']}" required>
<small>Thumbnails below this impression count are excluded from winner/loser learning.</small>
<label>Full Reliability Impressions</label>
<input name="full_reliability_impressions" type="number" min="{s['min_impressions']}" step="1" value="{s['full_reliability_impressions']}" required>
<small>Must be equal to or greater than Minimum Eligible Impressions.</small>
<button type="submit">Save Settings</button></form>
<div class="source">Source of truth: {html.escape(s['source'])}. Analyzer code reads these saved values; it does not own the thresholds.</div>
</div></div></body></html>"""
    return body.encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/","/settings"):
            data=_page(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.send_error(404)
    def do_POST(self):
        if self.path!="/settings/save": self.send_error(404); return
        try:
            length=int(self.headers.get("Content-Length","0")); form=parse_qs(self.rfile.read(length).decode("utf-8"))
            save_dashboard_settings(min_impressions=int(form["min_impressions"][0]),full_reliability_impressions=int(form["full_reliability_impressions"][0]),actor="dashboard_ui")
            data=_page("Settings saved successfully.")
            self.send_response(200)
        except Exception as exc:
            data=_page(f"Could not save settings: {exc}"); self.send_response(400)
        self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,format,*args): return

def run(host:str="127.0.0.1",port:int=8765)->None:
    ThreadingHTTPServer((host,port),Handler).serve_forever()

if __name__=="__main__": run()
