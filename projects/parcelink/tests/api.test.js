import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createApi, safeApiPath } from '../api.js';
import { normalizeSiteConfig, safePublicUrl } from '../site-config.js';
import { getShipments } from '../data.js';

const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test('API writes use the same-origin session and rotate CSRF after login', async () => {
  const calls = [];
  const replies = [response({csrfToken:'anonymous'}), response({user:{role:'customer'}}), response({csrfToken:'signed-in'}), response({prealert:{number:'PR1'}})];
  const api = createApi({fetchImpl:async (path, options) => {calls.push({path,...options}); return replies.shift();}});
  await api.login({username:'alice',password:'secret',remember:false,role:'customer'});
  await api.createPrealert({trackingNumber:'SF123456'});
  assert.deepEqual(calls.map(call=>call.path), ['/api/auth/csrf/','/api/auth/login/','/api/auth/csrf/','/api/package-prealerts/']);
  assert.equal(calls[1].headers['X-CSRFToken'], 'anonymous');
  assert.equal(calls[3].headers['X-CSRFToken'], 'signed-in');
  assert.ok(calls.every(call=>call.credentials==='same-origin' && call.redirect==='error'));
  assert.equal(JSON.parse(calls[1].body).remember,false);
});

test('API failures retain server status and readable errors without falling back to samples', async () => {
  const api = createApi({fetchImpl:async()=>response({detail:'此账号无权访问'},403)});
  await assert.rejects(api.me(), error => error instanceof ApiError && error.status === 403 && error.message === '此账号无权访问');
  const offline = createApi({fetchImpl:async()=>{throw new Error('offline');}});
  await assert.rejects(offline.me(), /无法连接服务器/);
  const invalidJson = createApi({fetchImpl:async()=>({ok:true,status:200,json:async()=>{throw new Error('html');}})});
  await assert.rejects(invalidJson.me(), /无法读取/);
  const invalidList = createApi({fetchImpl:async()=>response({results:[{id:'broken'}],count:1,next:null})});
  await assert.rejects(invalidList.shipments(), /无效的运单列表/);
});

test('pagination refuses external and malformed next URLs before fetching', async () => {
  assert.equal(safeApiPath('/api/shipments/?page=2','https://parcel.test/'),'/api/shipments/?page=2');
  for(const value of ['https://evil.test/api/shipments/','//evil.test/api/shipments/','/admin/','/api/../admin/','/api/\\evil.test/']) assert.throws(()=>safeApiPath(value,'https://parcel.test/'));
  const api = createApi({fetchImpl:async()=>response({results:[],count:1,next:'https://evil.test/api/shipments/'})});
  await assert.rejects(api.shipments(), /无效的分页地址/);
});

test('public links allow HTTPS and local development while rejecting unsafe destinations', () => {
  assert.equal(safePublicUrl('backup.example.com'),'https://backup.example.com');
  assert.equal(safePublicUrl('https://backup.example.com/'),'https://backup.example.com');
  assert.equal(safePublicUrl('http://localhost:8000'),'http://localhost:8000');
  for(const value of ['javascript:alert(1)','data:text/html,a','http://example.com','https://user:pass@example.com','https://example.com/?token=secret','https://example.com/login','//example.com','https://bad host/']) assert.equal(safePublicUrl(value),null,value);
  const config = normalizeSiteConfig({company:{phone:'<script>',email:'bad'},access:{primaryDomain:'https://main.test',backupDomains:['https://backup.test','javascript:a','https://backup.test']}});
  assert.equal(config.company.phone,null);
  assert.equal(config.company.email,null);
  assert.deepEqual(config.access.backupDomains,['https://backup.test']);
});


test('API accepts unknown weight and volume and an empty ETA or timeline', async () => {
  const item={...getShipments(null)[0],weight:null,volume:null,eta:'',timeline:[]};
  const api=createApi({fetchImpl:async()=>response({results:[item],count:1,next:null})});
  assert.deepEqual((await api.shipments()).results,[item]);
  assert.equal(normalizeSiteConfig({company:{isPlaceholder:true}}).company.isPlaceholder,true);
});
