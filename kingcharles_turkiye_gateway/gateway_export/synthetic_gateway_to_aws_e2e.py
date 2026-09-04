import json, os, sqlite3, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO_ROOT=ROOT.parents[1]
EXAMPLES_DIR=ROOT.parent / "examples"
CONTRACT_PATH=REPO_ROOT / "contracts" / "telemetry-event-v2.schema.json"
TOKEN='SYNTHETIC_EXPORT_TOKEN_'+'x'*40
TEST='SYNTHETIC_TEST_TOKEN_'+'t'*40
INGEST='SYNTHETIC_INGEST_KEY_'+'i'*40

def wait(url,timeout=10):
  end=time.time()+timeout
  while time.time()<end:
    try:
      with urllib.request.urlopen(url,timeout=.5) as r: return
    except Exception: time.sleep(.1)
  raise RuntimeError('gateway did not become ready')

def main():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td); received=td/'received.jsonl'
    for name,value in [('test-token',TEST),('ingest-key',INGEST),('export-token',TOKEN),('dedupe-key','11'*32)]:
      (td/name).write_text(value)
    receiver=subprocess.Popen([sys.executable,str(ROOT/'synthetic_aws_receiver.py'),'--port','19090','--token',TOKEN,'--output',str(received),'--fail-first','2'])
    env=os.environ.copy(); env.update({
      'PYTHONPATH':str(ROOT), 'PANDOK_DB_PATH':str(td/'aggregate.sqlite3'),
      'PANDOK_TEST_TOKEN_PATH':str(td/'test-token'),'PANDOK_INGEST_KEY_PATH':str(td/'ingest-key'),
      'PANDOK_DEDUPE_KEY_PATH':str(td/'dedupe-key'),'PANDOK_SCHEMA_PATH':str(CONTRACT_PATH),
      'PANDOK_AWS_EXPORT_ENABLED':'1',
      'PANDOK_AWS_EXPORT_URL':'http://127.0.0.1:19090/v2/telemetry','PANDOK_AWS_EXPORT_TOKEN_PATH':str(td/'export-token'),
      'PANDOK_AWS_EXPORT_MAX_ATTEMPTS':'3','PANDOK_AWS_EXPORT_BACKOFF_SECONDS':'0.01',
      'PANDOK_ALLOW_INSECURE_EXPORT_FOR_TEST':'1'})
    gateway=subprocess.Popen([sys.executable,'-m','uvicorn','app_phase2_8:app','--host','127.0.0.1','--port','18080','--no-access-log','--log-level','critical'],cwd=ROOT,env=env)
    try:
      wait('http://127.0.0.1:18080/health')
      lines=(EXAMPLES_DIR/'complete_run_sequence.jsonl').read_text().splitlines()
      for line in lines:
        req=urllib.request.Request('http://127.0.0.1:18080/v1/telemetry',data=line.encode(),method='POST',headers={'Content-Type':'application/json','x-pandok-controlled-test':'1','x-pandok-test-token':TEST})
        with urllib.request.urlopen(req,timeout=5) as r: assert r.status==204
      # Retry the last client event; local dedupe must keep AWS receiver at 5 accepted events.
      req=urllib.request.Request('http://127.0.0.1:18080/v1/telemetry',data=lines[-1].encode(),method='POST',headers={'Content-Type':'application/json','x-pandok-controlled-test':'1','x-pandok-test-token':TEST})
      with urllib.request.urlopen(req,timeout=5) as r: assert r.status==204
      time.sleep(.2)
      rows=received.read_text().splitlines(); assert len(rows)==5, len(rows)
      db=sqlite3.connect(td/'aggregate.sqlite3')
      assert db.execute('SELECT SUM(event_count) FROM event_counts').fetchone()[0]==5
      db.close()
      print('PASS: synthetic Gateway -> AWS HTTP E2E; 2 transient AWS failures retried; 5 v2 events accepted; client retry deduped')
    finally:
      gateway.terminate(); receiver.terminate(); gateway.wait(timeout=5); receiver.wait(timeout=5)

if __name__=='__main__': main()
