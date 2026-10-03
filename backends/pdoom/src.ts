import * as THREE from 'three';
import { FSPass } from './vendor/gl';

const spec = await (await fetch('/contract.json')).json();
const W=spec.video.width,H=spec.video.height, sx=W/1280,sy=H/720;
for (const [name,path] of [['VCH',spec.style.font],['Latin','assets/fonts/Inter.ttf']]) {
 const font=new FontFace(name,`url(/asset/${path})`);await font.load();document.fonts.add(font);
}
const output=document.querySelector('#output') as HTMLCanvasElement;output.width=W;output.height=H;
const ctx=output.getContext('2d',{willReadFrequently:true})!;
const glCanvas=document.createElement('canvas');
// The soft procedural backdrop renders at half resolution; text/diagrams stay native.
const renderer=new THREE.WebGLRenderer({canvas:glCanvas,antialias:false,preserveDrawingBuffer:true});renderer.setSize(W/2,H/2);
const uniforms={t:{value:0},mode:{value:0},dark:{value:1},res:{value:new THREE.Vector2(W,H)}};
const shader=new FSPass(`
uniform float t,mode,dark; uniform vec2 res;
void main(){
 vec2 q=vUv*2.-1.;q.x*=res.x/res.y;
 vec3 bg=mix(vec3(.94,.95,.92),vec3(.043,.074,.12),dark);
 vec3 accent=mix(vec3(.09,.40,.43),vec3(.20,.76,.71),dark);
 float field=0.;
 if(mode<.5){
  vec2 r=q-vec2(.8,-.05);float a=atan(r.y,r.x),d=length(r);
  for(int i=0;i<6;i++){float k=float(i);float ring=.23+k*.105+.026*sin(a*5.+t*.7+k);
   field+=.8*exp(-abs(d-ring)*200.)*(.65+.35*sin(a*3.-t+k));}
 }else if(mode<1.5){
  for(int i=0;i<5;i++){float f=float(i);float y=-.2+.16*sin(q.x*3.5-t*1.7+f*.38)+.055*f;
   field+=.25*exp(-abs(q.y-y)*240.);}
 }else{
  vec2 g=q*vec2(8.,9.);g.x+=.08*sin(g.y+t*.5);
  field=.10*exp(-min(abs(fract(g.x)-.5),abs(fract(g.y)-.5))*120.);
 }
 float vign=1.-.1*dot(q,q);fragColor=vec4(bg*vign+accent*field*.30,1.);
}`,uniforms);
let elements:any[]=[];let colors:any;let scene:any;
const ease=(p:number)=>{p=Math.max(0,Math.min(1,p));return p*p*(3-2*p)};
const hash=(i:number)=>{const x=Math.sin(i*127.1+spec.seed*311.7)*43758.5453;return x-Math.floor(x)};
const lum=(hex:string)=>{const a=hex.match(/[a-f0-9]{2}/gi)!.map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*a[0]+.7152*a[1]+.0722*a[2]};
const contrast=(a:string,b:string)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
function text(id:string,str:string,x:number,y:number,size:number,color=colors.ink,maxWidth=1140,font='VCH'){
 ctx.font=`${size}px ${font}`;while(ctx.measureText(str).width>maxWidth&&size>20){size--;ctx.font=`${size}px ${font}`}
 ctx.textBaseline='alphabetic';ctx.fillStyle=color;const m=ctx.measureText(str);const base=y+size;
 ctx.fillText(str,x,base);
 elements.push({id:scene.id+'.'+id,type:'text',text:str,size:size*sy,
 bbox:[(x-m.actualBoundingBoxLeft)*sx,(base-m.actualBoundingBoxAscent)*sy,(x+m.actualBoundingBoxRight)*sx,(base+m.actualBoundingBoxDescent)*sy],contrast:contrast(color,colors.bg)});
}
function line(x:number,y:number,xx:number,yy:number,color=colors.line,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(xx,yy);ctx.stroke()}
function box(x:number,y:number,w:number,h:number,fill=colors.panel,r=12){ctx.fillStyle=fill;ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fill()}
function dot(x:number,y:number,r:number,color=colors.accent){ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill()}
function labelRows(rows:string[],t:number,x=76,y=268){rows.forEach((r,i)=>{line(x,y+i*70+45,1194,y+i*70+45);text('row'+i,r,x+18,y+i*70,30);dot(x,y+i*70+24,4+3*ease((t-i*.3)/.4))})}
function renderVisual(kind:string,t:number,p:number,params:any){
 const A=colors.accent, rows=params.labels||[];
 if(kind==='hero'||kind==='finale'){
  text('large',params.word||'一帧一帧',76,252,112,colors.ink,780);
  text('sub',rows[0]||'想法，成为可验证的画面。',82,426,32,colors.ink,800);
  const n=kind==='finale'?4:6;for(let i=0;i<n;i++){let a=t*.4+i*2*Math.PI/n;dot(1035+Math.cos(a)*110,355+Math.sin(a)*110,6+i*2)}
 }else if(kind==='network'||kind==='depth'){
  const nodes:Array<number[]>=[];for(let i=0;i<76;i++){let z=1-2*(i+.5)/76,a=i*2.39996+t*.16,r=Math.sqrt(1-z*z),x=Math.cos(a)*r,y=Math.sin(a)*r;
   const yy=y*Math.cos(.45)-z*Math.sin(.45),zz=y*Math.sin(.45)+z*Math.cos(.45),d=1/(2.8-zz);
   nodes.push([850+x*430*d,416+yy*430*d,zz]);}
  for(let i=0;i<nodes.length;i++){for(let j=i+1;j<nodes.length;j++){const a=nodes[i],b=nodes[j];if(Math.hypot(a[0]-b[0],a[1]-b[1])<72)line(a[0],a[1],b[0],b[1],colors.line,1)}}
  nodes.sort((a,b)=>a[2]-b[2]).forEach(a=>dot(a[0],a[1],2+(a[2]+1)*2,A));
  rows.slice(0,3).forEach((r,i)=>text('node-note'+i,r,80,290+i*78,30,colors.ink,570));
 }else if(kind==='pipeline'){
  const names=rows.length?rows:['文字','场景代码','渲染画面','实际检验'];
  names.slice(0,4).forEach((r,i)=>{let x=76+i*300;box(x,310,260,178);text('step'+i,String(i+1).padStart(2,'0'),x+22,330,24,A,220,'Latin');text('name'+i,r,x+22,395,34,colors.ink,216);if(i<3)line(x+268,398,x+290,398,A,3)});
  dot(90+(t*.18%1)*1100,530,7);line(76,530,1200,530,A,1);
 }else if(kind==='wave'){
  const start=76,width=1124;for(let g=0;g<5;g++)line(start,280+g*66,1200,280+g*66,colors.line,1);
  ctx.beginPath();ctx.strokeStyle=A;ctx.lineWidth=3;for(let i=0;i<1000;i++){let x=start+i*width/999,tt=i/999*8;
   let amp=Math.exp(-((tt+t*.8)%1)*3);let y=414+Math.sin(tt*37-t*4)*amp*105;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.stroke();
  text('waveLabel',rows[0]||'同一条时间轴',82,542,27);
  const beat=(t*2)%1;dot(1180,560,10+16*(1-beat),A);
 }else if(kind==='timeline'){
  for(let k=0;k<3;k++){text('track'+k,rows[k]||['旁白','画面','节奏'][k],78,275+k*92,27);
   for(let i=0;i<12;i++)box(208+i*81,275+k*92,73,52,i%4===Math.floor(t*.6)%4?A:colors.panel,5)}
  const x=210+(t*.11%1)*960;line(x,262,x,566,A,4);text('clock',`${t.toFixed(2)} s`,Math.min(x+8,1050),570,24,colors.ink,148,'Latin');
 }else if(kind==='code'){
  box(70,259,1140,335);const code=params.code||['frame = render(time, seed)','audio = timeline(time)','inspect(encoded_video)','repair(failed_requirements)'];
  code.forEach((s:string,i:number)=>{text('ln'+i,String(i+1).padStart(2,'0'),92,286+i*65,23,A,80,'Latin');text('code'+i,s,156,279+i*65,31,colors.ink,995,'Latin')});
  line(139,273,139,572,colors.line,1);
 }else if(kind==='samples'){
  for(let j=0;j<3;j++){const x=76+j*388;box(x,265,356,310);text('sample-label'+j,rows[j]||['时间采样','逐帧检查','实际输出'][j],x+20,281,29,colors.ink,316);
   for(let i=0;i<[1,4,12][j];i++){const ph=t*.7+i*.09;ctx.globalAlpha=1/Math.sqrt([1,4,12][j]);dot(x+178+Math.sin(ph)*118,438+Math.cos(ph)*55,17,A)}ctx.globalAlpha=1;
   line(x+22,530,x+334,530,colors.line,2)}
 }else if(kind==='comparison'){
  for(let k=0;k<2;k++){let x=76+k*580;box(x,260,550,340);text('compare'+k,rows[k]||['预览','解码后'][k],x+25,280,32);for(let i=0;i<6;i++)box(x+28+i*81,370,61,80+40*Math.sin(t*.8+i),i===Math.floor(t)%6?A:colors.line,4)}
 }else if(kind==='meter'){
  const x=76,y=330;rows.slice(0,4).forEach((s:string,i:number)=>{text('metric'+i,s,x,y+i*60,29);for(let j=0;j<14;j++)box(580+j*42,y+i*60+10,34,18,j<Math.round(ease((t-i*.2)/2)*[14,12,9,0][i])?A:colors.panel,3)});
 }else if(kind==='cards'){
  rows.slice(0,3).forEach((r:string,i:number)=>{let x=76+i*388;box(x,277,356,285);text('cardnum'+i,String(i+1).padStart(2,'0'),x+24,300,65,A,300,'Latin');text('card'+i,r,x+24,445,29,colors.ink,308);line(x+24,422,x+332,422,colors.line)})
 }else{labelRows(rows,t)}
}
function frame(t:number,encode=true){
 // Reset both pixels and drawing state: a seek cannot inherit prior raster state.
 ctx.reset();
 scene=spec.scenes.find((s:any)=>t>=s.start&&t<s.end);if(!scene)throw Error('Outside timeline');
 const params=scene.params||{},lt=t-scene.start,p=lt/(scene.end-scene.start),dark=params.theme!=='light';
 colors=dark?{bg:'#0B131F',ink:'#EEF2EA',accent:'#59D6C2',line:'#294455',panel:'#122D3A'}:{bg:'#EEF2EA',ink:'#112D3A',accent:'#09635E',line:'#B8CFCE',panel:'#DCE8E2'};
 uniforms.t.value=t;uniforms.dark.value=dark?1:0;uniforms.mode.value=params.kind==='wave'?1:params.kind==='hero'||params.kind==='finale'?0:2;
 shader.render(renderer,null);ctx.setTransform(1,0,0,1,0,0);ctx.drawImage(glCanvas,0,0,W,H);ctx.scale(sx,sy);elements=[];
 // Flat backing behind text makes declared contrast meaningful; artwork stays in visual zone.
 ctx.fillStyle=colors.bg;ctx.fillRect(0,0,1280,224);ctx.fillRect(0,632,1280,88);
 text('chapter',`${String(spec.scenes.indexOf(scene)+1).padStart(2,'0')}   /   ${params.chapter||'CODEABLE VIDEO'}`,76,40,22,colors.accent,1110);
 text('headline',params.headline||spec.title,72,93+12*(1-ease(lt/.7)),58+6*ease(lt/.7),colors.ink,1136);
 line(76,211,1204,211,colors.line,1);
 renderVisual(params.kind,lt,p,params);
 const cue=(spec.captions||[]).find((c:any)=>t>=c.start&&t<c.end);
 if(cue)text('caption',cue.text,76,650,26,colors.ink,1128);
 ctx.fillStyle=colors.accent;ctx.fillRect(0,716,1280*t/spec.video.duration,4);
 return {png:encode?output.toDataURL('image/png').split(',')[1]:null,elements};
}
async function stream(n:number){
 for(let i=0;i<n;i++){
  const t=i/spec.video.fps;const f=frame(t,false);
  const meta=new TextEncoder().encode(JSON.stringify({frame:i,t,elements:f.elements}));
  const blob=await new Promise<Blob>((resolve,reject)=>output.toBlob(b=>b?resolve(b):reject(Error('PNG encoding failed')),'image/png'));
  const pixels=new Uint8Array(await blob.arrayBuffer());
  const payload=new Uint8Array(4+meta.length+pixels.length);new DataView(payload.buffer).setUint32(0,meta.length,true);
  payload.set(meta,4);payload.set(pixels,4+meta.length);
  const r=await fetch('/frame',{method:'POST',body:payload});if(!r.ok)throw Error('Frame receiver rejected '+i);
 }
 return n;
}
(window as any).__vch={ready:true,frame,stream,provenance:{name:'pdoom-primitives / Three.js / Canvas2D',upstream_commit:'a048746d25fa0333ca884fb79fe4482b9c89250d',full_upstream_engine:false,temporal_samples:1,shader_resolution_scale:0.5,typography_resolution_scale:1,graphics:renderer.getContext().getParameter(renderer.getContext().RENDERER)}};
