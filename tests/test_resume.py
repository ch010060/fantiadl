"""Run: python -m pytest tests/test_resume.py  (or python tests/test_resume.py)"""
import http.server, os, sys, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fantiadl.models import FantiaDownloader

DATA = os.urandom(300_000)
calls = []

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        rng = self.headers.get("Range")
        calls.append(rng)
        start = int(rng.split("=")[1].rstrip("-")) if rng else 0
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(DATA) - start))
        if rng:
            self.send_header("Content-Range", "bytes {}-{}/{}".format(start, len(DATA) - 1, len(DATA)))
        self.end_headers()
        body = DATA[start:]
        if len(calls) == 1:  # first request: die halfway
            self.wfile.write(body[:100_000]); self.wfile.flush()
            self.connection.close(); return
        self.wfile.write(body)

def test_resume_after_midstream_drop():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["NO_PROXY"] = "127.0.0.1"
    d = FantiaDownloader.__new__(FantiaDownloader)  # skip __init__ (it logs in)
    d.directory, d.quiet, d.chunk_size, d.request_timeout, d.exclusions = tempfile.mkdtemp(), True, 16 * 1024, (5, 5), []
    d.initialize_session()
    d.db = type("DB", (), {"conn": None, "insert_url": lambda *a: None})()
    out = os.path.join(d.directory, "0")
    d.perform_download("http://127.0.0.1:{}/a.jpg".format(srv.server_port), out, append_server_extension=True)
    srv.shutdown()
    assert calls[0] is None and calls[1].startswith("bytes=") and calls[1] != "bytes=0-", calls
    assert open(out + ".jpg", "rb").read() == DATA
    assert not os.path.exists(out + ".jpg.part")

if __name__ == "__main__":
    test_resume_after_midstream_drop(); print("PASS")
