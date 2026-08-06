#!/usr/bin/env python3
"""Generate real-adder.html (+ _artifact) : an INTERACTIVE viewer that runs the
ACTUAL verified half-adder glider field in raw B3/S23 -- real gliders, real Snarks,
real duplicators, real annihilation hits -- for whichever A,B you pick. No schematic."""
STATES = {}
for A in (0, 1):
    for B in (0, 1):
        STATES[(A, B)] = open(f"real_ha_{A}{B}.rle").read().strip()

def js_state(A, B):
    return f'"{A}{B}":`{STATES[(A,B)]}`'
STATE_JS = ",\n".join(js_state(A, B) for A in (0, 1) for B in (0, 1))

BODY = r'''<style>
:root{--ground:#07090e;--panel:#0d1017;--panel2:#11151d;--edge:#1d2431;--ink:#e9edf4;
 --dim:#8a94a6;--faint:#525c6c;--cyan:#3fe9ff;--amber:#e0a53a;--green:#5dff9b;--violet:#b98cff;
 --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",sans-serif;}
*{box-sizing:border-box}
html,body{margin:0;background:radial-gradient(1100px 650px at 72% -8%,#10161f 0%,var(--ground) 58%);
 color:var(--ink);font-family:var(--sans);min-height:100vh}
body{padding:18px 20px 40px;max-width:1180px;margin:0 auto}
h1{font-size:17px;letter-spacing:.1em;text-transform:uppercase;margin:0;font-weight:650}
h1 b{color:var(--cyan)}
.sub{color:var(--dim);font-size:12.5px;margin:6px 0 0;max-width:92ch;line-height:1.55}
.sub b{color:var(--ink)} .sub code{color:var(--amber);font-family:var(--mono)}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0 10px;
 background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:11px 13px}
.lbl{font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin-right:2px}
button{font-family:var(--sans);font-size:12.5px;color:var(--ink);background:var(--panel2);
 border:1px solid var(--edge);border-radius:8px;padding:8px 13px;cursor:pointer;transition:.15s}
button:hover{border-color:var(--cyan);color:var(--cyan)}
button.on{background:var(--cyan);color:#04212a;border-color:var(--cyan);font-weight:700}
.grow{flex:1}
input[type=range]{accent-color:var(--cyan);width:120px}
.readout{font-family:var(--mono);font-size:11.5px;color:var(--faint);white-space:nowrap}
.eqbar{display:flex;align-items:center;gap:16px;flex-wrap:wrap;justify-content:center;
 background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--edge);
 border-radius:12px;padding:12px 18px;margin-bottom:12px}
.eq{font-family:var(--mono);font-size:22px;font-weight:600}
.eq .a{color:var(--cyan)} .eq .b{color:var(--amber)} .eq .s{color:var(--green);font-size:26px}
.eq .op{color:var(--faint)}
.note{font-family:var(--mono);font-size:11px;color:var(--dim)}
.wrap{position:relative;background:#05070b;border:1px solid var(--edge);border-radius:12px;overflow:hidden}
canvas{display:block;width:100%;height:600px;cursor:grab}
canvas:active{cursor:grabbing}
.focus{position:absolute;top:10px;left:10px;display:flex;gap:6px}
.focus button{font-size:11px;padding:6px 10px}
.hud{position:absolute;top:10px;right:12px;font-family:var(--mono);font-size:11px;color:var(--faint);text-align:right}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--dim);margin:12px 0 0}
.legend b{color:var(--ink)}
.foot{color:var(--faint);font-size:11px;margin-top:14px;border-top:1px solid var(--edge);padding-top:12px;line-height:1.65}
.foot a{color:var(--cyan);text-decoration:none}
</style>
<h1>The <b>real</b> glider half-adder — watch it compute</h1>
<p class="sub">This is <b>not</b> a diagram. Below runs the <b>actual</b> half-adder circuit in raw
 Conway's Life — every cell obeying only <code>B3/S23</code>. Pick A and B (each a bit), and the real
 <b>input gliders</b> fly in, hit <b>duplicators</b> that fan them out, route through <b>Snark
 reflectors</b>, and collide: two gliders <b>annihilate</b> (that's the XOR / inhibit — the sum), or
 <b>merge</b> into one (that's the AND — the carry). Zoom in to watch the individual hits. Verified
 glider-by-glider: every catalyst is restored to the exact cell.</p>

<div class="bar">
 <span class="lbl">A</span><button id="btnA">1</button>
 <span class="lbl" style="margin-left:8px">B</span><button id="btnB">1</button>
 <div style="width:14px"></div>
 <button id="play" class="on">Pause</button>
 <button id="step">Step</button>
 <button id="reset">Restart</button>
 <span class="lbl" style="margin-left:8px">Speed</span><input id="speed" type="range" min="1" max="8" value="4">
 <div class="grow"></div>
 <div class="readout" id="ro">gen 0</div>
</div>

<div class="eqbar">
 <div class="eq"><span class="a" id="eqA">1</span> <span class="op">+</span> <span class="b" id="eqB">1</span>
  <span class="op">=</span> <span class="s" id="eqS"></span></div>
 <div class="note" id="eqNote"></div>
</div>

<div class="wrap">
 <canvas id="cv"></canvas>
 <div class="focus">
  <button id="fSum" class="on">Sum stage (XOR)</button>
  <button id="fCarry">Carry stage (AND)</button>
  <button id="fAll">Whole circuit</button>
 </div>
 <div class="hud" id="hud"></div>
</div>

<div class="legend">
 <span><b>a glider</b> = one moving bit (5 cells, crawls diagonally)</span>
 <span><b>duplicator</b> = fan-out (1 glider &#8594; 2)</span>
 <span><b>Snark</b> = 90&#176; reflector</span>
 <span><b>hit</b> = collision: annihilate (XOR) or merge (AND)</span>
</div>
<p class="foot"><b>What you're seeing:</b> the real routed half-adder — routed XOR (sum) atop the routed
 AND (carry), driven by the same A,B. Every gate's fan-out is a real duplicator; the sum is computed by
 real glider annihilations, the carry by a real merge through two Snarks. Truth table verified in the
 raw rule (<code>ha_xor.py</code>/<code>ha_full.py</code>). Two of these make a full adder; the real
 multi-bit machine at scale is Nicholas Carlini's 137,712-cell glider adder (we verified it computes
 6+5=11). More real components — Gosper guns, gun grids, streams, crossovers, a 1-bit glider memory —
 run in <a href="life-viewer.html">life-viewer.html</a>.</p>

<script>
"use strict";
const key=(x,y)=>x+","+y, unkey=k=>{const i=k.indexOf(",");return[+k.slice(0,i),+k.slice(i+1)];};
function step(cells){const nb=new Map();
 for(const k of cells){const[x,y]=unkey(k);
  for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){if(!dx&&!dy)continue;
   const kk=key(x+dx,y+dy);nb.set(kk,(nb.get(kk)||0)+1);}}
 const nx=new Set();for(const[k,n]of nb){if(n===3||(n===2&&cells.has(k)))nx.add(k);}return nx;}
function bbox(c){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;for(const k of c){const[x,y]=unkey(k);
 if(x<x0)x0=x;if(y<y0)y0=y;if(x>x1)x1=x;if(y>y1)y1=y;}return c.size?[x0,y0,x1,y1]:[0,0,0,0];}
function parseRLE(txt){const s=new Set();let x=0,y=0,num="";
 let body=txt.substring(txt.indexOf("\n")+1).replace(/\s+/g,"");
 for(const ch of body){if(ch>="0"&&ch<="9"){num+=ch;continue;}
  const n=num?parseInt(num):1;num="";
  if(ch==="b")x+=n;else if(ch==="o"){for(let i=0;i<n;i++)s.add(key(x++,y));}
  else if(ch==="$"){y+=n;x=0;}else if(ch==="!")break;}
 return s;}

const STATES={__STATES__};
const RES={"00":[0,0],"01":[1,0],"10":[1,0],"11":[0,1]};
const seeds={}; for(const k in STATES) seeds[k]=parseRLE(STATES[k]);

const cv=document.getElementById("cv"),ctx=cv.getContext("2d");
let A=1,B=1,cells=new Set(),gen=0,playing=true,scale=1,camx=0,camy=0,acc=0,seed=new Set();
let curRegion="sum";
function fit(region){
 const[x0,y0,x1,y1]=bbox(seed.size?seed:new Set(["0,0"]));
 let rx0=x0,ry0=y0,rx1=x1,ry1=y1;
 if(region==="sum")ry1=Math.min(y1,y0+470);
 else if(region==="carry")ry0=Math.max(y0,y1-330);
 const bw=Math.max(1,rx1-rx0+1),bh=Math.max(1,ry1-ry0+1);
 scale=Math.max(.6,Math.min(cv.width/(bw+8),cv.height/(bh+8)));
 camx=(rx0+rx1)/2;camy=(ry0+ry1)/2;fullClear=true;render();
}
function w2s(x,y){return[cv.width/2+(x-camx)*scale,cv.height/2+(y-camy)*scale];}
function resize(){const r=cv.getBoundingClientRect();cv.width=r.width;cv.height=r.height;fullClear=true;}
let fullClear=true;
function render(){
 // motion trails: fully clear only on camera/state change, else fade so gliders streak
 if(fullClear){ctx.fillStyle="#05070b";ctx.fillRect(0,0,cv.width,cv.height);fullClear=false;}
 else{ctx.fillStyle="rgba(5,7,11,0.16)";ctx.fillRect(0,0,cv.width,cv.height);}
 const r=Math.max(2,scale*.95),glow=scale>=2.5;
 if(glow){ctx.shadowColor="#3fe9ff";ctx.shadowBlur=Math.min(8,scale);}
 ctx.fillStyle="#9dedff";
 for(const k of cells){const[x,y]=unkey(k);const[sx,sy]=w2s(x,y);
  if(sx<-3||sy<-3||sx>cv.width+3||sy>cv.height+3)continue;ctx.fillRect(sx,sy,r,r);}
 ctx.shadowBlur=0;
 document.getElementById("ro").textContent="gen "+gen+" · "+cells.size+" cells";
 document.getElementById("hud").textContent="scale "+scale.toFixed(1)+"×  ·  drag to pan · scroll to zoom";
}
function load(region){seed=new Set(seeds[A+""+B]);cells=new Set(seed);gen=0;fullClear=true;fit(region||curRegion);}
const SETTLE=2600;   // after the computation resolves, loop so it always animates
function advance(){cells=step(cells);gen++;}
function frame(){if(playing){const spd=+document.getElementById("speed").value;
 for(let i=0;i<spd;i++)advance();
 if(gen>SETTLE){cells=new Set(seed);gen=0;fullClear=true;}
 render();}requestAnimationFrame(frame);}

function setResult(){
 const r=RES[A+""+B];const sm=r[0],cy=r[1],total=A+B;
 document.getElementById("eqA").textContent=A;
 document.getElementById("eqB").textContent=B;
 document.getElementById("eqS").textContent=(cy?"1":"0")+sm+"₂ = "+total;
 document.getElementById("eqNote").textContent="sum bit = "+sm+", carry = "+cy
  +(cy?"  (carry out to the next bit)":"");
}
function setAB(){document.getElementById("btnA").textContent=A;document.getElementById("btnB").textContent=B;
 document.getElementById("btnA").classList.toggle("on",!!A);
 document.getElementById("btnB").classList.toggle("on",!!B);
 setResult();load();}

document.getElementById("btnA").onclick=()=>{A^=1;setAB();};
document.getElementById("btnB").onclick=()=>{B^=1;setAB();};
document.getElementById("play").onclick=function(){playing=!playing;this.textContent=playing?"Pause":"Play";};
document.getElementById("step").onclick=()=>{advance();render();};
document.getElementById("reset").onclick=()=>load();
function focusBtn(id,region){document.getElementById(id).onclick=function(){
 curRegion=region;document.querySelectorAll(".focus button").forEach(b=>b.classList.remove("on"));
 this.classList.add("on");fit(region);};}
focusBtn("fSum","sum");focusBtn("fCarry","carry");focusBtn("fAll","all");

let drag=null;
cv.addEventListener("mousedown",e=>drag=[e.clientX,e.clientY,camx,camy]);
window.addEventListener("mouseup",()=>drag=null);
window.addEventListener("mousemove",e=>{if(!drag)return;
 camx=drag[2]-(e.clientX-drag[0])/scale;camy=drag[3]-(e.clientY-drag[1])/scale;fullClear=true;render();});
cv.addEventListener("wheel",e=>{e.preventDefault();const f=e.deltaY<0?1.15:1/1.15;
 scale=Math.max(.3,Math.min(40,scale*f));fullClear=true;render();},{passive:false});
window.addEventListener("resize",()=>{resize();fit(curRegion);});
resize();setAB();frame();
</script>'''

html = BODY.replace("__STATES__", "\n" + STATE_JS + "\n")
open("real-adder_artifact.html", "w").write(html)
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>The real glider half-adder</title>\n</head>\n<body>\n'
        + html + "\n</body>\n</html>\n")
open("real-adder.html", "w").write(full)
print("wrote real-adder.html + real-adder_artifact.html")
