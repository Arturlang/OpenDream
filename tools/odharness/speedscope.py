"""Usage: python -I speedscope.py <file.speedscope.json> [thread-substring|auto] [topN] [focus-substring]
Ranks inclusive and self time on one thread. 'auto' picks the thread containing GameLoop/Run.
With focus, only stacks containing that frame are counted, and inclusive time is relative to it."""
import json, sys
from collections import Counter

d = json.load(open(sys.argv[1], encoding="utf-8"))
frames = [f["name"] for f in d["shared"]["frames"]]
want = sys.argv[2] if len(sys.argv) > 2 else "auto"
top = int(sys.argv[3]) if len(sys.argv) > 3 else 40
focus = sys.argv[4] if len(sys.argv) > 4 else None

def stacks(p):
    """Yield (stack tuple, weight) for sampled or evented profiles."""
    if p["type"] == "sampled":
        for s, w in zip(p["samples"], p["weights"]):
            yield tuple(s), w
    else:
        st, last = [], p["startValue"]
        for e in p["events"]:
            if st and e["at"] > last:
                yield tuple(st), e["at"] - last
            last = e["at"]
            if e["type"] == "O":
                st.append(e["frame"])
            else:
                st.pop()

profiles = d["profiles"]
print("threads:")
summary = []
for p in profiles:
    tot = sum(w for _, w in stacks(p))
    names = Counter()
    for s, w in stacks(p):
        names.update({frames[i] for i in s})
    hit = any("GameLoop.Run" in n for n in names)
    summary.append((tot, p["name"], hit, p))
for tot, n, hit, _ in sorted(summary, key=lambda x: -x[0])[:12]:
    print(f"  {tot:12.1f}  {'MAIN? ' if hit else ''}{n}")

if want == "auto":
    chosen = max((x for x in summary if x[2]), key=lambda x: x[0])[3]
else:
    chosen = next(x[3] for x in summary if want in x[1])
print(f"\nthread: {chosen['name']}")

inc, self_ = Counter(), Counter()
total = 0
for s, w in stacks(chosen):
    names = [frames[i] for i in s]
    if focus:
        idx = next((i for i, n in enumerate(names) if focus in n), None)
        if idx is None:
            continue
        names = names[idx:]
    total += w
    for n in set(names):
        inc[n] += w
    # The sampler appends CPU_TIME/UNMANAGED_CODE_TIME pseudo-frames; self time belongs to the real frame above
    leaf = len(names) - 1
    # PollGCWorker is where the sampler suspends a thread to sample it, not where it spent time
    while leaf > 0 and (names[leaf] in ("CPU_TIME", "UNMANAGED_CODE_TIME") or "PollGCWorker" in names[leaf]):
        leaf -= 1
    self_[names[leaf]] += w

def short(n):
    return n if len(n) < 150 else n[:147] + "..."
print(f"total weight {total:.1f}\n\nINCLUSIVE")
for n, w in inc.most_common(top):
    print(f"{100*w/total:6.1f}%  {short(n)}")
print("\nSELF")
for n, w in self_.most_common(top):
    print(f"{100*w/total:6.1f}%  {short(n)}")
