import os, uuid, unittest
import engine
class Tests(unittest.TestCase):
 def setUp(self):
  self.path='test-'+uuid.uuid4().hex+'.db';os.environ['DATA_DB']=self.path
 def tearDown(self):
  for suffix in ('','-wal','-shm','-journal'):
   try:os.remove(self.path+suffix)
   except FileNotFoundError:pass

 def test_checkout_retry_and_cart_conflict(self):
  order=engine.checkout({'key':'one','cart':{'kit':2}})
  self.assertEqual(order['total'],9800);self.assertEqual(engine.checkout({'key':'one','cart':{'kit':2}})['id'],order['id'])
  with self.assertRaises(ValueError):engine.checkout({'key':'one','cart':{'guide':1}})
 def test_payment_retry_and_signature(self):
  order=engine.checkout({'key':'one','cart':{'kit':1}})
  self.assertFalse(engine.action('/api/simulate',{'order_id':order['id']})['replayed'])
  self.assertTrue(engine.action('/api/simulate',{'order_id':order['id']})['replayed'])
  self.assertEqual(engine.state()['events'],1)
  with self.assertRaises(ValueError):engine.apply_webhook(b'{}','wrong')
 def test_invalid_amount_cannot_mark_paid(self):
  import json,hmac,hashlib
  o=engine.checkout({'key':'one','cart':{'guide':1}})
  body=json.dumps({'event_id':'bad','order_id':o['id'],'amount_cents':1,'currency':'USDC','status':'confirmed'}).encode()
  with self.assertRaises(ValueError):engine.apply_webhook(body,hmac.new(engine.SECRET.encode(),body,hashlib.sha256).hexdigest())
  self.assertEqual(engine.state()['orders'][0]['status'],'awaiting_payment');self.assertEqual(engine.state()['events'],0)
