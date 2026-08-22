// Attributes an OpenDream server's managed heap to DM types and DM variable names.
//
// dumpheap -stat answers "which CLR type is big", which for a DM server is always the
// same unhelpful answer: dictionaries and DreamValue arrays. What you actually need to
// act is which /datum subtype owns them and which var on it. That means walking from
// each DreamObject to its ObjectDefinition.TreeEntry.Path for the DM type, and through
// its instance variable dictionary for the names - an aggregation SOS cannot express.
//
//   heapaudit <dump> [output.txt]

using System.Text;
using Microsoft.Diagnostics.Runtime;

var dumpPath = args.Length > 0 ? args[0] : null;
if (dumpPath is null || !File.Exists(dumpPath)) {
    Console.Error.WriteLine("usage: heapaudit <dump> [output.txt]");
    return 1;
}

var outPath = args.Length > 1 ? args[1] : Path.ChangeExtension(dumpPath, ".audit.txt");

Console.WriteLine($"Opening {dumpPath} ...");
using var target = DataTarget.LoadDump(dumpPath);
using var runtime = target.ClrVersions[0].CreateRuntime();
var heap = runtime.Heap;
if (!heap.CanWalkHeap) {
    Console.Error.WriteLine("Heap is not walkable - is this a full or heap dump?");
    return 1;
}

// Cost of one Dictionary<string, DreamValue> entry: hash, next, key reference and the
// 16 byte DreamValue, which is what makes a per-instance dictionary so expensive.
const int EntryOverhead = 40;
string[] BackingFields = ["_values", "_entries", "_buckets", "_items", "_array"];

// Per DM type.
var typeStats = new Dictionary<string, TypeStat>(StringComparer.Ordinal);
// Per (DM type, var name).
var varStats = new Dictionary<(string Type, string Var), VarStat>();

// An object is only charged to the first variable that reaches it, so a list shared by
// two vars is not counted twice. Shared bytes are reported separately rather than hidden.
var charged = new HashSet<ulong>();

// /list dominates the heap by instance count, so track where every list is actually held:
// directly on a datum var, nested inside another list, or neither - which means something
// on the C# side or a global is holding it, and no DM author can see it.
var allLists = new HashSet<ulong>();
var ownedLists = new HashSet<ulong>();
var nestedLists = new HashSet<ulong>();
var listOwners = new Dictionary<(string Type, string Var), ListOwnerStat>();
var sizeHistogram = new long[7];
var sizeHistogramBytes = new long[7];
long listSelfBytes = 0, listBackingBytes = 0;
long sharedBytes = 0, totalHeap = 0, dreamObjects = 0, scanned = 0;

var sw = System.Diagnostics.Stopwatch.StartNew();
foreach (var obj in heap.EnumerateObjects()) {
    if (!obj.IsValid || obj.Type is null)
        continue;

    scanned++;
    totalHeap += (long)obj.Size;
    if ((scanned & 0xFFFFF) == 0)
        Console.WriteLine($"  {scanned:N0} objects, {dreamObjects:N0} datums, {sw.Elapsed.TotalSeconds:0}s");

    if (!DerivesFromDreamObject(obj.Type))
        continue;

    var dmType = ReadDmType(obj) ?? "<unknown>";
    dreamObjects++;

    if (IsDreamList(obj.Type)) {
        allLists.Add(obj.Address);

        var (elements, backing) = MeasureList(obj);
        listSelfBytes += (long)obj.Size;
        listBackingBytes += backing;

        var bucket = elements switch {
            0 => 0, <= 2 => 1, <= 4 => 2, <= 8 => 3, <= 16 => 4, <= 64 => 5, _ => 6
        };
        sizeHistogram[bucket]++;
        sizeHistogramBytes[bucket] += (long)obj.Size + backing;

        // A list holding lists is the other place they hide.
        foreach (var nested in EnumerateListValues(obj))
            nestedLists.Add(nested);
    }

    ref var stat = ref GetTypeStat(typeStats, dmType);
    stat.Count++;
    stat.SelfBytes += (long)obj.Size;

    // DreamObject.Variables is a lazily allocated Dictionary<string, DreamValue> holding
    // only the vars this instance has actually set; the defaults live on the definition.
    var vars = obj.ReadObjectField("Variables");
    if (!vars.IsValid || vars.IsNull)
        continue;

    stat.VarDictBytes += (long)vars.Size;

    var entries = vars.ReadObjectField("_entries");
    if (!entries.IsValid || entries.IsNull)
        continue;

    stat.VarDictBytes += (long)entries.Size;

    var buckets = vars.ReadObjectField("_buckets");
    if (buckets.IsValid && !buckets.IsNull)
        stat.VarDictBytes += (long)buckets.Size;

    var count = vars.ReadField<int>("_count");
    var array = entries.AsArray();

    for (var i = 0; i < count && i < array.Length; i++) {
        ClrValueType entry;
        try {
            entry = array.GetStructValue(i);
        } catch {
            break;
        }

        if (!entry.IsValid)
            continue;

        // ReadStringField refuses this: inside a struct array ClrMD types the field as a
        // plain class reference, so go through the object and read the string off that.
        string name;
        try {
            var key = entry.ReadObjectField("key");
            name = key.IsValid && !key.IsNull ? key.AsString(512) : null;
        } catch {
            continue;
        }

        if (name is null)
            continue;

        // The value is a DreamValue struct; anything heap-allocated hangs off _refValue.
        long valueBytes = 0;
        try {
            var value = entry.ReadValueTypeField("value");
            var referenced = value.ReadObjectField("_refValue");
            if (referenced.IsValid && !referenced.IsNull) {
                valueBytes = OwnedSize(referenced, charged, ref sharedBytes);

                if (referenced.Type is not null && IsDreamList(referenced.Type)) {
                    ownedLists.Add(referenced.Address);

                    ref var owner = ref System.Runtime.InteropServices.CollectionsMarshal
                        .GetValueRefOrAddDefault(listOwners, (dmType, name), out _);
                    owner.Count++;
                    owner.Bytes += (long)referenced.Size + MeasureList(referenced).Backing;
                }
            }
        } catch {
            // A torn or unreadable field in a dump is not worth aborting the whole run for.
        }

        ref var vstat = ref GetVarStat(varStats, dmType, name);
        vstat.Count++;
        vstat.Bytes += EntryOverhead + valueBytes;

        stat.VarValueBytes += valueBytes;
    }
}

sw.Stop();
Console.WriteLine($"Scanned {scanned:N0} objects ({totalHeap / 1048576.0:N0} MiB) in {sw.Elapsed.TotalSeconds:0}s");

Write(outPath, typeStats, varStats, totalHeap, dreamObjects, sharedBytes);
AppendListReport(outPath, allLists, ownedLists, nestedLists, listOwners,
                 sizeHistogram, sizeHistogramBytes, listSelfBytes, listBackingBytes);
Console.WriteLine($"Wrote {outPath}");
return 0;


static bool IsDreamList(ClrType type) {
    for (var t = type; t is not null; t = t.BaseType)
        if (t.Name == "OpenDreamRuntime.Objects.Types.DreamList")
            return true;

    return false;
}

// A DreamList keeps its entries in a List<DreamValue> and, when associative, a second
// dictionary. Both backing stores are charged here, not the DreamValues themselves.
static (int Elements, long Backing) MeasureList(ClrObject list) {
    long backing = 0;
    var elements = 0;

    try {
        var values = list.ReadObjectField("_values");
        if (values.IsValid && !values.IsNull) {
            backing += (long)values.Size;
            elements = values.ReadField<int>("_size");

            var items = values.ReadObjectField("_items");
            if (items.IsValid && !items.IsNull)
                backing += (long)items.Size;
        }

        var assoc = list.ReadObjectField("_associativeValues");
        if (assoc.IsValid && !assoc.IsNull) {
            backing += (long)assoc.Size;

            foreach (var field in new[] {"_entries", "_buckets"}) {
                var part = assoc.ReadObjectField(field);
                if (part.IsValid && !part.IsNull)
                    backing += (long)part.Size;
            }
        }
    } catch {
        // Unreadable in the dump; report what we could measure.
    }

    return (elements, backing);
}

static IEnumerable<ulong> EnumerateListValues(ClrObject list) {
    ClrArray items;
    int size;

    try {
        var values = list.ReadObjectField("_values");
        if (!values.IsValid || values.IsNull)
            yield break;

        size = values.ReadField<int>("_size");
        var array = values.ReadObjectField("_items");
        if (!array.IsValid || array.IsNull)
            yield break;

        items = array.AsArray();
    } catch {
        yield break;
    }

    for (var i = 0; i < size && i < items.Length; i++) {
        ulong address;
        try {
            var element = items.GetStructValue(i);
            var referenced = element.ReadObjectField("_refValue");
            if (!referenced.IsValid || referenced.IsNull || referenced.Type is null || !IsDreamList(referenced.Type))
                continue;

            address = referenced.Address;
        } catch {
            continue;
        }

        yield return address;
    }
}

static bool DerivesFromDreamObject(ClrType type) {
    for (var t = type; t is not null; t = t.BaseType)
        if (t.Name == "OpenDreamRuntime.Objects.DreamObject")
            return true;

    return false;
}

static string ReadDmType(ClrObject obj) {
    try {
        var def = obj.ReadObjectField("ObjectDefinition");
        if (!def.IsValid || def.IsNull)
            return null;

        var tree = def.ReadObjectField("TreeEntry");
        return tree.IsValid && !tree.IsNull ? tree.ReadStringField("Path") : null;
    } catch {
        return null;
    }
}

// Shallow size plus the backing storage an object obviously owns - a DreamList's value
// array, a dictionary's entries. Deliberately not a full retained-size walk: that would
// need a dominator tree over 42 million objects, and the backing arrays are where the
// bytes actually are.
long OwnedSize(ClrObject obj, HashSet<ulong> charged, ref long shared) {
    if (!charged.Add(obj.Address)) {
        shared += (long)obj.Size;
        return 0;
    }

    long size = (long)obj.Size;

    foreach (var fieldName in BackingFields) {
        try {
            var backing = obj.ReadObjectField(fieldName);
            if (backing.IsValid && !backing.IsNull && charged.Add(backing.Address))
                size += (long)backing.Size;
        } catch {
            // Field does not exist on this type; that is the common case.
        }
    }

    return size;
}


static ref TypeStat GetTypeStat(Dictionary<string, TypeStat> map, string key) {
    ref var slot = ref System.Runtime.InteropServices.CollectionsMarshal.GetValueRefOrAddDefault(map, key, out _);
    return ref slot;
}

static ref VarStat GetVarStat(Dictionary<(string, string), VarStat> map, string type, string name) {
    ref var slot = ref System.Runtime.InteropServices.CollectionsMarshal.GetValueRefOrAddDefault(map, (type, name), out _);
    return ref slot;
}

static void Write(string path, Dictionary<string, TypeStat> types, Dictionary<(string Type, string Var), VarStat> vars,
                  long totalHeap, long datums, long shared) {
    var sb = new StringBuilder();
    var attributed = types.Values.Sum(t => t.Total);

    sb.AppendLine("DM heap audit");
    sb.AppendLine($"  heap walked      {totalHeap / 1048576.0,10:N0} MiB");
    sb.AppendLine($"  attributed       {attributed / 1048576.0,10:N0} MiB to {datums:N0} datums across {types.Count:N0} DM types");
    sb.AppendLine($"  shared, uncharged{shared / 1048576.0,10:N0} MiB (objects reachable from more than one var; charged once)");
    sb.AppendLine();
    sb.AppendLine("Attribution is self + instance var dictionary + the storage those vars own.");
    sb.AppendLine("It does not follow the whole object graph, so it undercounts deep structures.");
    sb.AppendLine();
    sb.AppendLine("'var dict' is what the Dictionary actually allocated, which is capacity based:");
    sb.AppendLine("entries and buckets are sized to the next prime, so a dictionary holding nine");
    sb.AppendLine("values pays for eleven. The per variable rows below charge 40 bytes per entry");
    sb.AppendLine("that is really set, so they total less than 'var dict' - the difference is the");
    sb.AppendLine("slack, and it is pure overhead.");
    sb.AppendLine();

    sb.AppendLine("=== DM types by attributed bytes ===");
    sb.AppendLine($"{"MiB",10} {"count",12} {"self",10} {"var dict",10} {"var values",11}  type");
    foreach (var (name, stat) in types.OrderByDescending(kv => kv.Value.Total).Take(40))
        sb.AppendLine($"{stat.Total / 1048576.0,10:N1} {stat.Count,12:N0} {stat.SelfBytes / 1048576.0,10:N1} " +
                      $"{stat.VarDictBytes / 1048576.0,10:N1} {stat.VarValueBytes / 1048576.0,11:N1}  {name}");

    sb.AppendLine();
    sb.AppendLine("=== variables by attributed bytes, within the ten largest types ===");
    foreach (var (typeName, stat) in types.OrderByDescending(kv => kv.Value.Total).Take(10)) {
        sb.AppendLine();
        sb.AppendLine($"{typeName}  ({stat.Count:N0} instances, {stat.Total / 1048576.0:N1} MiB)");
        sb.AppendLine($"  {"MiB",10} {"set on",12} {"bytes each",12}  var");

        var forType = vars.Where(kv => kv.Key.Type == typeName)
                          .OrderByDescending(kv => kv.Value.Bytes)
                          .ToList();

        foreach (var (key, v) in forType.Take(15))
            sb.AppendLine($"  {v.Bytes / 1048576.0,10:N1} {v.Count,12:N0} {(v.Count == 0 ? 0 : v.Bytes / v.Count),12:N0}  {key.Var}");

        if (forType.Count > 15) {
            var rest = forType.Skip(15).Sum(kv => kv.Value.Bytes);
            sb.AppendLine($"  {rest / 1048576.0,10:N1} {"",12} {"",12}  ({forType.Count - 15} more vars)");
        }

        var rows = forType.Sum(kv => kv.Value.Bytes);
        var slack = stat.VarDictBytes - forType.Sum(kv => kv.Value.Count) * 40;
        sb.AppendLine($"  {"",10} {"",12} {"",12}  vars set: {forType.Count}, " +
                      $"rows total {rows / 1048576.0:N1} MiB, dictionary slack {slack / 1048576.0:N1} MiB");
    }

    sb.AppendLine();
    sb.AppendLine("=== single most expensive variables, any type ===");
    sb.AppendLine($"{"MiB",10} {"set on",12} {"bytes each",12}  type.var");
    foreach (var (key, v) in vars.OrderByDescending(kv => kv.Value.Bytes).Take(40))
        sb.AppendLine($"{v.Bytes / 1048576.0,10:N1} {v.Count,12:N0} {(v.Count == 0 ? 0 : v.Bytes / v.Count),12:N0}  {key.Type}.{key.Var}");

    File.WriteAllText(path, sb.ToString());
}

static void AppendListReport(string path, HashSet<ulong> all, HashSet<ulong> owned, HashSet<ulong> nested,
                             Dictionary<(string Type, string Var), ListOwnerStat> owners,
                             long[] histogram, long[] histogramBytes, long selfBytes, long backingBytes) {
    var sb = new StringBuilder();
    sb.AppendLine();
    sb.AppendLine("=== where the lists are ===");
    sb.AppendLine($"  {all.Count,12:N0} lists, {(selfBytes + backingBytes) / 1048576.0:N0} MiB " +
                  $"({selfBytes / 1048576.0:N0} MiB objects + {backingBytes / 1048576.0:N0} MiB backing)");

    var nestedOnly = nested.Count(a => !owned.Contains(a) && all.Contains(a));
    var unheld = all.Count(a => !owned.Contains(a) && !nested.Contains(a));

    sb.AppendLine($"  {owned.Count,12:N0} held directly by a datum variable");
    sb.AppendLine($"  {nestedOnly,12:N0} nested inside another list");
    sb.AppendLine($"  {unheld,12:N0} held by neither - a global, or something on the C# side");

    sb.AppendLine();
    sb.AppendLine("  elements        lists          MiB");
    string[] labels = ["empty", "1-2", "3-4", "5-8", "9-16", "17-64", "65+"];
    for (var i = 0; i < labels.Length; i++)
        sb.AppendLine($"  {labels[i],8} {histogram[i],12:N0} {histogramBytes[i] / 1048576.0,12:N1}");

    sb.AppendLine();
    sb.AppendLine("=== variables holding the most lists ===");
    sb.AppendLine($"{"MiB",10} {"lists",12} {"bytes each",12}  type.var");
    foreach (var (key, stat) in owners.OrderByDescending(kv => kv.Value.Bytes).Take(40))
        sb.AppendLine($"{stat.Bytes / 1048576.0,10:N1} {stat.Count,12:N0} " +
                      $"{(stat.Count == 0 ? 0 : stat.Bytes / stat.Count),12:N0}  {key.Type}.{key.Var}");

    File.AppendAllText(path, sb.ToString());
}

struct ListOwnerStat {
    public long Count, Bytes;
}

struct TypeStat {
    public long Count, SelfBytes, VarDictBytes, VarValueBytes;
    public readonly long Total => SelfBytes + VarDictBytes + VarValueBytes;
}

struct VarStat {
    public long Count, Bytes;
}
