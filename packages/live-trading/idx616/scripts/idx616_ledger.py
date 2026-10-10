#!/usr/bin/env python3
"""SQLite signal ledger and conservative forward grader; no order execution."""
import argparse,datetime as dt,hashlib,json,sqlite3
from pathlib import Path
try:
    from _paths import LEDGER_DB as DB  # versi lokal (War Room)
except Exception:  # fallback: jalur Tencent asli (tidak dipakai di sini)
    DB=Path('/home/ubuntu/.hermes/cron/state/idx616_signal_ledger.db')
SCHEMA='''CREATE TABLE IF NOT EXISTS signals(
 event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, producer TEXT NOT NULL, created_at TEXT NOT NULL,
 ticker TEXT NOT NULL, setup TEXT NOT NULL, source TEXT NOT NULL, direction TEXT NOT NULL,
 entry_low REAL NOT NULL, entry_high REAL NOT NULL, sl REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL,
 status TEXT NOT NULL DEFAULT 'CREATED', filled_at TEXT, closed_at TEXT, result TEXT, net_r REAL,
 costs_r REAL DEFAULT 0, data_source TEXT NOT NULL, source_timestamp TEXT, freshness_s REAL,
 duplicate_of TEXT, note TEXT, graded_at TEXT, grader_version TEXT,
 UNIQUE(job_id,created_at,ticker,setup))'''

def con(path=DB):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path); c.row_factory=sqlite3.Row; c.execute(SCHEMA)
 cols={r[1] for r in c.execute('PRAGMA table_info(signals)')}
 for name,typ in [('producer','TEXT'),('source_timestamp','TEXT'),('freshness_s','REAL'),('graded_at','TEXT'),('grader_version','TEXT')]:
  if name not in cols: c.execute(f'ALTER TABLE signals ADD COLUMN {name} {typ}')
 return c
def init_db(path=DB):
 c=con(path); c.commit(); c.close()
def iso(v):
 x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
 if x.tzinfo is None: raise ValueError('timestamp requires timezone')
 return x.isoformat()
def eid(e):
 raw='|'.join(str(e[k]) for k in ('job_id','created_at','ticker','setup','direction','entry_low','entry_high','sl','tp1','tp2'))
 return hashlib.sha256(raw.encode()).hexdigest()[:24]
def validate(e):
 required=('job_id','producer','created_at','ticker','setup','source','direction','entry_low','entry_high','sl','tp1','data_source','source_timestamp')
 if any(e.get(k) in (None,'') for k in required): raise ValueError('missing required signal field')
 e=dict(e); e['created_at']=iso(e['created_at']); e['source_timestamp']=iso(e['source_timestamp']); e['ticker']=str(e['ticker']).upper(); e['direction']=str(e['direction']).upper()
 if e['direction'] not in ('LONG','SHORT'): raise ValueError('invalid direction')
 nums=('entry_low','entry_high','sl','tp1');
 if any(float(e[k])<=0 for k in nums): raise ValueError('prices must be positive')
 if float(e['entry_low'])>float(e['entry_high']): raise ValueError('invalid entry zone')
 if e['direction']=='LONG' and not (e['sl']<e['entry_low']<=e['entry_high']<e['tp1']): raise ValueError('invalid LONG levels')
 if e['direction']=='SHORT' and not (e['tp1']<e['entry_low']<=e['entry_high']<e['sl']): raise ValueError('invalid SHORT levels')
 e['event_id']=eid(e); return e
def insert_signal(path,e):
 e=validate(e); c=con(path); cols=['event_id','job_id','producer','created_at','ticker','setup','source','direction','entry_low','entry_high','sl','tp1','tp2','data_source','source_timestamp','freshness_s','note']
 vals=[e.get(k) for k in cols]; cur=c.execute('INSERT OR IGNORE INTO signals('+','.join(cols)+') VALUES('+','.join('?'*len(cols))+')',vals); c.commit(); row=c.execute('SELECT * FROM signals WHERE event_id=?',(e['event_id'],)).fetchone(); c.close(); return {'event_id':e['event_id'],'inserted':cur.rowcount==1,'status':row['status']}

def record_event(**kwargs):
 return insert_signal(DB, kwargs)
def count(path=DB):
 c=con(path); n=c.execute('SELECT count(*) FROM signals').fetchone()[0]; c.close(); return n
def grade_bars(path,event_id,bars,fee_bps=0,slippage_bps=0):
 c=con(path); r=c.execute('SELECT * FROM signals WHERE event_id=?',(event_id,)).fetchone()
 if not r: raise KeyError(event_id)
 filled=None; result=None; close=None; fill_price=None
 for b in sorted(bars,key=lambda x:x['ts']):
  if filled is None:
   touched=b['low']<=r['entry_high'] and b['high']>=r['entry_low']
   if not touched: continue
   filled=b['ts']; fill_price=max(r['entry_low'],min(r['entry_high'],b.get('open',r['entry_low'])))
  if r['direction']=='LONG':
   sl_hit=b['low']<=r['sl']; tp1_hit=b['high']>=r['tp1']; tp2_hit=r['tp2'] is not None and b['high']>=r['tp2']
  else:
   sl_hit=b['high']>=r['sl']; tp1_hit=b['low']<=r['tp1']; tp2_hit=r['tp2'] is not None and b['low']<=r['tp2']
  if sl_hit and (tp1_hit or tp2_hit): result='AMBIGUOUS'; close=b['ts']; break
  if sl_hit: result='SL'; close=b['ts']; break
  if tp2_hit: result='TP2'; close=b['ts']; break
  if tp1_hit: result='TP1'; close=b['ts']; break
 if filled is None: status='CREATED'
 elif result is None: status='FILLED'
 else: status='CLOSED'
 net=None
 if result in ('SL','TP1','TP2'):
  raw={'SL':-1.0,'TP1':1.0,'TP2':2.0}[result]; net=raw-(fee_bps+slippage_bps)/100.0
 now=dt.datetime.now(dt.timezone.utc).isoformat(); c.execute('UPDATE signals SET status=?,filled_at=?,closed_at=?,result=?,net_r=?,graded_at=?,grader_version=? WHERE event_id=?',(status,filled,close,result,net,now,'v1',event_id)); c.commit(); out=dict(c.execute('SELECT * FROM signals WHERE event_id=?',(event_id,)).fetchone()); c.close(); return out
def metrics(path=DB):
 c=con(path); rows=c.execute('SELECT * FROM signals').fetchall(); c.close(); closed=[r for r in rows if r['result'] in ('TP1','TP2','SL') and r['net_r'] is not None]; vals=[r['net_r'] for r in closed]; wins=[v for v in vals if v>0]; losses=[-v for v in vals if v<0]; eq=peak=dd=0
 for v in vals: eq+=v; peak=max(peak,eq); dd=max(dd,peak-eq)
 return {'signals':len(rows),'filled':sum(r['filled_at'] is not None for r in rows),'pending':sum(r['status'] in ('CREATED','FILLED') for r in rows),'closed':len(closed),'tp1':sum(r['result']=='TP1' for r in closed),'tp2':sum(r['result']=='TP2' for r in closed),'sl':sum(r['result']=='SL' for r in closed),'win_rate':round(len(wins)/len(closed)*100,2) if closed else None,'expectancy_r':round(sum(vals)/len(vals),4) if vals else None,'profit_factor':round(sum(wins)/sum(losses),4) if losses else None,'total_r':round(sum(vals),4),'max_drawdown_r':round(dd,4),'gate':'INSUFFICIENT_SAMPLE' if len(closed)<10 else 'DIRECTIONAL_ONLY' if len(closed)<30 else 'PRELIMINARY_EVALUATION' if len(closed)<100 else 'TUNING_CANDIDATE'}
def report(path=DB): print(json.dumps(metrics(path),indent=2))
def main():
 p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True); a=s.add_parser('report'); a.add_argument('--db',default=str(DB)); g=s.add_parser('grade-fixture'); g.add_argument('--db',default=str(DB)); g.add_argument('--event-id',required=True); g.add_argument('--bars',required=True); x=p.parse_args()
 if x.cmd=='report': report(x.db)
 else: print(json.dumps(grade_bars(x.db,x.event_id,json.loads(Path(x.bars).read_text())),indent=2))
if __name__=='__main__': main()
