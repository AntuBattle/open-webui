"""Forward the registered local Archi callback to OpenWebUI."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path != '/redirect':
            self.send_error(404)
            return

        target = 'http://127.0.0.1:3000/oauth/oidc/login/callback'
        if url.query:
            target += '?' + url.query
        self.send_response(302)
        self.send_header('Location', target)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        # Callback queries contain authorization codes; never log them.
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 7869), CallbackHandler).serve_forever()
