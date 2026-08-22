# DMHeapAudit

Attributes a server's managed heap to **DM types and DM variable names**, from a process
dump. Offline — it never touches a running server.

```
dotnet-dump collect -p <server pid> -o server.dmp
bin/DMHeapAudit/DMHeapAudit server.dmp report.txt
```

Expect roughly 90 seconds and a few GB of RAM for a full station dump (~42M objects).

## Why not just use SOS

`dumpheap -stat` tells you which *CLR* type is big, which for a DM server is always the
same unhelpful answer: dictionaries and `DreamValue` arrays. It cannot tell you which
`/datum` subtype owns them or which var on it, because that means walking from every
`DreamObject` to `ObjectDefinition.TreeEntry.Path` and through its instance variable
dictionary — an aggregation SOS has no way to express.

## What it reports

- **DM types by attributed bytes**, split into the object itself, its instance variable
  dictionary, and the storage those variables point at.
- **Variables by attributed bytes**, within the largest types and overall — how many
  instances set each var and what it costs on each.
- **Where the lists are**: how many are held by a datum var, nested in another list, or
  held by neither (a global, or something on the C# side), plus a size histogram.

## Reading the numbers

`var dict` is what the `Dictionary<string, DreamValue>` actually allocated, and that is
capacity based: entries and buckets round up to the next prime, so a dictionary holding
nine values pays for eleven. The per-variable rows charge 40 bytes per entry genuinely
set. The two deliberately disagree, and the gap is the slack — on a real station it has
been half the cost of the largest type.

Attribution is self + variable dictionary + the storage those variables own. It stops
there rather than walking the whole graph, so **treat every figure as a lower bound**. An
object reachable from more than one variable is charged once, to the first one that
reaches it; the total charged more than once is reported separately rather than hidden.
