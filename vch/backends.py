"""Optional browser backend using reviewed pdoom-video rendering primitives.

Declarative scenes only: no arbitrary JS from a prompt is executed by this adapter.
The pinned upstream primitives are MIT, not the upstream film/media/full Engine.
"""
from __future__ import annotations
import base64
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from PIL import Image
from .core import Frame, SceneRenderer, contained, finite


def create_renderer(spec, root, trust_code=False):
    name = spec.get('backend', 'pillow')
    if name == 'pillow': return SceneRenderer(spec, root, trust_code)
    if name == 'pdoom': return BrowserRenderer(spec, root, trust_code)
    raise ValueError(f'Unknown backend: {name}')


class BrowserRenderer:
    def __init__(self, spec, root, trust_code=False):
        if not trust_code: raise PermissionError('Review renderer code and pass --trust-scene-code')
        from playwright.sync_api import sync_playwright
        self.spec, self.root = spec, Path(root)
        dist = Path(__file__).resolve().parents[1]/'backends/pdoom/dist'
        if not (dist/'index.html').is_file():
            raise ValueError('Build browser backend first: npm ci --prefix backends/pdoom && npm run build --prefix backends/pdoom')
        allowed = {a['path'] for a in spec.get('assets', [])}
        data = json.dumps(spec, ensure_ascii=False).encode()
        backend = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(handler):
                route = unquote(urlparse(handler.path).path)
                try:
                    if route == '/contract.json': payload, mime = data, 'application/json'
                    elif route.startswith('/asset/'):
                        rel = route[len('/asset/'):]
                        if rel not in allowed: raise ValueError('Undeclared asset')
                        payload, mime = contained(root, rel).read_bytes(), 'application/octet-stream'
                    else:
                        p = contained(dist, route.lstrip('/') or 'index.html')
                        payload = p.read_bytes()
                        mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css'}.get(p.suffix,'application/octet-stream')
                    handler.send_response(200); handler.send_header('Content-Type', mime)
                    handler.end_headers(); handler.wfile.write(payload)
                except (OSError,ValueError): handler.send_error(404)
            def do_POST(handler):
                if handler.path != '/frame' or not getattr(backend,'consume',None):
                    handler.send_error(404);return
                try:
                    length=int(handler.headers['Content-Length'])
                    expected=spec['video']['width']*spec['video']['height']*4
                    if not 4<=length<=expected*2:raise ValueError('Invalid frame payload')
                    payload=handler.rfile.read(length);n=int.from_bytes(payload[:4],'little')
                    metadata=json.loads(payload[4:4+n]);pixels=payload[4+n:]
                    decoded=Image.open(io.BytesIO(pixels)).convert('RGB')
                    if decoded.size!=(spec['video']['width'],spec['video']['height']):raise ValueError('Wrong frame dimensions')
                    backend.consume(metadata,decoded)
                    handler.send_response(200);handler.end_headers();handler.wfile.write(b'OK')
                except Exception as e:
                    backend.errors.append(str(e));handler.send_error(500)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.pw = self.browser = None
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=True,
                args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            self.page = self.browser.new_page(viewport={'width':spec['video']['width'],'height':spec['video']['height']})
            self.errors=[]
            self.page.on('pageerror', lambda e:self.errors.append(str(e)))
            # No runtime fetches beyond the local server that exposes declared assets.
            origin = f'http://127.0.0.1:{self.server.server_port}'
            self.page.route('**/*', lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            self.page.goto(origin, wait_until='networkidle')
            self.page.wait_for_function('window.__vch?.ready',timeout=60000)
            self.provenance = self.page.evaluate('window.__vch.provenance')
            self.provenance['browser'] = self.browser.version
        except BaseException:
            self.close(); raise

    def sampled(self,t):
        if not finite(t) or not 0 <= t < self.spec['video']['duration']: raise ValueError('Timestamp out of range')
        result=self.page.evaluate('(t)=>window.__vch.frame(t)', t)
        if self.errors: raise RuntimeError('Browser render error: '+'; '.join(self.errors))
        return Frame(Image.open(io.BytesIO(base64.b64decode(result['png']))).convert('RGB'),result['elements'])

    render=sampled

    def stream(self, consume, total):
        self.consume=consume
        try:
            count=self.page.evaluate('(n)=>window.__vch.stream(n)',total)
            if self.errors:raise RuntimeError('; '.join(self.errors))
            if count!=total:raise RuntimeError('Browser frame count mismatch')
        finally:self.consume=None

    def close(self):
        if self.browser: self.browser.close();self.browser=None
        if self.pw: self.pw.stop();self.pw=None
        if getattr(self,'server',None): self.server.shutdown();self.server.server_close();self.server=None
