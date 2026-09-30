import os,json,subprocess,base64,logging,tempfile
from pathlib import Path
from dataclasses import dataclass,field
logger = logging.getLogger(__name__)
HAVE_CV2=False
try:
  import cv2, numpy as np; HAVE_CV2=True
except: pass

@dataclass
class VisionResult:
  frame_analyses:list=field(default_factory=list)
  description:str=""
  text_on_screen:list=field(default_factory=list)
  coherence_score:float=0.0
  frames_count:int=0

class VisionAnalyzer:
  def __init__(s,key="",url="https://openrouter.ai/api/v1",model="google/gemini-2.0-flash-exp:free"):
    s.api_key=key; s.api_url=url.rstrip("/")
    s.model=model; s.temperature=0.2; s._load_key()
  def _load_key(s):
    if s.api_key: return
    ef=Path.home()/".secrets/env"
    if ef.exists():
      for l in ef.read_text().split("\n"):
        if "OPENROUTER_API_KEY" in l and "=" in l:
          s.api_key=l.split("=",1)[1].strip().strip(chr(34)+chr(39))
  def _encode(s,path):
    with open(path,"rb") as f: return base64.b64encode(f.read()).decode()
  def _call(s,prompt,img=None,model=""):
    if not s.api_key: return ""
    m=model or s.model; c=prompt
    if img and Path(img).exists():
      c=[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+s._encode(img)}}]
    b=json.dumps({"model":m,"messages":[{"role":"user","content":c}],"temperature":s.temperature,"max_tokens":500})
    try:
      r=subprocess.run(["curl","-s","-m","60",s.api_url+"/chat/completions","-H","Content-Type: application/json","-H","Authorization: Bearer "+s.api_key,"-d",b],capture_output=True,text=True,timeout=90)
      if r.returncode: return ""
      d=json.loads(r.stdout or "{}")
      if "choices" in d: return d["choices"][0]["message"].get("content","")
    except: pass
    return ""
  def extract(s,vp,od,n=10):
    od=Path(od); od.mkdir(parents=True,exist_ok=True); frames=[]
    p=subprocess.run(["ffprobe","-v","q","-print_format","json","-show_format",str(vp)],capture_output=True,text=True)
    d=float(json.loads(p.stdout or"{}").get("format",{}).get("duration",0))
    if d<=0: return frames
    step=d/n
    for i in range(n):
      ts=i*step; o=od/f"f_{i:03d}.jpg"
      subprocess.run(["ffmpeg","-ss",str(ts),"-i",str(vp),"-vf","scale=1280:720","-vframes","1","-q:v","2","-y",str(o)],capture_output=True)
      if o.exists() and o.stat().st_size>1000: frames.append({"i":i,"p":str(o),"t":ts})
    return frames
  def analyze(s,vp,od=None):
    vp=Path(vp)
    if not vp.exists(): raise FileNotFoundError(str(vp))
    out=Path(od or tempfile.mkdtemp())
    fd=out/"vf"
    r=VisionResult()
    frames=s.extract(vp,fd,10)
    r.frames_count=len(frames)
    if not frames: return r
    fp="Describe this finance frame. Focus on text, numbers. 2-3 sentences."
    for f in frames:
      resp=s._call(fp,f["p"])
      if resp: r.frame_analyses.append({"f":f["i"],"t":f["t"],"x":resp})
    tp="List ALL visible text on screen. One per line."
    for f in [frames[0],frames[-1]]:
      resp=s._call(tp,f["p"])
      if resp:
        for l in resp.split("\n"):
          l=l.strip(); u=l.upper()
          if l and len(l)>2 and not any(k in u for k in ["HERE","NOTE","SCREEN"]): r.text_on_screen.append(l)
    if r.frame_analyses:
      dp="Summarize this finance video."
      for fa in r.frame_analyses: dp+=f"\n- {fa["t"]:.1f}s: {fa["x"]}"
      r.description=s._call(dp) or ""
    if r.frame_analyses: r.coherence_score=min(1.0,len(r.frame_analyses)/10*0.8)
    return r
if __name__=="__main__":
  import argparse; a=argparse.ArgumentParser(); a.add_argument("--video",required=True); args=a.parse_args()
  va=VisionAnalyzer(); r=va.analyze(Path(args.video))
  print(json.dumps({"frames":r.frames_count,"analyses":len(r.frame_analyses),"desc":r.description[:200],"text":r.text_on_screen[:8],"score":round(r.coherence_score,2)},indent=2,ensure_ascii=False))