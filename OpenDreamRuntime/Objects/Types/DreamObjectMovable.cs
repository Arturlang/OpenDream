using OpenDreamRuntime.Procs;
using OpenDreamRuntime.Rendering;
using OpenDreamShared.Dream;
using Robust.Shared.Map;

namespace OpenDreamRuntime.Objects.Types;

[Virtual]
public class DreamObjectMovable : DreamObjectAtom {
    public EntityUid Entity;
    public readonly DMISpriteComponent SpriteComponent;
    public DreamObjectAtom? Loc;

    // TODO: Cache this shit. GetWorldPosition is slow.
    public Vector2i Position => Loc is DreamObjectTurf turf
        ? (turf.X, turf.Y)
        : (Vector2i?)TransformSystem?.GetWorldPosition(_transformComponent) ?? (0, 0);
    public int X => Position.X;
    public int Y => Position.Y;
    public int Z => Loc is DreamObjectTurf turf ? turf.Z : (int)_transformComponent.MapID;

    private readonly TransformComponent _transformComponent;
    private readonly MovableContentsList _contents;
    private string? _screenLoc;
    private DreamObjectParticles? _particles;
    private double? _boundX;
    private double? _boundY;
    private double? _boundWidth;
    private double? _boundHeight;
    private bool _hasLocRef;

    public bool HasLocRef => _hasLocRef;

    private string? ScreenLoc {
        get => _screenLoc;
        set => SetScreenLoc(value);
    }

    public DreamObjectParticles? Particles {
        get;
        set {
            if(field == value)
                return;

            if(field is not null) {
                field.DecRef();
                field.RemoveOwner(this);
            }

            field = value;

            if(value is not null) {
                value.AddOwner(this);
                value.IncRef();
            }
        }
    }

    public DreamObjectMovable(DreamObjectDefinition objectDefinition) : base(objectDefinition) {
        Entity = AtomManager.CreateMovableEntity(this);
        SpriteComponent = EntityManager.GetComponent<DMISpriteComponent>(Entity);
        AtomManager.SetSpriteAppearance((Entity, SpriteComponent), AtomManager.GetAppearanceFromDefinition(ObjectDefinition));
        UpdateSpriteBoundOffset();

        _transformComponent = EntityManager.GetComponent<TransformComponent>(Entity);
        _contents = new MovableContentsList(ObjectTree.List.ObjectDefinition, this, _transformComponent);
    }

    public override void Initialize(DreamProcArguments args) {
        base.Initialize(args);

        ObjectDefinition.Variables["screen_loc"].TryGetValueAsString(out var screenLoc);
        ScreenLoc = screenLoc;

        if (EntityManager.TryGetComponent(Entity, out MetaDataComponent? metaData)) {
            MetaDataSystem?.SetEntityName(Entity, GetDisplayName(), metaData);
            MetaDataSystem?.SetEntityDescription(Entity, GetRTEntityDesc(), metaData);
        }

        args.GetArgument(0).TryGetValueAsDreamObject<DreamObjectAtom>(out var loc);
        SetLoc(loc); //loc is set before /New() is ever called
    }

    protected override void HandleDeletion() {
        SetLoc(null);
        WalkManager.StopWalks(this);
        Particles = null;
        AtomManager.DeleteMovableEntity(this);

        _contents.DecRef();
        _contents.Delete();
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
                Loc?.IncRef();
                value = new(Loc);
                return true;
            case "bound_width":
                value = new(_boundWidth ?? DreamManager.WorldInstance.IconSize);
                return true;
            case "bound_height":
                value = new(_boundHeight ?? DreamManager.WorldInstance.IconSize);
                return true;
            case "bound_x":
                value = new(_boundX ?? 0);
                return true;
            case "bound_y":
                value = new(_boundY ?? 0);
                return true;
            case "screen_loc":
                value = (ScreenLoc != null) ? new(ScreenLoc) : DreamValue.Null;
                return true;
            case "contents":
                _contents.IncRef();
                value = new(_contents);
                return true;
            case "locs":
                DreamList locs = ObjectTree.CreateList();
                switch (Loc) {
                    case DreamObjectTurf turf: {
                        var iconSize = DreamManager.WorldInstance.IconSize;
                        var tileWidth = Math.Max(1, (int)Math.Ceiling((_boundWidth ?? iconSize) / iconSize));
                        var tileHeight = Math.Max(1, (int)Math.Ceiling((_boundHeight ?? iconSize) / iconSize));

                        for (int x = turf.X; x < turf.X + tileWidth; x++) {
                            for (int y = turf.Y; y < turf.Y + tileHeight; y++) {
                                if (DreamMapManager.TryGetTurfAt((x, y), turf.Z, out var locTurf))
                                    locs.AddValue(new(locTurf));
                            }
                        }

                        break;
                    }
                    case not null:
                        locs.AddValue(new(Loc));
                        break;
                }

                value = new DreamValue(locs);
                return true;
            case "particles":
                Particles?.IncRef();
                value = new(Particles);
                return true;
            default:
                return base.TryGetVar(varName, out value);
        }
    }

    protected override void SetVar(string varName, DreamValue value) {
        switch (varName) {
            case "x":
            case "y":
            case "z": {
                int x = (varName == "x") ? value.MustGetValueAsInteger() : X;
                int y = (varName == "y") ? value.MustGetValueAsInteger() : Y;
                int z = (varName == "z") ? value.MustGetValueAsInteger() : Z;

                DreamMapManager.TryGetTurfAt((x, y), z, out var newLoc);
                SetLoc(newLoc);
                break;
            }
            case "loc": {
                if (!value.TryGetValueAsDreamObject<DreamObjectAtom>(out var newLoc) && !value.IsNull)
                    throw new DMException($"Invalid loc {value}");

                SetLoc(newLoc);
                break;
            }
            case "name":
            case "desc": {
                base.SetVar(varName, value); // Let DreamObjectAtom do its own name/desc handling

                if (varName == "name") {
                    MetaDataSystem?.SetEntityName(Entity, GetDisplayName());
                } else {
                    value.TryGetValueAsString(out string? valueStr);

                    MetaDataSystem?.SetEntityDescription(Entity, valueStr ?? string.Empty);
                }

                break;
            }
            case "screen_loc":
                value.TryGetValueAsString(out var screenLoc);

                ScreenLoc = screenLoc;
                break;
            case "bound_x":
                value.TryGetValueAsFloat(out var boundX);
                _boundX = boundX;
                UpdateSpriteBoundOffset();
                break;
            case "bound_y":
                value.TryGetValueAsFloat(out var boundY);
                _boundY = boundY;
                UpdateSpriteBoundOffset();
                break;
            case "bound_width":
                value.TryGetValueAsFloat(out var boundWidth);
                _boundWidth = boundWidth;
                break;
            case "bound_height":
                value.TryGetValueAsFloat(out var boundHeight);
                _boundHeight = boundHeight;
                break;
            case "particles":
                value.TryGetValueAsDreamObject<DreamObjectParticles>(out var particles);

                Particles = particles;
                break;
            default:
                base.SetVar(varName, value);
                break;
        }
    }

    public void SetLoc(DreamObjectAtom? loc) {
        var oldLoc = Loc;
        var oldMapCell = oldLoc is DreamObjectTurf oldTurf ? oldTurf.Cell : null;

        loc?.IncRef();
        Loc?.DecRef();
        Loc = loc;
        if (TransformSystem == null)
            return;

        oldMapCell?.Movables.Remove(this);

        if (loc is DreamObjectArea area) { // Puts the atom on the area's first turf
            loc = null; // Nullspace if we can't find a turf

            // We don't actually keep track of area turfs currently
            // So do the classic BYOND trick of looping through every turf and checking its area :)
            // TODO: Remove this monstrosity
            for (int z = 1; z <= DreamMapManager.Levels; z++) {
                for (int x = 1; x <= DreamMapManager.Size.X; x++) {
                    for (int y = 1; y <= DreamMapManager.Size.Y; y++) {
                        if (!DreamMapManager.TryGetCellAt((x, y), z, out var cell))
                            continue;

                        if (cell.Area == area) {
                            loc = cell.Turf;
                            break;
                        }
                    }
                }
            }
        }

        switch (loc) {
            case DreamObjectTurf turf:
                var zLevelEntity = DreamMapManager.GetZLevelEntity(turf.Z);
                if (zLevelEntity != EntityUid.Invalid) {
                    TransformSystem.SetParent(Entity, zLevelEntity);
                    TransformSystem.SetWorldPosition(Entity, new Vector2(turf.X, turf.Y));
                }

                turf.Cell.Movables.Add(this);
                if (!_hasLocRef) {
                    IncRef();
                    _hasLocRef = true;
                }
                break;
            case DreamObjectMovable movable:
                TransformSystem.SetParent(Entity, movable.Entity);
                TransformSystem.SetLocalPosition(Entity, Vector2.Zero);
                if (!_hasLocRef) {
                    IncRef();
                    _hasLocRef = true;
                }
                break;
            case null:
                TransformSystem.SetParent(Entity, MapManager.GetMapOrInvalid(MapId.Nullspace));
                if (_hasLocRef) {
                    ReleaseLocRef();
                    _hasLocRef = false;
                }
                break;
            default:
                throw new ArgumentException($"Invalid loc {loc}");
        }
    }

    private void ReleaseLocRef() {
        if (Deleting && !Deleted) {
            RefCount--;
        } else {
            DecRef();
        }
    }

    private void UpdateSpriteBoundOffset() {
        var boundX = (int)MathF.Round((float)(_boundX ?? 0));
        var boundY = (int)MathF.Round((float)(_boundY ?? 0));
        AtomManager.SetMovableBoundOffset(this, (boundX, boundY));
    }

    protected override DreamValue CreatePixLoc() {
        if (Loc is not DreamObjectTurf)
            return DreamValue.Null;

        var iconSize = DreamManager.WorldInstance.IconSize;
        var stepX = GetFloatVar("step_x");
        var stepY = GetFloatVar("step_y");
        var boundX = GetFloatVar("bound_x");
        var boundY = GetFloatVar("bound_y");
        var pixLoc = ObjectTree.CreateObject(ObjectTree.PixLoc);

        pixLoc.InitSpawn(new(
            new((X - 1) * iconSize + boundX + stepX + 1),
            new((Y - 1) * iconSize + boundY + stepY + 1),
            new(Z)));

        return new(pixLoc);
    }

    protected override void ApplyPixLoc(DreamValue value) {
        if (value.IsNull) {
            SetLoc(null);
            return;
        }

        if (!value.TryGetValueAsDreamObject(out var pixLoc) || pixLoc == null || !pixLoc.ObjectDefinition.IsSubtypeOf(ObjectTree.PixLoc))
            return;

        using var locValue = pixLoc.GetVariable("loc");
        if (locValue.TryGetValueAsDreamObject<DreamObjectAtom>(out var loc)) {
            SetLoc(loc);
        } else {
            SetLoc(null);
        }

        using var stepX = pixLoc.GetVariable("step_x");
        using var stepY = pixLoc.GetVariable("step_y");

        SetVariableValue("step_x", stepX);
        SetVariableValue("step_y", stepY);
    }

    private float GetFloatVar(string varName) {
        using var value = GetVariable(varName);

        return value.TryGetValueAsFloatCoerceNull(out var floatValue) ? floatValue : 0;
    }

    private void SetScreenLoc(string? screenLoc) {
        _screenLoc = screenLoc;
        AtomManager.SetMovableScreenLoc(this, !string.IsNullOrEmpty(screenLoc) ? new ScreenLocation(screenLoc) : new ScreenLocation(0, 0, 0, 0));
    }
}
