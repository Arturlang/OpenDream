using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using OpenDreamRuntime.Procs;
using System.Globalization;
using System.Runtime.CompilerServices;
using DMCompiler.Bytecode;
using JetBrains.Annotations;
using OpenDreamRuntime.Map;
using OpenDreamRuntime.Objects.Types;
using OpenDreamRuntime.Rendering;
using OpenDreamRuntime.Resources;
using OpenDreamShared.Dream;
using Robust.Server.GameObjects;
using Robust.Server.GameStates;
using Robust.Shared.Map;
using Robust.Shared.Serialization.Manager;
using Robust.Shared.Utility;

namespace OpenDreamRuntime.Objects;

[Virtual]
public class DreamObject {
    private static readonly string? RefTraceType = Environment.GetEnvironmentVariable("OPENDREAM_REF_TRACE_TYPE");
    private static readonly string? RefTraceRefId = Environment.GetEnvironmentVariable("OPENDREAM_REF_TRACE_REFID");
    private static readonly bool RefTraceStacks = Environment.GetEnvironmentVariable("OPENDREAM_REF_TRACE_STACKS") != "0";
    private static readonly bool RefTraceQdelOnly = Environment.GetEnvironmentVariable("OPENDREAM_REF_TRACE_QDEL_ONLY") == "1";
    private static readonly int? RefTraceMaxRefCount = int.TryParse(Environment.GetEnvironmentVariable("OPENDREAM_REF_TRACE_MAX"), out var maxRefCount)
        ? maxRefCount
        : null;

    public DreamObjectDefinition ObjectDefinition;

    [Access(typeof(DreamObject))]
    public bool Deleting, Deleted;

    public readonly uint RefId;

    [Access(typeof(DreamObject))]
    public int RefCount = 1; // Starts at 1 because the code creating us is considered to hold a ref to us now

    private bool _runningDel;

    public virtual bool ShouldCallNew => true;

    /// <summary>
    ///     Whether this object gets deleted once nothing references it anymore.
    ///     Objects that opt out are still reference counted, they just never die of their own accord;
    ///     an explicit del() still deletes them.
    /// </summary>
    public virtual bool ShouldGarbageCollect => true;

    // Shortcuts to IoC dependencies & entity systems
    protected DreamManager DreamManager => ObjectDefinition.DreamManager;
    protected DreamRefManager DreamRefManager => ObjectDefinition.DreamRefManager;
    protected DreamObjectTree ObjectTree => ObjectDefinition.ObjectTree;
    protected AtomManager AtomManager => ObjectDefinition.AtomManager;
    protected IDreamMapManager DreamMapManager => ObjectDefinition.DreamMapManager;
    protected SharedMapSystem MapManager => ObjectDefinition.MapManager;
    protected DreamResourceManager DreamResourceManager => ObjectDefinition.DreamResourceManager;
    protected WalkManager WalkManager => ObjectDefinition.WalkManager;
    protected IEntityManager EntityManager => ObjectDefinition.EntityManager;
    protected ISerializationManager SerializationManager => ObjectDefinition.SerializationManager;
    protected ServerAppearanceSystem? AppearanceSystem => ObjectDefinition.AppearanceSystem;
    protected TransformSystem? TransformSystem => ObjectDefinition.TransformSystem;
    protected PvsOverrideSystem? PvsOverrideSystem => ObjectDefinition.PvsOverrideSystem;
    protected MetaDataSystem? MetaDataSystem => ObjectDefinition.MetaDataSystem;
    protected ServerVerbSystem? VerbSystem => ObjectDefinition.VerbSystem;
    protected ServerDreamParticlesSystem? ParticlesSystem => ObjectDefinition.ParticlesSystem;

    /// <summary>
    /// The variables this instance has actually set, as slot indices into its type's
    /// shared name table alongside the values. Defaults live on the definition and reads
    /// fall through to them.
    ///
    /// This used to be a Dictionary&lt;string, DreamValue&gt; per instance, which cost about
    /// 874 bytes to hold roughly fifteen values worth 240 - 1.6 GB across 1.9 million
    /// objects on a full station, a fifth of the heap. The slots are kept sorted so a
    /// lookup is a binary search: an instance holds only a handful of the variables its
    /// type declares, so most reads miss and fall through, and a miss has to be cheap.
    /// </summary>
    private int[]? _varSlots;
    private DreamValue[]? _varValues;
    private int _varCount;

#if TOOLS
    protected ProfilerMemory? TracyMemoryId;
#endif

    //handle to the list of vars on this object so that it's only created once and refs to object.vars are consistent
    private DreamListVars? _varsList;

    private string? Tag {
        get;
        set {
            // Even if we're setting it to the same string we still need to remove it
            if (!string.IsNullOrEmpty(field)) {
                var list = DreamRefManager.Tags[field];

                if (list.Count > 1) {
                    list.Remove(this);
                } else {
                    DreamRefManager.Tags.Remove(field);
                }
            }

            field = value;

            // Now we add it (if it's a string)
            if (!string.IsNullOrEmpty(field)) {
                if (DreamRefManager.Tags.TryGetValue(field, out var list)) {
                    list.Add(this);
                } else {
                    var newList = new List<DreamObject> {
                        this
                    };

                    DreamRefManager.Tags.Add(field, newList);
                }
            }
        }
    }

    public DreamObject(DreamObjectDefinition objectDefinition) {
        ObjectDefinition = objectDefinition;
        RefId = DreamRefManager.GetRef(this);
        TraceRefChange("new", 0, RefCount, stackSkip: 1);

#if TOOLS
         //if it's not null, subclasses have done their own allocation
        TracyMemoryId ??= Profiler.BeginMemoryZone((ulong)(Unsafe.SizeOf<DreamObject>() + ObjectDefinition.Variables.Count * Unsafe.SizeOf<DreamValue>() ), "/datum");
#endif
    }

    public virtual void Initialize(DreamProcArguments args) {
        // For subtypes to implement
    }

    protected virtual void HandleDeletion() {
        // Remove the locate()-able reference to this object
        // Freeing up the slot for later reuse, as well as the .NET hard ref
        DreamRefManager.DeleteRef(RefId);

        for (var i = 0; i < _varCount; i++)
            _varValues![i].DecRef();

        //we release all relevant information, making this a very tiny object
        Tag = null;
        Deleted = true;
        _varSlots = null;
        _varValues = null;
        _varCount = 0;
        _varsList?.DecRef();
        _varsList?.Delete();
        _varsList = null;

        ObjectDefinition = null!;

#if TOOLS
        TracyMemoryId?.ReleaseMemory();
#endif
    }

    public void IncRef() {
        if (Deleted || Deleting)
            return;

        int oldRefCount = RefCount;
        RefCount++;
        TraceRefChange("inc", oldRefCount, RefCount);
    }

    public void DecRef() {
        if (Deleted)
            return;

        int oldRefCount = RefCount;
        RefCount--;
        TraceRefChange("dec", oldRefCount, RefCount);
        if (RefCount != 0)
            return;

        if (Deleting) {
            if (_runningDel)
                return;

            HandleDeletion();
            return;
        }

        if (IsManagedByQdel()) {
            Deleting = true;
            HandleDeletion();
        } else if (ShouldGarbageCollect) {
            // Areas opt out of collection entirely (upstream #2679).
            Delete();
        }
    }

    private bool IsManagedByQdel() {
        var slot = ObjectDefinition.GetGcDestroyedSlot(out var defaultTruthy);
        if (slot < 0)
            return false;

        if (_varCount > 0) {
            var index = IndexOfSlot(slot);
            if (index >= 0)
                return _varValues![index].IsTruthy();
        }

        return defaultTruthy;
    }

    private void TraceRefChange(string op, int oldRefCount, int newRefCount, int stackSkip = 2) {
        if (RefTraceType is not { Length: > 0 })
            return;

        string type = ObjectDefinition?.Type ?? "<deleted>";
        if (!type.Contains(RefTraceType, StringComparison.Ordinal))
            return;

        if (RefTraceRefId is { Length: > 0 } refId && !RefId.ToString("x").Equals(refId, StringComparison.OrdinalIgnoreCase))
            return;

        if (RefTraceQdelOnly && !Deleting && !TraceObjectIsQdelManaged())
            return;

        if (RefTraceMaxRefCount is { } max && oldRefCount > max && newRefCount > max)
            return;

        Console.Error.WriteLine($"[OD REF TRACE] {op} {type} [{RefId:x}] {oldRefCount}->{newRefCount} deleting={Deleting} deleted={Deleted}");
        if (RefTraceStacks) {
            Console.Error.WriteLine(new StackTrace(stackSkip, fNeedFileInfo: true));
        }
    }

    private bool TraceObjectIsQdelManaged() {
        if (Deleted || ObjectDefinition is null || !ObjectDefinition.HasVariable("gc_destroyed"))
            return false;

        using var gcDestroyed = GetVariable("gc_destroyed");
        return gcDestroyed.IsTruthy();
    }

    /// <summary>
    ///     Del() the object, cleaning up its variables and refs to allow the .NET GC to collect it.
    /// </summary>
    public void Delete() {
        Delete(force: false);
    }

    public void HardDelete() {
        Delete(force: true);
    }

    private void Delete(bool force) {
        if (Deleting || Deleted)
            return;

        Deleting = true;
        if (TryGetProc("Del", out var delProc)) {
            // Don't bother running Del() if there's no code in it
            var datumBaseProc = delProc is DMProc {Bytecode.Length: 0};
            if (!datumBaseProc) {
                _runningDel = true;
                try {
                    DreamThread.Run(delProc, this, null).Dispose();
                } finally {
                    _runningDel = false;
                }
            }
        }

        if (Deleted)
            return;

        if (!force && !ShouldDelete()) {
            Deleting = false;
            return;
        }

        HandleDeletion();
    }

    protected virtual bool ShouldDelete() {
        return true;
    }

    public bool IsSubtypeOf(TreeEntry ancestor) {
        if(Deleted) //null deref protection, deleted objects don't have ObjectDefinition anymore
            return false;
        return ObjectDefinition.IsSubtypeOf(ancestor);
    }

    #region Variables

    public virtual bool IsSaved(string name) {
        return ObjectDefinition.Variables.ContainsKey(name)
               && !ObjectDefinition.GlobalVariables.ContainsKey(name)
               && !(ObjectDefinition.ConstVariables is not null && ObjectDefinition.ConstVariables.Contains(name))
               && !(ObjectDefinition.TmpVariables is not null && ObjectDefinition.TmpVariables.Contains(name));
    }

    /// <summary>
    /// Index of a slot in <see cref="_varSlots"/>, or the bitwise complement of where it
    /// would be inserted, matching Array.BinarySearch's convention.
    /// </summary>
    private int IndexOfSlot(int slot) {
        var slots = _varSlots;
        var low = 0;
        var high = _varCount - 1;

        while (low <= high) {
            var mid = (low + high) >> 1;
            var here = slots![mid];

            if (here == slot)
                return mid;

            if (here < slot)
                low = mid + 1;
            else
                high = mid - 1;
        }

        return ~low;
    }

    private bool TryGetInstanceVariable(string name, out DreamValue value) {
        if (_varCount > 0 && ObjectDefinition.TryGetVarSlot(name, out var slot)) {
            var index = IndexOfSlot(slot);
            if (index >= 0) {
                value = _varValues![index];
                return true;
            }
        }

        value = default;
        return false;
    }

    /// <summary>
    /// Drops every variable this instance has set, so it falls back to its type's defaults
    /// again. Used when a turf changes type in place.
    /// </summary>
    protected void ClearInstanceVariables() {
        for (var i = 0; i < _varCount; i++)
            _varValues![i].DecRef();

        // The arrays are kept: a turf that changed type is given variables again at once.
        _varCount = 0;
    }

    public bool HasVariable(string name) {
        DebugTools.Assert(!Deleted, "Cannot call HasVariable() on a deleted object");

        return ObjectDefinition.HasVariable(name);
    }

    [MustDisposeResource]
    public DreamValue GetVariable(string name) {
        DebugTools.Assert(!Deleted, "Cannot call GetVariable() on a deleted object");

        if (TryGetVariable(name, out var variableValue)) {
            return variableValue;
        } else {
            throw new KeyNotFoundException($"Variable {name} doesn't exist");
        }
    }

    public IEnumerable<string> GetVariableNames() {
        DebugTools.Assert(!Deleted, "Cannot call GetVariableNames() on a deleted object");

        return ObjectDefinition.Variables.Keys;
    }

    internal IEnumerable<(string Name, DreamValue Value)> EnumerateStoredVariablesForDebug() {
        for (var i = 0; i < _varCount; i++)
            yield return (ObjectDefinition.GetVarSlotName(_varSlots![i]), _varValues![i]);
    }

    protected virtual bool TryGetVar(string varName, [MustDisposeResource] out DreamValue value) {
        switch (varName) {
            case "type":
                value = new(ObjectDefinition.TreeEntry);
                return true;
            case "parent_type":
                if (ObjectDefinition.Parent != null)
                    value = new(ObjectDefinition.Parent.TreeEntry);
                else
                    value = DreamValue.Null;

                return true;
            case "vars":
                _varsList ??= new DreamListVars(ObjectTree.List.ObjectDefinition, this);
                _varsList.IncRef();
                value = new(_varsList);
                return true;
            case "tag":
                value = (Tag != null) ? new(Tag) : DreamValue.Null;
                return true;
            default:
                var success =
                    (ObjectDefinition.GlobalVariables.TryGetValue(varName, out var globalIndex) && ObjectDefinition.DreamManager.Globals.TryGetValue(globalIndex, out value)) ||
                    TryGetInstanceVariable(varName, out value) ||
                    (ObjectDefinition.Variables.TryGetValue(varName, out value));

                value.IncRef();
                return success;
        }
    }

    protected virtual void SetVar(string varName, DreamValue value) {
        switch (varName) {
            case "type":
            case "parent_type":
            case "vars":
                throw new DMException($"Cannot set var \"{varName}\"");
            case "tag":
                value.TryGetValueAsString(out var newTag);

                Tag = newTag;
                break;
            default:
                if (ObjectDefinition.ConstVariables is not null && ObjectDefinition.ConstVariables.Contains(varName))
                    throw new DMException($"Cannot set const var \"{varName}\" on {ObjectDefinition.Type}");
                if (ObjectDefinition.GlobalVariables.TryGetValue(varName, out var globalIndex)) {
                    DreamManager.SetGlobal(globalIndex, value);
                    break;
                }
                if (!ObjectDefinition.Variables.ContainsKey(varName))
                    throw new DMException($"Cannot set var \"{varName}\" on {ObjectDefinition.Type}");

                SetVariableValue(varName, value);
                break;
        }
    }

    public bool TryGetVariable(string name, [MustDisposeResource] out DreamValue variableValue) {
        DebugTools.Assert(!Deleted, "Cannot call TryGetVariable() on a deleted object");

        return TryGetVar(name, out variableValue);
    }

    /// <summary>
    /// Handles setting a variable, and special behavior by calling OnVariableSet()
    /// </summary>
    public void SetVariable(string name, DreamValue value) {
        DebugTools.Assert(!Deleted, "Cannot call SetVariable() on a deleted object");

        SetVar(name, value);
    }

    /// <summary>
    /// Directly sets a variable's value, bypassing any special behavior
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public void SetVariableValue(string name, DreamValue value) {
        DebugTools.Assert(!Deleted, "Cannot call SetVariableValue() on a deleted object");

        value.IncRef();

        var slot = ObjectDefinition.GetOrCreateVarSlot(name);
        var index = IndexOfSlot(slot);
        if (index >= 0) {
            _varValues![index].DecRef();
            _varValues[index] = value;
            return;
        }

        var insertAt = ~index;
        if (_varSlots is null) {
            _varSlots = new int[4];
            _varValues = new DreamValue[4];
        } else if (_varCount == _varSlots.Length) {
            // Grown in small steps on purpose: most objects stop at a handful, and doubling
            // would put back the slack this layout exists to remove.
            var grown = _varCount + 4;
            Array.Resize(ref _varSlots, grown);
            Array.Resize(ref _varValues, grown);
        }

        if (insertAt < _varCount) {
            Array.Copy(_varSlots, insertAt, _varSlots, insertAt + 1, _varCount - insertAt);
            Array.Copy(_varValues!, insertAt, _varValues!, insertAt + 1, _varCount - insertAt);
        }

        _varSlots[insertAt] = slot;
        _varValues![insertAt] = value;
        _varCount++;
    }

    #endregion Variables

    #region Proc Helpers

    public DreamProc GetProc(string procName) {
        DebugTools.Assert(!Deleted, "Cannot call GetProc() on a deleted object");

        return ObjectDefinition.GetProc(procName);
    }

    public bool TryGetProc(string procName, [NotNullWhen(true)] out DreamProc? proc) {
        DebugTools.Assert(!Deleted, "Cannot call TryGetProc() on a deleted object");

        return ObjectDefinition.TryGetProc(procName, out proc);
    }

    public void InitSpawn([HandlesResourceDisposal] DreamProcArguments creationArguments) {
        if (ObjectDefinition.NoConstructors) {
            // Skip thread spinup.
            Initialize(creationArguments);
            creationArguments.Dispose();
            return;
        }

        var thread = new DreamThread("new " + ObjectDefinition.Type);
        var procState = InitProc(thread, null, creationArguments);

        thread.PushProcState(procState);
        thread.Resume().Dispose();
    }

    public ProcState InitProc(DreamThread thread, DreamObject? usr, [HandlesResourceDisposal] DreamProcArguments arguments) {
        DebugTools.Assert(!Deleted, "Cannot call InitProc() on a deleted object");

        if (!InitDreamObjectState.Pool.TryPop(out var state)) {
            state = new InitDreamObjectState(ObjectDefinition.DreamManager, ObjectDefinition.ObjectTree);
        }

        state.Initialize(thread, this, usr, arguments);
        return state;
    }

    [MustDisposeResource]
    public DreamValue SpawnProc(string procName, DreamObject? usr = null, params DreamValue[] arguments) {
        DebugTools.Assert(!Deleted, "Cannot call SpawnProc() on a deleted object");

        var proc = GetProc(procName);
        return DreamThread.Run(proc, this, usr, arguments);
    }

    #endregion Proc Helpers

    #region Name Helpers

    // This could probably be placed elsewhere. Not sure where tho
    /// <returns>true if \proper noun formatting should be used, false if \improper</returns>
    public static bool StringIsProper(string str) {
        if (str.Length == 0)
            return true;
        if (StringFormatEncoder.Decode(str[0], out var properMaybe)) {
            switch (properMaybe) {
                case StringFormatEncoder.FormatSuffix.Proper:
                    return true;
                case StringFormatEncoder.FormatSuffix.Improper:
                    return false;
            }
        }

        if (char.IsWhiteSpace(
                str[0])) // NOTE: This might result in slightly different behaviour (since C# may be more unicode-friendly about what "whitespace" means)
            return true;
        return char.IsUpper(str[0]);
    }

    public static bool StringStartsWithVowel(string str) {
        if (str.Length == 0)
            return false;
        char start = char.ToLower(str[0], CultureInfo.InvariantCulture);
        switch (start) {
            case 'a':
            case 'e':
            case 'i':
            case 'o':
            case 'u':
                return true;
            default:
                return false;
        }
    }

    /// <summary>
    /// Get the display name of this object, WITH ALL FORMATTING EVALUATED OR REMOVED!
    /// </summary>
    public virtual string GetDisplayName(StringFormatEncoder.FormatSuffix? suffix = null) {
        // /client is a little special and will return its key var
        // TODO: Maybe this should be an override to GetDisplayName()?
        if (this is DreamObjectClient client)
            return client.Connection.Key;

        var name = GetRawName();
        bool isProper = StringIsProper(name);
        name = StringFormatDecoder.RemoveFormatting(name); // TODO: Care about other formatting macros for obj names beyond \proper & \improper
        if(!isProper) {
            return name;
        }

        switch(suffix) {
            case StringFormatEncoder.FormatSuffix.UpperDefiniteArticle:
                return isProper ? name : $"The {name}";
            case StringFormatEncoder.FormatSuffix.LowerDefiniteArticle:
                return isProper ? name : $"the {name}";
            default:
                return name;
        }
    }

    /// <summary>
    /// Similar to <see cref="GetDisplayName"/> except it just returns the name as plaintext, with formatting removed. No article or anything.
    /// </summary>
    public string GetNameUnformatted() {
        return StringFormatDecoder.RemoveFormatting(GetRawName());
    }

    /// <summary>
    /// Returns the name of this object with no formatting evaluated
    /// </summary>
    public string GetRawName() {
        string name = ObjectDefinition.Type;

        if (this is DreamObjectAtom) {
            if (AtomManager.TryGetAppearance(this, out var appearance))
                name = appearance.Name;
        } else if (TryGetVariable("name", out DreamValue nameVar)) {
            if (nameVar.TryGetValueAsString(out var nameVarStr))
                name = nameVarStr;

            nameVar.Dispose();
        }

        return name;
    }

    #endregion Name Helpers

    #region Operators

    // +
    [MustDisposeResource]
    public virtual DreamValue OperatorAdd(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator+", new DreamProcArguments(b), out var result))
            return result;

        throw new InvalidOperationException($"Addition cannot be done between {this} and {b}");
    }

    // -
    [MustDisposeResource]
    public virtual DreamValue OperatorSubtract(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator-", new DreamProcArguments(b), out var result))
            return result;

        throw new InvalidOperationException($"Subtraction cannot be done between {this} and {b}");
    }

    // *
    [MustDisposeResource]
    public virtual DreamValue OperatorMultiply(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator*", new DreamProcArguments(b), out var result))
            return result;

        throw new InvalidOperationException($"Multiplication cannot be done between {this} and {b}");
    }

    // *=
    [MustDisposeResource]
    public virtual DreamValue OperatorMultiplyRef(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator*=", new(b), out var result))
            return result;
        if (TryExecuteOperatorOverload(state, "operator*", new(b), out result))
            return result;

        throw new InvalidOperationException($"Multiplication cannot be done between {this} and {b}");
    }

    // /
    [MustDisposeResource]
    public virtual DreamValue OperatorDivide(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator/", new DreamProcArguments(b), out var result))
            return result;

        throw new InvalidOperationException($"Division cannot be done between {this} and {b}");
    }

    // /=
    [MustDisposeResource]
    public virtual DreamValue OperatorDivideRef(DreamValue b, DMProcState state) {
        var args = new DreamProcArguments(b);
        if (TryExecuteOperatorOverload(state, "operator/=", args, out var result))
            return result;

        if (TryExecuteOperatorOverload(state, "operator/", args, out result))
            return result;

        throw new InvalidOperationException($"Division cannot be done between {this} and {b}");
    }

    // |
    [MustDisposeResource]
    public virtual DreamValue OperatorOr(DreamValue b, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator|", new DreamProcArguments(b), out var result))
            return result;

        throw new InvalidOperationException($"Cannot or {this} and {b}");
    }

    // +=
    [MustDisposeResource]
    public virtual DreamValue OperatorAppend(DreamValue b) {
        throw new InvalidOperationException($"Cannot append {b} to {this}");
    }

    // -=
    [MustDisposeResource]
    public virtual DreamValue OperatorRemove(DreamValue b) {
        throw new InvalidOperationException($"Cannot remove {b} from {this}");
    }

    // |=
    [MustDisposeResource]
    public virtual DreamValue OperatorCombine(DreamValue b) {
        throw new InvalidOperationException($"Cannot combine {this} and {b}");
    }

    // &=
    [MustDisposeResource]
    public virtual DreamValue OperatorMask(DreamValue b) {
        throw new InvalidOperationException($"Cannot mask {this} and {b}");
    }

    // ~=
    [MustDisposeResource]
    public virtual DreamValue OperatorEquivalent(DreamValue b) {
        if (!b.TryGetValueAsDreamObject(out var bObject))
            return DreamValue.False;

        return Equals(bObject) ? DreamValue.True : DreamValue.False;
    }

    // << statement
    public virtual void OperatorOutput(DreamValue b) {
        throw new InvalidOperationException($"Cannot output {b} to {this}");
    }

    // []
    [MustDisposeResource]
    public virtual DreamValue OperatorIndex(DreamValue index, DMProcState state) {
        if (TryExecuteOperatorOverload(state, "operator[]", new DreamProcArguments(index), out var result))
            return result;

        throw new InvalidOperationException($"Cannot index {this} with {index}");
    }

    // []=
    public virtual void OperatorIndexAssign(DreamValue index, DMProcState state, DreamValue value) {
        if (TryExecuteOperatorOverload(state, "operator[]=", new DreamProcArguments(index, value), out var result)) {
            result.Dispose();
            return;
        }

        throw new InvalidOperationException($"Cannot assign {value} to index {index} of {this}");
    }

    public bool TryOperatorStringify(DMProcState state, [MustDisposeResource] out DreamValue procResult) {
        return TryExecuteOperatorOverload(state, "operator\"\"", new DreamProcArguments(), out procResult);
    }

    #endregion Operators

    private bool TryExecuteOperatorOverload(
        DMProcState parentState,
        string operatorName,
        [HandlesResourceDisposal] DreamProcArguments arguments,
        [MustDisposeResource] out DreamValue procResult) {
        if (!TryGetProc(operatorName, out var proc)) {
            procResult = default;
            return false;
        }

        var thread = parentState.Thread;
        var operatorProcState = proc.CreateState(thread, this, parentState.Usr, arguments);
        operatorProcState.WaitFor = false;
        thread.PushProcState(operatorProcState);
        procResult = thread.ReentrantResume(parentState, out var resultStatus);

        switch (resultStatus) {
            case ProcStatus.Cancelled:
                // Throw DMError so parent .Resume() call also cancels cleanly.
                throw new DMError("Re-entrant proc cancelled");
            case ProcStatus.Returned:
                // Normal behavior, proc finished executing.
                return true;
            default:
                // This means Deferred, most likely. Which shouldn't be possible,
                // as the proc state is WaitFor = false.
                throw new Exception($"Unexpected proc result from re-entrant operator: {resultStatus}");
        }
    }

    public override string ToString() {
        if (Deleted) {
            return "<deleted>";
        }

        string name = GetNameUnformatted();
        if (!string.IsNullOrEmpty(name)) {
            return $"{ObjectDefinition.Type}{{name=\"{name}\"}}";
        }

        return ObjectDefinition.Type;
    }

    public override int GetHashCode() {
        return (int)RefId;
    }
}
