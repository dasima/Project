import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { STATUS_OPTIONS, getShipments, getStats, filterShipments } from '../data.js';
import { SITE_CONFIG, normalizeSiteConfig } from '../site-config.js';

function portalHarness(api) {
  const handlers = new Map();
  const app = {html:'',writes:0,details:[],querySelectorAll:selector=>selector==='details[data-disclosure]'?app.details:[],querySelector:()=>null};
  Object.defineProperty(app,'innerHTML',{get:()=>app.html,set:value=>{app.html=value;app.writes+=1;}});
  const modal = {innerHTML:'',querySelector:()=>null};
  const connection = {innerHTML:''};
  const document = {
    activeElement:null,
    body:{classList:{add(){},remove(){}}},
    querySelector:selector=>({'#app':app,'#modal-root':modal,'#connection-status':connection,'#toast-root':{append(){}}}[selector] || null),
    addEventListener:(type,handler)=>handlers.set(type,handler),
    createElement:()=>({setAttribute(){},remove(){}}),
  };
  const context=vm.createContext({
    document,window:{location:{search:'',href:'http://localhost/'},scrollTo(){}},
    URL,URLSearchParams,Map,JSON,Date,crypto:webcrypto,
    setInterval:()=>1,clearInterval(){},setTimeout:()=>1,requestAnimationFrame(){},
    STATUS_OPTIONS,getShipments,getStats,filterShipments,SITE_CONFIG,normalizeSiteConfig,
    createApi:()=>api,renderRouteMap:()=>'',deliveryDate:shipment=>shipment.eta,validTrackingNumber:value=>/^[A-Za-z0-9-]{6,40}$/.test(value),
    FormData:class {constructor(form){this.values=form.values;}get(key){return this.values[key];}},
  });
  const source=readFileSync(new URL('../app.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^initialize\(\);\s*$/m,'');
  vm.runInContext(source,context);
  return {app,modal,handlers,context,run:code=>vm.runInContext(code,context)};
}

test('a prealert retry keeps its form submission key until a successful response', async()=>{
  const requests=[];
  const portal=portalHarness({createPrealert:async payload=>{
    requests.push({...payload});
    if(requests.length===1)throw new Error('response interrupted');
    return {prealert:{number:'PR001',status:'submitted'}};
  }});
  portal.run("session={role:'customer',name:'客户'};newShipmentModal();");
  const firstMarkup=portal.modal.innerHTML;
  const key=firstMarkup.match(/data-submission-key="([^"]+)"/)[1];
  assert.match(key,/^[a-f0-9-]{32,36}$/);
  const button={disabled:false},error={textContent:''};
  const form={id:'new-shipment-form',dataset:{submissionKey:key},values:{trackingNumber:'SF123456',goods:'衣物',pieces:'1',weight:'1',method:'空运专线',destination:'SIN'},querySelector:selector=>selector==='[type="submit"]'?button:error};
  await portal.handlers.get('submit')({target:form,preventDefault(){}});
  assert.equal(portal.modal.innerHTML,firstMarkup);
  assert.equal(error.textContent,'response interrupted');
  assert.equal(button.disabled,false);
  await portal.handlers.get('submit')({target:form,preventDefault(){}});
  assert.equal(requests[0].submissionKey,key);
  assert.equal(requests[1].submissionKey,key);
  assert.equal(portal.modal.innerHTML,'');
  portal.run('newShipmentModal();');
  assert.notEqual(portal.modal.innerHTML.match(/data-submission-key="([^"]+)"/)[1],key);
});

test('background shipment reads keep help disclosures and their existing DOM intact', async()=>{
  const items=getShipments(null);
  const portal=portalHarness({shipments:async()=>({results:items,count:items.length,next:null})});
  portal.run("session={role:'customer',name:'客户',customerCode:'C001'};page='help';render();");
  const access={dataset:{disclosure:'access'},open:true};
  const faq={dataset:{disclosure:'faq-1'},open:true};
  portal.app.details=[access,faq];
  portal.app.writes=0;
  await portal.run('refreshShipments();');
  assert.equal(portal.app.writes,0);
  assert.equal(portal.app.details[0],access);
  assert.equal(access.open,true);
  portal.run('render();');
  assert.match(portal.app.innerHTML,/data-disclosure="access" open/);
  assert.match(portal.app.innerHTML,/data-disclosure="faq-1" open/);
});
