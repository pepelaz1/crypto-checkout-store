from contextlib import contextmanager
import sqlite3, os, json
@contextmanager
def db():
 c=sqlite3.connect(os.getenv('DATA_DB','data.sqlite3'),timeout=10);c.row_factory=sqlite3.Row
 try:
  schema(c)
  yield c
  c.commit()
 except BaseException:
  c.rollback();raise
 finally:c.close()

import hashlib,hmac,secrets,time
SECRET=os.getenv('WEBHOOK_SECRET') or secrets.token_hex(32)
PRODUCTS=[{'id':'kit','name':'Developer field kit','cents':4900},{'id':'guide','name':'API integration guide','cents':1900},{'id':'icons','name':'Interface icon pack','cents':1200}]
def schema(c):
 c.executescript("""CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,checkout_key TEXT UNIQUE,cart TEXT,total INTEGER,status TEXT,created INTEGER);
 CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,order_id TEXT,payload TEXT);""")
def checkout(data):
 key=str(data.get('key',''));cart=data.get('cart',{})
 if not 1<=len(key)<=100 or not isinstance(cart,dict):raise ValueError('Checkout key and cart required')
 clean={};total=0
 for pid,q in cart.items():
  product=next((p for p in PRODUCTS if p['id']==pid),None)
  if product is None or type(q) is not int or not 1<=q<=20:raise ValueError('Invalid product or quantity')
  clean[pid]=q;total+=q*product['cents']
 if not clean:raise ValueError('Cart is empty')
 payload=json.dumps(clean,sort_keys=True)
 with db() as c:
  c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM orders WHERE checkout_key=?',(key,)).fetchone()
  if old:
   if old['cart']!=payload:raise ValueError('Checkout key already used with another cart')
   return dict(old)
  oid=secrets.token_hex(6);c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?)',(oid,key,payload,total,'awaiting_payment',int(time.time())))
  return dict(c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())
def apply_webhook(body,signature):
 expected=hmac.new(SECRET.encode(),body,hashlib.sha256).hexdigest()
 if not hmac.compare_digest(expected,signature):raise ValueError('Invalid payment signature')
 event=json.loads(body);eid=str(event.get('event_id',''))
 if not 1<=len(eid)<=100:raise ValueError('Event ID required')
 with db() as c:
  c.execute('BEGIN IMMEDIATE');order=c.execute('SELECT * FROM orders WHERE id=?',(event.get('order_id'),)).fetchone()
  if not order:raise ValueError('Unknown order')
  if event.get('currency')!='USDC' or type(event.get('amount_cents')) is not int or event['amount_cents']!=order['total'] or event.get('status')!='confirmed':raise ValueError('Unconfirmed or mismatched payment')
  payload=body.decode();old=c.execute('SELECT payload FROM events WHERE id=?',(eid,)).fetchone()
  if old:
   if old['payload']!=payload:raise ValueError('Conflicting payment event')
   return {'replayed':True,'order_id':order['id']}
  c.execute('INSERT INTO events VALUES(?,?,?)',(eid,order['id'],payload));c.execute("UPDATE orders SET status='paid' WHERE id=?",(order['id'],))
  return {'replayed':False,'order_id':order['id']}
def state():
 with db() as c:return {'products':PRODUCTS,'orders':[dict(r) for r in c.execute('SELECT * FROM orders ORDER BY created DESC')],'events':c.execute('SELECT count(*) FROM events').fetchone()[0]}
def action(path,data):
 if path=='/api/checkout':return checkout(data)
 if path=='/api/simulate':
  with db() as c:order=c.execute('SELECT * FROM orders WHERE id=?',(data.get('order_id'),)).fetchone()
  if not order:raise ValueError('Unknown order')
  body=json.dumps({'event_id':'demo-'+order['id'],'order_id':order['id'],'amount_cents':order['total'],'currency':'USDC','status':'confirmed'},sort_keys=True).encode()
  return apply_webhook(body,hmac.new(SECRET.encode(),body,hashlib.sha256).hexdigest())
 raise ValueError('Unknown action')
