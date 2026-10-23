using OpenDreamRuntime.Map;
using OpenDreamRuntime.Procs;
using OpenDreamShared.Dream;

namespace OpenDreamRuntime.Objects.Types;

public sealed class DreamObjectTurf : DreamObjectAtom {
    public readonly int X, Y, Z;
    public readonly TurfContentsList Contents;
    public ImmutableAppearance Appearance;
    /// <summary>What clients draw for this turf: <see cref="Appearance"/> plus its area's appearance as an overlay</summary>
    public ImmutableAppearance? DrawnAppearance;
    public IDreamMapManager.Cell Cell;
    public bool IsDense;

    public DreamObjectTurf(DreamObjectDefinition objectDefinition, int x, int y, int z) : base(objectDefinition) {
        X = x;
        Y = y;
        Z = z;

        Cell = default!; // NEEDS to be set by DreamMapManager after creation
        Appearance = default!; // This will be set by DreamMapManager
        Contents = new TurfContentsList(ObjectTree.List.ObjectDefinition, this);
    }

    public override void Initialize(DreamProcArguments args) {
        base.Initialize(args);

        ObjectDefinition.TryGetVariable("density", out var density);
        IsDense = density.IsTruthy();
    }

    public void SetTurfType(DreamObjectDefinition objectDefinition) {
        if (!objectDefinition.IsSubtypeOf(ObjectTree.Turf))
            throw new DMException($"Cannot set turf's type to {objectDefinition.Type}");

        ObjectDefinition = objectDefinition;

        ClearInstanceVariables();

        Initialize(new());
    }

    protected override bool ShouldDelete() {
        return false;
    }

    public void OnAreaChange(DreamObjectArea oldArea) {
        if (Cell == null!)
            return;

        if (Appearance == null! || oldArea.Appearance == null!)
            return;

        // Appearance never holds the area, so this only redraws the turf with its new area
        DreamMapManager.SetTurfAppearance(this, Appearance);
    }

    protected override void HandleDeletion() {
        Contents.DecRef();
        Contents.Delete();
        base.HandleDeletion();
    }

    protected override bool TryGetVar(string varName, out DreamValue value) {
        switch (varName) {
            case "x":
                value = new(X);
                return true;
            case "y":
                value = new(Y);
                return true;
            case "z":
                value = new(Z);
                return true;
            case "loc":
                Cell.Area.IncRef();
                value = new(Cell.Area);
                return true;
            case "density":
                value = IsDense ? DreamValue.True : DreamValue.False;
                return true;
            case "contents":
                Contents.IncRef();
                value = new(Contents);
                return true;
            default:
                return base.TryGetVar(varName, out value);
        }
    }

    protected override void SetVar(string varName, DreamValue value) {
        switch (varName) {
            case "density":
                IsDense = value.IsTruthy();
                break;
            case "contents":
                Contents.Cut();

                if (value.TryGetValueAsDreamList(out var valueList)) {
                    foreach (DreamValue contentValue in valueList.EnumerateValues()) {
                        Contents.AddValue(contentValue);
                    }
                }

                break;
            default:
                base.SetVar(varName, value);
                break;
        }
    }
}
