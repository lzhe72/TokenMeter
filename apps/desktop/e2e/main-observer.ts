/** Start the actual installed Electron app paused, attach observation, then resume.
 * Inspector changes only add evidence listeners; no business result is replaced. */
import { _electron, type ElectronApplication } from '@playwright/test';
import { createServer } from 'node:net';
import { readFileSync, existsSync } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { join } from 'node:path';

export type MainObservation = {run_id:string;case_id:string;launch_id:string;pid:number;sequence:number;
  time:string;kind:string;origin?:string;path?:string;method?:string;source_sha256?:string;transport?:string};
export function observations(output:string):MainObservation[] {
  const path=join(output,'main-observer.jsonl');
  return existsSync(path)?readFileSync(path,'utf8').trim().split('\n').filter(Boolean).map(line=>JSON.parse(line)):[];
}
export async function launchObserved(options:Parameters<typeof _electron.launch>[0],
  identity:{run_id:string;case_id:string;output:string}):Promise<ElectronApplication> {
  const port=await new Promise<number>((resolve,reject)=>{
    const server=createServer();server.on('error',reject);server.listen(0,'127.0.0.1',()=>{
      const address=server.address();if(!address||typeof address==='string')return reject(Error('Inspector port absent'));
      server.close(error=>error?reject(error):resolve(address.port));});});
  let socket:WebSocket|undefined;
  const launch=_electron.launch({...options,args:[...(options?.args??[]),`--inspect-brk=127.0.0.1:${port}`]});
  // Observe rejection immediately while waiting for the independently owned inspector.
  let launchError:unknown;void launch.catch(error=>{launchError=error;});
  try {
    const deadline=Date.now()+45_000;let endpoint='';
    while(!endpoint&&Date.now()<deadline){
      if(launchError)throw launchError;
      try{const response=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(500)});
        const list=await response.json() as {webSocketDebuggerUrl:string}[];endpoint=list[0]?.webSocketDebuggerUrl??'';}catch{}
      if(!endpoint)await new Promise(resolve=>setTimeout(resolve,50));
    }
    if(!endpoint)throw Error('Owned main inspector did not become available');
    socket=new WebSocket(endpoint);const ws=socket;
    await new Promise<void>((resolve,reject)=>{ws.addEventListener('open',()=>resolve(),{once:true});ws.addEventListener('error',()=>reject(Error('Inspector connection failed')),{once:true});});
    let counter=0;
    const pending=new Map<number,{resolve:(result:any)=>void;reject:(error:Error)=>void}>();
    let pausedResolve:(params:any)=>void=()=>{};
    const paused=new Promise<any>(resolve=>{pausedResolve=resolve;});
    ws.addEventListener('message',event=>{const message=JSON.parse(String(event.data));
      if(message.method==='Debugger.paused')pausedResolve(message.params);
      if(message.id){const item=pending.get(message.id);if(item){pending.delete(message.id);
        message.error?item.reject(Error(JSON.stringify(message.error))):item.resolve(message.result);}}});
    function send(method:string,params:Record<string,unknown>={}):Promise<any>{return new Promise((resolve,reject)=>{
      const id=++counter;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
    await send('Debugger.enable');await send('Runtime.runIfWaitingForDebugger');
    let pauseTimer:ReturnType<typeof setTimeout>|undefined;
    const state=await Promise.race([paused,new Promise<never>((_,reject)=>{
      pauseTimer=setTimeout(()=>reject(Error('Main entry did not pause')),15_000);})])
      .finally(()=>{if(pauseTimer)clearTimeout(pauseTimer);});
    const frame=state.callFrames[0];
    if(!frame)throw Error('No paused main call frame');
    const location=await send('Debugger.evaluateOnCallFrame',{callFrameId:frame.callFrameId,
      expression:'__filename',returnByValue:true});
    const mainPath=location.result?.value;
    if(typeof mainPath!=='string'||!mainPath.endsWith('/app.asar/out/main/index.cjs'))
      throw Error('Unexpected paused entry: '+JSON.stringify(location));
    const code=readFileSync(join(process.cwd(),'e2e/main-observer.cjs'),'utf8');
    const params={...identity,path:join(identity.output,'main-observer.jsonl'),launch_id:randomUUID(),
      source_sha256:createHash('sha256').update(code).digest('hex'),paused_function:frame.functionName,paused_url:mainPath};
    const result=await send('Debugger.evaluateOnCallFrame',{callFrameId:frame.callFrameId,
      expression:`(()=>{const module={exports:{}};${code}\nreturn module.exports(${JSON.stringify(params)});})()`,returnByValue:true});
    if(result.exceptionDetails||result.result?.value?.installed!==true)throw Error('Main observer could not attach: '+JSON.stringify(result.exceptionDetails??result));
    await send('Debugger.resume');ws.close();socket=undefined;
    return await launch;
  }catch(error){socket?.close();void launch.then(app=>app.close()).catch(()=>{});throw error;}
}
