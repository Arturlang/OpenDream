// Ranks allocations in a dotnet-trace capture (gc-verbose profile) by type and by allocating
// stack, from GC AllocationTick events (one per ~100 KB allocated, so counts are samples).
//   alloctop <trace.nettrace> [topN] [frames]
using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Etlx;
using Microsoft.Diagnostics.Tracing.Parsers.Clr;

var path = args[0];
var top = args.Length > 1 ? int.Parse(args[1]) : 25;
var depth = args.Length > 2 ? int.Parse(args[2]) : 6;

var etlx = TraceLog.CreateFromEventPipeDataFile(path);
using var log = TraceLog.OpenOrConvert(etlx);
var byType = new Dictionary<string, long>();
var byStack = new Dictionary<string, long>();
long total = 0;

foreach (var ev in log.Events) {
    if (ev is not GCAllocationTickTraceData tick)
        continue;

    long bytes = tick.AllocationAmount64;
    total += bytes;
    var type = tick.TypeName ?? "?";
    byType[type] = byType.GetValueOrDefault(type) + bytes;

    var frames = new List<string>();
    for (var cs = ev.CallStack(); cs != null && frames.Count < depth; cs = cs.Caller) {
        var m = cs.CodeAddress.FullMethodName;
        if (string.IsNullOrEmpty(m) || m.StartsWith("System.") && frames.Count == 0)
            continue;
        frames.Add(m.Length > 90 ? m[..90] : m);
    }

    var key = type + "  <=  " + string.Join("  <  ", frames);
    byStack[key] = byStack.GetValueOrDefault(key) + bytes;
}

Console.WriteLine($"sampled allocation: {total / 1048576.0:N1} MiB\n\n== by type");
foreach (var (k, v) in byType.OrderByDescending(kv => kv.Value).Take(top))
    Console.WriteLine($"{100.0 * v / total,6:N1}%  {k}");
Console.WriteLine("\n== by type and stack");
foreach (var (k, v) in byStack.OrderByDescending(kv => kv.Value).Take(top))
    Console.WriteLine($"{100.0 * v / total,6:N1}%  {k}");
