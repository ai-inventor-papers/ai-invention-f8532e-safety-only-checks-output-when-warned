import subprocess, sys, json, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
SKILL="/ai-inventor/.claude/skills/aii-web-tools"
PY=f"{SKILL}/../.ability_client_venv/bin/python"
SCRIPT=f"{SKILL}/scripts/aii_fast_web_fetch.py"
# jobs file: json list of {"url":..,"pattern":..,"label":..,"ctx":int,"max":int,"i":bool}
jobs=json.load(open(sys.argv[1]))
def run(j):
    cmd=[PY,SCRIPT,"grep","--url",j["url"],"--pattern",j["pattern"],
         "--max-matches",str(j.get("max",12)),"--context-chars",str(j.get("ctx",320))]
    if j.get("i"): cmd.append("-i")
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=420)
        out=r.stdout+("\nSTDERR:"+r.stderr[-300:] if r.returncode else "")
    except Exception as e:
        out=f"EXC {e}"
    return j,out
with ThreadPoolExecutor(max_workers=5) as ex:
    for j,out in ex.map(run,jobs):
        out="\n".join(l for l in out.splitlines() if "fitz" not in l)
        print(f"\n########## {j['label']} | {j['url']} | /{j['pattern']}/")
        print(out[:j.get("cap",6000)])
