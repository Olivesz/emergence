// wwcpu2.js — SAP-2 CPU + assembler, ported from the verified Python (sap2.py,
// asm2.py, modules.py). Same NAND+DFF netlist; topological single-pass settle so
// the whole machine runs live. Memory is gate-level: 256 rows of 8 flip-flops.

class Circuit {
  constructor() { this.vals=[]; this.nands=[]; this.dffs=[]; this._n=0; this._order=null;
    this.GND=this.net(0); this.VCC=this.net(1); }
  net(init=0){ const i=this._n++; this.vals[i]=init; return i; }
  bus(w,init=0){ const b=[]; for(let k=0;k<w;k++) b.push(this.net((init>>k)&1)); return b; }
  nand(a,b){ const o=this.net(); this.nands.push([o,a,b]); this._order=null; return o; }
  dff(d,en=null,clr=null,init=0){ const q=this.net(init); this.dffs.push({q,d,en,clr,init}); return q; }
  not_(a){ return this.nand(a,a); }
  and_(a,b){ return this.not_(this.nand(a,b)); }
  or_(a,b){ return this.nand(this.not_(a),this.not_(b)); }
  xor_(a,b){ const n=this.nand(a,b); return this.nand(this.nand(a,n),this.nand(n,b)); }
  andList(xs){ if(!xs.length) return this.VCC; let a=xs[0]; for(let i=1;i<xs.length;i++)a=this.and_(a,xs[i]); return a; }
  orList(xs){ if(!xs.length) return this.GND; let a=xs[0]; for(let i=1;i<xs.length;i++)a=this.or_(a,xs[i]); return a; }
  mux2(sel,a,b){ const ns=this.not_(sel); return this.or_(this.and_(ns,a),this.and_(sel,b)); }
  _buildOrder(){
    const producer={}; for(let i=0;i<this.nands.length;i++) producer[this.nands[i][0]]=i;
    const state=new Int8Array(this.nands.length); const order=[];
    for(let s=0;s<this.nands.length;s++){
      if(state[s]) continue;
      const stack=[[s,0]];
      while(stack.length){
        const [idx,phase]=stack.pop();
        if(phase===0){ if(state[idx]===2) continue; state[idx]=1; stack.push([idx,1]);
          const g=this.nands[idx];
          for(const inp of [g[1],g[2]]){ const p=producer[inp]; if(p!==undefined&&state[p]===0) stack.push([p,0]); } }
        else { if(state[idx]!==2){ state[idx]=2; order.push(idx); } }
      }
    }
    this._order=order;
  }
  settle(){ if(this._order===null) this._buildOrder(); const v=this.vals; v[this.GND]=0; v[this.VCC]=1;
    const nd=this.nands; for(const idx of this._order){ const g=nd[idx]; v[g[0]]=(v[g[1]]&&v[g[2]])?0:1; } }
  commitDffs(){ const v=this.vals; const nxt=[];
    for(const ff of this.dffs){ let nv;
      if(ff.clr!==null && v[ff.clr]) nv=0;
      else if(ff.en!==null && !v[ff.en]) nv=v[ff.q];
      else nv=v[ff.d]; nxt.push([ff.q,nv]); }
    for(const [q,nv] of nxt) v[q]=nv; }
  get(n){ return this.vals[n]; }
  getbus(b){ let s=0; for(let k=0;k<b.length;k++) s|=(this.vals[b[k]]&1)<<k; return s; }
  setbus(b,val){ for(let k=0;k<b.length;k++) this.vals[b[k]]=(val>>k)&1; }
  dffsByQ(q){ if(!this._byQ||this._byQ.size!==this.dffs.length){ this._byQ=new Map(); for(const ff of this.dffs) this._byQ.set(ff.q,ff); }
    const ff=this._byQ.get(q); if(!ff) throw new Error("no dff"); return ff; }
}

// ---- datapath helpers ----
function fullAdder(c,a,b,cin){ const s1=c.xor_(a,b),s=c.xor_(s1,cin);
  return [s, c.or_(c.and_(a,b),c.and_(s1,cin))]; }
function addSub(c,A,B,sub){ const n=Math.max(A.length,B.length); let carry=sub; const S=[];
  for(let k=0;k<n;k++){ const a=k<A.length?A[k]:c.GND; let b=k<B.length?B[k]:c.GND; b=c.xor_(b,sub);
    const [s,co]=fullAdder(c,a,b,carry); carry=co; S.push(s);} return [S,carry]; }
function decoder(c,sel){ const n=sel.length,inv=sel.map(s=>c.not_(s)),lines=[];
  for(let i=0;i<(1<<n);i++){ const t=[]; for(let k=0;k<n;k++) t.push(((i>>k)&1)?sel[k]:inv[k]); lines.push(c.andList(t)); }
  return lines; }
function muxOnehot(c,selects,buses){ const w=buses[0].length,out=[];
  for(let bit=0;bit<w;bit++){ const t=[]; for(let i=0;i<buses.length;i++) t.push(c.and_(selects[i],buses[i][bit])); out.push(c.orList(t)); }
  return out; }
function matchConst(c,bus,val){ const t=[]; for(let i=0;i<bus.length;i++) t.push(((val>>i)&1)?bus[i]:c.not_(bus[i])); return c.andList(t); }

const ALU_OPS={ADD:0,SUB:1,AND:2,OR:3,XOR:4,NOT:5,SHL:6,SHR:7,INC:8,DEC:9,PASSA:10,PASSB:11};
function alu(c,A,B,sel){ const n=A.length, one=[c.VCC].concat(Array(n-1).fill(c.GND));
  const [add,cadd]=addSub(c,A,B,c.GND); const [sub,csub]=addSub(c,A,B,c.VCC); const borrow=c.not_(csub);
  const andb=A.map((a,i)=>c.and_(a,B[i])), orb=A.map((a,i)=>c.or_(a,B[i])), xorb=A.map((a,i)=>c.xor_(a,B[i]));
  const notb=A.map(a=>c.not_(a));
  const shl=[c.GND].concat(A.slice(0,n-1)); const cshl=A[n-1];
  const shr=A.slice(1,n).concat([c.GND]); const cshr=A[0];
  const [inc,cinc]=addSub(c,A,one,c.GND); const [dec,cdec]=addSub(c,A,one,c.VCC); const decb=c.not_(cdec);
  const cands=[add,sub,andb,orb,xorb,notb,shl,shr,inc,dec,A,B];
  const carrs=[cadd,borrow,c.GND,c.GND,c.GND,c.GND,cshl,cshr,cinc,decb,c.GND,c.GND];
  const lines=decoder(c,sel);
  const result=muxOnehot(c,lines.slice(0,cands.length),cands);
  const carry=c.orList(carrs.map((cc,i)=>c.and_(lines[i],cc)));
  const zero=c.not_(c.orList(result)); const sign=result[n-1];
  return [result,carry,zero,sign]; }

// ---- ISA ----
const OPS={NOP:0x00,HLT:0x01,LDA:0x10,STA:0x11,LDI:0x12,MAB:0x13,MBA:0x14,LDB:0x15,LBI:0x16,
  LDX:0x17,STX:0x18,ADD:0x20,SUB:0x21,ANA:0x22,ORA:0x23,XRA:0x24,CMA:0x25,INR:0x26,DCR:0x27,
  SHL:0x28,SHR:0x29,ADI:0x2A,SUI:0x2B,ANI:0x2C,ORI:0x2D,XRI:0x2E,CMP:0x30,CPI:0x31,
  JMP:0x40,JZ:0x41,JNZ:0x42,JC:0x43,JNC:0x44,CALL:0x50,RET:0x51,PUSH:0x52,POP:0x53,IN:0x60,OUT:0x61};
const MNEM={}; for(const k in OPS) MNEM[OPS[k]]=k;
const HAS_OPERAND=new Set(["LDA","STA","LDI","LDB","LBI","ADI","SUI","ANI","ORI","XRI","CPI",
  "JMP","JZ","JNZ","JC","JNC","CALL"]);
const FO=[["PCo","MARi"],["RAMo","MDRi","PCc"]];
const A_="alu", P_="pci";
const MICRO={
  NOP:[["NI"]], HLT:[["HALT","NI"]],
  LDA:[...FO,["MDRo","MARi"],["RAMo","Ai","NI"]],
  STA:[...FO,["MDRo","MARi"],["Ao","RAMw","NI"]],
  LDI:[["PCo","MARi"],["RAMo","Ai","PCc","NI"]],
  MAB:[["Ao","Bi","NI"]], MBA:[["Bo","Ai","NI"]],
  LDB:[...FO,["MDRo","MARi"],["RAMo","Bi","NI"]],
  LBI:[["PCo","MARi"],["RAMo","Bi","PCc","NI"]],
  LDX:[["Bo","MARi"],["RAMo","Ai","NI"]],
  STX:[["Bo","MARi"],["Ao","RAMw","NI"]],
  ADD:[[{alu:"ADD"},"ALUo","Ai","FL","NI"]], SUB:[[{alu:"SUB"},"ALUo","Ai","FL","NI"]],
  ANA:[[{alu:"AND"},"ALUo","Ai","FL","NI"]], ORA:[[{alu:"OR"},"ALUo","Ai","FL","NI"]],
  XRA:[[{alu:"XOR"},"ALUo","Ai","FL","NI"]], CMA:[[{alu:"NOT"},"ALUo","Ai","FL","NI"]],
  INR:[[{alu:"INC"},"ALUo","Ai","FL","NI"]], DCR:[[{alu:"DEC"},"ALUo","Ai","FL","NI"]],
  SHL:[[{alu:"SHL"},"ALUo","Ai","FL","NI"]], SHR:[[{alu:"SHR"},"ALUo","Ai","FL","NI"]],
  ADI:[...FO,[{alu:"ADD"},"ALUbMDR","ALUo","Ai","FL","NI"]],
  SUI:[...FO,[{alu:"SUB"},"ALUbMDR","ALUo","Ai","FL","NI"]],
  ANI:[...FO,[{alu:"AND"},"ALUbMDR","ALUo","Ai","FL","NI"]],
  ORI:[...FO,[{alu:"OR"},"ALUbMDR","ALUo","Ai","FL","NI"]],
  XRI:[...FO,[{alu:"XOR"},"ALUbMDR","ALUo","Ai","FL","NI"]],
  CMP:[[{alu:"SUB"},"FL","NI"]], CPI:[...FO,[{alu:"SUB"},"ALUbMDR","FL","NI"]],
  JMP:[...FO,["MDRo","PCi","NI"]],
  JZ:[...FO,["MDRo",{pci:"Z"},"NI"]], JNZ:[...FO,["MDRo",{pci:"nZ"},"NI"]],
  JC:[...FO,["MDRo",{pci:"C"},"NI"]], JNC:[...FO,["MDRo",{pci:"nC"},"NI"]],
  CALL:[...FO,["SPo","MARi"],["PCo","RAMw","SPdec"],["MDRo","PCi","NI"]],
  RET:[["SPinc"],["SPo","MARi"],["RAMo","PCi","NI"]],
  PUSH:[["SPo","MARi"],["Ao","RAMw","SPdec","NI"]],
  POP:[["SPinc"],["SPo","MARi"],["RAMo","Ai","NI"]],
  IN:[["INo","Ai","NI"]], OUT:[["Ao","OUTi","NI"]],
};
const SIGNALS=["PCo","MDRo","Ao","Bo","ALUo","RAMo","SPo","INo","MARi","PCi","IRi","MDRi","Ai","Bi",
  "OUTi","RAMw","PCc","SPinc","SPdec","FL","HALT","NI","ALUbMDR"];
const DRIVERS=["PCo","MDRo","Ao","Bo","ALUo","RAMo","SPo","INo"];

class SAP2 {
  constructor(program, inval=0){
    const c=this.c=new Circuit();
    const prog=(program||[]).slice(); while(prog.length<256) prog.push(0);
    this.in_val=inval&0xFF;
    const raw=(init=0)=>c.dff(c.GND,c.GND,null,init);
    const b8=(init=0)=>{const a=[]; for(let k=0;k<8;k++) a.push(raw((init>>k)&1)); return a;};
    this.A=b8(); this.B=b8(); this.MAR=b8(); this.PC=b8(); this.IR=b8(); this.MDR=b8();
    this.SP=b8(0xFF); this.Zf=raw(); this.Cf=raw(); this.Sf=raw();
    this.Tc=[raw(),raw(),raw()];
    // memory: 256 rows of 8 flip-flops, preloaded with the program image
    this.RAMQ=[]; for(let w=0;w<256;w++){ const row=[]; for(let b=0;b<8;b++) row.push(raw((prog[w]>>b)&1)); this.RAMQ.push(row); }
    const memsel=decoder(c,this.MAR);
    this.ram_out=muxOnehot(c,memsel,this.RAMQ);
    this.in_nets=c.bus(8);
    const RQ=this.RAMQ;
    this.RAM=new Proxy({},{   // cpu.RAM[a] reads or writes memory row a's flip-flops
      get:(t,k)=>k==="length"?256:(typeof k==="string"&&/^\d+$/.test(k)?c.getbus(RQ[+k]):undefined),
      set:(t,k,v)=>{ c.setbus(RQ[+k],v&0xFF); c.settle(); return true; }});
    const stepline=decoder(c,this.Tc);
    const opmatch={}; for(const nm in OPS) opmatch[nm]=matchConst(c,this.IR,OPS[nm]);
    const condnet={Z:this.Zf,nZ:c.not_(this.Zf),C:this.Cf,nC:c.not_(this.Cf)};
    // collect minterms
    const mint={}; for(const s of SIGNALS) mint[s]=[]; const aluMint=[];
    const fetchTerms={PCo:[0],MARi:[0],RAMo:[1],IRi:[1],PCc:[1]};
    for(const name in MICRO){ const steps=MICRO[name];
      for(let j=0;j<steps.length;j++){ const tstep=j+2;
        for(const tok of steps[j]){
          if(tok&&tok.alu) aluMint.push([name,tstep,tok.alu]);
          else if(tok&&tok.pci) mint["PCi"].push([name,tstep,tok.pci]);
          else mint[tok].push([name,tstep,null]);
        } } }
    const term=(nm,ts,cd)=>{ const base=c.and_(opmatch[nm],stepline[ts]); return cd===null?base:c.and_(base,condnet[cd]); };
    const sig={};
    for(const s of SIGNALS){ const terms=(fetchTerms[s]||[]).map(t=>c.and_(c.VCC,stepline[t]));
      for(const [nm,ts,cd] of mint[s]) terms.push(term(nm,ts,cd));
      sig[s]=terms.length?c.orList(terms):c.GND; }
    const selbits=[];
    for(let b=0;b<4;b++){ const terms=[];
      for(const [nm,ts,op] of aluMint) if((ALU_OPS[op]>>b)&1) terms.push(c.and_(opmatch[nm],stepline[ts]));
      selbits.push(terms.length?c.orList(terms):c.GND); }
    this.sig=sig; this.HALT=sig["HALT"];
    const aluB=[]; for(let k=0;k<8;k++) aluB.push(c.mux2(sig["ALUbMDR"],this.B[k],this.MDR[k]));
    const [aluR,aluC,aluZ,aluS]=alu(c,this.A,aluB,selbits);
    const srcs=[this.PC,this.MDR,this.A,this.B,aluR,this.ram_out,this.SP,this.in_nets];
    const bus=muxOnehot(c,DRIVERS.map(d=>sig[d]),srcs); this.bus=bus; this.RAMw=sig["RAMw"];
    const [pcInc]=addSub(c,this.PC,[c.VCC].concat(Array(7).fill(c.GND)),c.GND);
    const [spInc]=addSub(c,this.SP,[c.VCC].concat(Array(7).fill(c.GND)),c.GND);
    const [spDec]=addSub(c,this.SP,[c.VCC].concat(Array(7).fill(c.GND)),c.VCC);
    const [tInc]=addSub(c,this.Tc,[c.VCC,c.GND,c.GND],c.GND);
    const wire=(q,d,en)=>{ const ff=c.dffsByQ(q); ff.d=d; ff.en=en; };
    for(let k=0;k<8;k++){
      wire(this.MAR[k],bus[k],sig["MARi"]); wire(this.IR[k],bus[k],sig["IRi"]);
      wire(this.MDR[k],bus[k],sig["MDRi"]); wire(this.A[k],bus[k],sig["Ai"]); wire(this.B[k],bus[k],sig["Bi"]);
      const pcNxt=c.mux2(sig["PCi"],pcInc[k],bus[k]);
      wire(this.PC[k],c.mux2(c.or_(sig["PCc"],sig["PCi"]),this.PC[k],pcNxt),c.VCC);
      const spId=c.mux2(sig["SPinc"],spDec[k],spInc[k]);
      wire(this.SP[k],c.mux2(c.or_(sig["SPinc"],sig["SPdec"]),this.SP[k],spId),c.VCC);
    }
    wire(this.Zf,aluZ,sig["FL"]); wire(this.Cf,aluC,sig["FL"]); wire(this.Sf,aluS,sig["FL"]);
    for(let b=0;b<3;b++) wire(this.Tc[b],c.mux2(sig["NI"],tInc[b],c.GND),c.VCC);
    for(let w=0;w<256;w++){ const wen=c.and_(sig["RAMw"],memsel[w]); for(let b=0;b<8;b++) wire(RQ[w][b],bus[b],wen); }
    this.O=[]; for(let k=0;k<8;k++) this.O.push(c.dff(bus[k],sig["OUTi"],null,0));
    c.settle();
  }
  step(){ const c=this.c; c.setbus(this.in_nets,this.in_val); c.settle(); c.commitDffs(); c.settle(); }
  tstate(){ return this.c.getbus(this.Tc); }
  opcode(){ return this.c.getbus(this.IR); }
  activeSignals(){ return SIGNALS.filter(s=>this.c.get(this.sig[s])); }
  snapshot(){ const g=this.c; return {T:this.tstate(),PC:g.getbus(this.PC),MAR:g.getbus(this.MAR),
    IR:g.getbus(this.IR),op:this.opcode(),A:g.getbus(this.A),B:g.getbus(this.B),MDR:g.getbus(this.MDR),
    SP:g.getbus(this.SP),OUT:g.getbus(this.O),Z:g.get(this.Zf),C:g.get(this.Cf),S:g.get(this.Sf),
    bus:g.getbus(this.bus),halt:g.get(this.HALT),sigs:this.activeSignals()}; }
}

// ---- assembler (mirrors asm2.py) ----
function assemble2(src){
  const labels={},equ={}; const items=[]; let addr=0;
  const num=(tok)=>{ if(tok in labels) return labels[tok]; if(tok in equ) return equ[tok];
    const v=parseInt(tok, tok.startsWith("0x")||tok.startsWith("0X")?16:10);
    if(Number.isNaN(v)) throw new Error("bad operand: "+tok); return v; };
  const lines=src.replace(/\r/g,"").split("\n");
  for(let raw of lines){ let line=raw.split(";")[0].trim(); if(!line) continue;
    while(line.includes(":")){ const idx=line.indexOf(":"); const head=line.slice(0,idx).trim();
      if(head.includes(" ")||OPS[head.toUpperCase()]!==undefined) break;
      labels[head]=addr; line=line.slice(idx+1).trim(); if(!line) break; }
    if(!line) continue;
    const parts=line.split(/\s+/); const mn=parts[0].toUpperCase();
    if(mn==="ORG"){ addr=num(parts[1]); continue; }
    if(parts.length>=3 && parts[1]==="="){ equ[parts[0]]=num(parts[2]); continue; }
    if(mn==="DB"){ items.push([addr,"DB",parts.slice(1)]); addr+=parts.length-1; continue; }
    if(OPS[mn]===undefined) throw new Error("unknown mnemonic "+mn);
    items.push([addr,mn,parts.slice(1)]); addr += HAS_OPERAND.has(mn)?2:1;
  }
  const image=new Array(256).fill(0);
  for(const [a,mn,args] of items){
    if(mn==="DB"){ for(let i=0;i<args.length;i++) image[a+i]=num(args[i])&0xFF; continue; }
    image[a]=OPS[mn]; if(HAS_OPERAND.has(mn)) image[a+1]=num(args[0])&0xFF;
  }
  return {image,labels};
}

if(typeof module!=="undefined"&&module.exports) module.exports={Circuit,SAP2,assemble2,OPS,MNEM,SIGNALS,DRIVERS,HAS_OPERAND};
