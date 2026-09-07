import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=19090)
parser.add_argument('--token',default='SYNTHETIC_EXPORT_TOKEN_'+'x'*40)
parser.add_argument('--output',default='synthetic_aws_received.jsonl')
parser.add_argument('--fail-first',type=int,default=0)
args=parser.parse_args()
state={'attempts':0}
out=Path(args.output); out.write_text('')

class H(BaseHTTPRequestHandler):
  def log_message(self,*args): pass
  def do_POST(self):
    state['attempts']+=1
    if self.path!='/v2/telemetry': self.send_response(404); self.end_headers(); return
    if self.headers.get('Authorization')!='Bearer '+args.token:
      self.send_response(401); self.end_headers(); return
    n=int(self.headers.get('Content-Length','0')); body=self.rfile.read(n)
    payload=json.loads(body)
    if self.headers.get('Idempotency-Key')!=payload.get('event_id'):
      self.send_response(400); self.end_headers(); return
    if state['attempts']<=args.fail_first:
      self.send_response(503); self.end_headers(); return
    with out.open('a',encoding='utf-8') as f:
      f.write(json.dumps(payload,separators=(',',':'))+'\n')
    self.send_response(204); self.end_headers()

ThreadingHTTPServer(('127.0.0.1',args.port),H).serve_forever()
