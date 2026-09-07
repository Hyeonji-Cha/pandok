import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import urllib.error
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
GATEWAY_DIR = TEST_DIR.parent / "gateway_export"
REPO_ROOT = TEST_DIR.parents[1]
CONTRACT_PATH = REPO_ROOT / "contracts" / "telemetry-event-v2.schema.json"

def uid(n): return f"00000000-0000-4000-8000-{n:012d}"

def load_gateway(tmp):
    tmp=Path(tmp)
    (tmp/'test-token').write_text('t'*64)
    (tmp/'ingest-key').write_text('i'*64)
    (tmp/'dedupe-key').write_text('11'*32)
    (tmp/'export-token').write_text('e'*64)
    os.environ.update({
      'PANDOK_DB_PATH':str(tmp/'aggregate.sqlite3'),
      'PANDOK_TEST_TOKEN_PATH':str(tmp/'test-token'),
      'PANDOK_INGEST_KEY_PATH':str(tmp/'ingest-key'),
      'PANDOK_DEDUPE_KEY_PATH':str(tmp/'dedupe-key'),
      'PANDOK_SCHEMA_PATH':str(CONTRACT_PATH),
      'PANDOK_ALLOW_NONCANONICAL_SCHEMA':'1',
      'PANDOK_AWS_EXPORT_ENABLED':'1',
      'PANDOK_AWS_EXPORT_URL':'http://127.0.0.1:9/v2/telemetry',
      'PANDOK_AWS_EXPORT_TOKEN_PATH':str(tmp/'export-token'),
      'PANDOK_AWS_EXPORT_MAX_ATTEMPTS':'3',
      'PANDOK_AWS_EXPORT_BACKOFF_SECONDS':'0',
      'PANDOK_ALLOW_INSECURE_EXPORT_FOR_TEST':'1',
    })
    spec=importlib.util.spec_from_file_location('gwexport', GATEWAY_DIR/'app_phase2_8.py')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def payload():
    return {
      'event_id':uid(1),'event_name':'run_started','source_type':'CONTROLLED_SCENARIO',
      'run_id':uid(999),'event_sequence':1,'run_elapsed_seconds':0,
      'game_version':'1.2.3','schema_version':'2.0','map_id':'forest',
      'starting_max_hp':100,'starting_weapon_id':'bone'
    }

class Response:
    def __init__(self,status): self.status=status
    def __enter__(self): return self
    def __exit__(self,*a): return False

def main():
  with tempfile.TemporaryDirectory() as tmp:
    gw=load_gateway(tmp); p=payload(); gw.validate_client_event(p)

    # Privacy rejection.
    bad=dict(p); bad['ip_address']='192.0.2.1'
    try: gw.reject_forbidden_fields(bad); raise AssertionError('privacy field accepted')
    except gw.HTTPException as e: assert e.detail=='forbidden_privacy_field'

    # Retry twice on 500, succeed on third attempt; exact payload/run_id preserved.
    calls=[]
    def retry_then_ok(req, timeout=None):
      body=json.loads(req.data.decode()); calls.append((req,body))
      if len(calls)<3:
        raise urllib.error.HTTPError(req.full_url,500,'x',{},io.BytesIO())
      return Response(204)
    gw.urllib.request.urlopen=retry_then_ok
    assert gw.export_to_aws(p)==3
    assert len(calls)==3
    assert calls[-1][1]==p
    assert calls[-1][1]['run_id']==p['run_id']
    headers={k.lower():v for k,v in calls[-1][0].header_items()}
    assert headers['authorization']=='Bearer '+'e'*64
    assert headers['idempotency-key']==p['event_id']

    # Permanent 400 is not retried.
    calls.clear()
    def bad_request(req,timeout=None):
      calls.append(req); raise urllib.error.HTTPError(req.full_url,400,'x',{},io.BytesIO())
    gw.urllib.request.urlopen=bad_request
    try: gw.export_to_aws(p); raise AssertionError('400 unexpectedly succeeded')
    except gw.ExportPermanentError: pass
    assert len(calls)==1

    # Retryable network failure exhausts budget.
    calls.clear()
    def network_fail(req,timeout=None):
      calls.append(req); raise urllib.error.URLError('synthetic')
    gw.urllib.request.urlopen=network_fail
    try: gw.export_to_aws(p); raise AssertionError('network failure unexpectedly succeeded')
    except gw.ExportRetryableError: pass
    assert len(calls)==3

    # Local dedupe: successful event is aggregated once and then recognized.
    assert gw.aggregate_event(p) is True
    assert gw.event_already_processed(p) is True
    assert gw.aggregate_event(p) is False
    db=sqlite3.connect(Path(tmp)/'aggregate.sqlite3')
    assert db.execute("SELECT event_count FROM event_counts WHERE event_name='run_started'").fetchone()[0]==1
    db.close()

    # Static privacy/logging properties.
    src=(GATEWAY_DIR/'app_phase2_8.py').read_text()
    assert 'request.client' not in src
    assert 'import logging' not in src
    assert 'logging.' not in src
    assert 'print(' not in src

    print('PASS: validation/privacy/dedupe/export retry/permanent failure/network failure/auth interface')

if __name__=='__main__': main()
