import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = ["x"]
import importlib.util

spec = importlib.util.spec_from_file_location("mob", ROOT/"evals/measure_onset_bias.py")
mob = importlib.util.module_from_spec(spec); spec.loader.exec_module(mob)
from fabench.score.core import _SILENCE_WORDS
from fabench.score.matched import nw_align


def errs(hyp, pattern):
    gold = mob.gold_of(pattern, "words"); out=[]
    for n, line in enumerate(open(hyp)):
        r = json.loads(line)
        g = gold.get(r.get("utt_id")); h = mob._ivs(r, "words")
        if not g or not h: continue
        gi=[x for x in g if x.label.lower() not in _SILENCE_WORDS]
        hi=[x for x in h if x.label.lower() not in _SILENCE_WORDS]
        gl=[x.label.lower() for x in gi]; hl=[x.label.lower() for x in hi]
        for a,b in nw_align(gl,hl).matched(gl,hl):
            out.append((hi[b].start-gi[a].start)*1000)
            out.append((hi[b].end  -gi[a].end  )*1000)
    return out

PAT="buckeye__paper__test__*.jsonl"
print(f"{'system':<16}{'n':>7}{'MAE':>8}{'signed':>9}{'MAE debiased':>14}{'drop':>8}")
for name, d in [("Speechmatics","evals/timestamp_asrs/speechmatics"),
                ("Parakeet-TDT","evals/timestamp_asrs/parakeet_tdt"),
                ("Whisper","evals/timestamp_asrs/whisper3"),
                ("Olign","evals/aligners/olign")]:
    p = ROOT/d/"en/buckeye/test/origin/hyp.jsonl"
    if not p.is_file(): print(f"{name:<16} missing {p}"); continue
    e = errs(p, PAT)
    if not e: print(f"{name:<16} no pairs"); continue
    mae = statistics.fmean(abs(x) for x in e)
    mu  = statistics.fmean(e)
    deb = statistics.fmean(abs(x-mu) for x in e)
    print(f"{name:<16}{len(e):>7}{mae:>8.1f}{mu:>9.1f}{deb:>14.1f}{100*(mae-deb)/mae:>7.0f}%")
