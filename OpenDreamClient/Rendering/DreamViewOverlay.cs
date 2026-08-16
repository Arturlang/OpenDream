using System.Linq;
using OpenDreamClient.Interface;
using Robust.Client.Graphics;
using Robust.Client.Player;
using Robust.Shared.Map;
using OpenDreamShared.Dream;
using Robust.Shared.Console;
using Robust.Shared.Prototypes;
using OpenDreamShared.Rendering;
using OpenDreamClient.Rendering.Particles;
using OpenDreamClient.Interface.Controls.UI;
using Robust.Client.GameObjects;
using Robust.Shared.Map.Components;
using Robust.Shared.Profiling;
using Matrix3x2 = System.Numerics.Matrix3x2;
using Robust.Client.ResourceManagement;
using Robust.Client.UserInterface.RichText;
using Robust.Shared.Enums;

namespace OpenDreamClient.Rendering;

/// <summary>
/// Overlay for rendering world atoms
/// </summary>
internal sealed partial class DreamViewOverlay : Overlay {
    public static ShaderInstance ColorInstance = default!;

    public override OverlaySpace Space => OverlaySpace.WorldSpaceBelowWorld;

    public bool ScreenOverlayEnabled = true;
    public bool MouseMapRenderEnabled;

    public int IconSize => _interfaceManager.IconSize;
    public Texture? MouseMap => _mouseMapRenderTarget?.Texture;
    public readonly Dictionary<int, DreamPlane> Planes = new();
    public readonly ShaderInstance BlockColorInstance;
    public readonly Dictionary<Color, RendererMetaData> MouseMapLookup = new();
    public readonly Dictionary<string, IRenderTexture> RenderSourceLookup = new();
    public readonly HashSet<EntityUid> EntitiesInView = new();

    private const LookupFlags MapLookupFlags = LookupFlags.Approximate | LookupFlags.Uncontained;
    private static readonly ProtoId<ShaderPrototype> BlockColorShader = "blockcolor";
    private static readonly ProtoId<ShaderPrototype> ColorShader = "color";
    private static readonly ProtoId<ShaderPrototype> BlendOverlayShader = "blend_overlay";
    private static readonly ProtoId<ShaderPrototype> BlendAddShader = "blend_add";
    private static readonly ProtoId<ShaderPrototype> BlendSubtractShader = "blend_subtract";
    private static readonly ProtoId<ShaderPrototype> BlendMultiplyShader = "blend_multiply";
    private static readonly ProtoId<ShaderPrototype> BlendInsetOverlayShader = "blend_inset_overlay";

    [Dependency] private IDreamInterfaceManager _interfaceManager = default!;
    [Dependency] private IPlayerManager _playerManager = default!;
    [Dependency] private IEntityManager _entityManager = default!;
    [Dependency] private ParticlesManager _particlesManager = default!;
    [Dependency] private IEntitySystemManager _entitySystemManager = default!;
    [Dependency] private IClyde _clyde = default!;
    [Dependency] private IPrototypeManager _protoManager = default!;
    [Dependency] private ProfManager _prof = default!;
    [Dependency] private IResourceCache _resourceCache = default!;
    [Dependency] private MarkupTagManager _tagManager = default!;

    private readonly ISawmill _sawmill = Logger.GetSawmill("opendream.view");

    private readonly TransformSystem _transformSystem;
    private readonly MapSystem _mapSystem;
    private readonly EntityLookupSystem _lookupSystem;
    private readonly ClientAppearanceSystem _appearanceSystem;
    private readonly ClientScreenOverlaySystem _screenOverlaySystem;
    private readonly ClientImagesSystem _imagesSystem;
    private readonly DMISpriteSystem _spriteSystem;
    private readonly AtomGlideSystem _atomGlideSystem;
    private readonly EntityQuery<DMISpriteComponent> _spriteQuery;
    private readonly EntityQuery<TransformComponent> _xformQuery;
    private readonly EntityQuery<DreamMobSightComponent> _mobSightQuery;

    private readonly List<RendererMetaData> _spriteContainer = new();

    private readonly Dictionary<BlendMode, ShaderInstance> _blendModeInstances;

    private IRenderTexture? _mouseMapRenderTarget;
    private IRenderTexture? _baseRenderTarget;
    private readonly Dictionary<string, MapControlRenderState> _mapControlRenderStates = new();
    private readonly RenderTargetPool _renderTargetPool;
    private readonly Stack<RendererMetaData> _rendererMetaDataRental = new();
    private readonly Stack<RendererMetaData> _rendererMetaDataToReturn = new();
    private int _sortIndex;
    private readonly MapTextRenderer _mapTextRenderer;

    private static readonly Matrix3x2 FlipMatrix = Matrix3x2.Identity with {
        M22 = -1
    };

    //Used for supressing the "No Literals" warning on shader index lookups
    private static class OdShaderId {
        public const string
            BlockColor = "blockcolor",
            Color = "color",
            BlendOverlay = "blend_overlay",
            BlendAdd = "blend_add",
            BlendSubtract = "blend_subtract",
            BlendMultiply = "blend_multiply",
            BlendInsetOverlay = "blend_inset_overlay";
    }

    public DreamViewOverlay(RenderTargetPool renderTargetPool) {
        IoCManager.InjectDependencies(this);
        _renderTargetPool = renderTargetPool;
        _transformSystem = _entitySystemManager.GetEntitySystem<TransformSystem>();
        _mapSystem = _entitySystemManager.GetEntitySystem<MapSystem>();
        _lookupSystem = _entitySystemManager.GetEntitySystem<EntityLookupSystem>();
        _appearanceSystem = _entitySystemManager.GetEntitySystem<ClientAppearanceSystem>();
        _screenOverlaySystem = _entitySystemManager.GetEntitySystem<ClientScreenOverlaySystem>();
        _imagesSystem = _entitySystemManager.GetEntitySystem<ClientImagesSystem>();
        _spriteSystem = _entitySystemManager.GetEntitySystem<DMISpriteSystem>();
        _atomGlideSystem = _entitySystemManager.GetEntitySystem<AtomGlideSystem>();
        _spriteQuery = _entityManager.GetEntityQuery<DMISpriteComponent>();
        _xformQuery = _entityManager.GetEntityQuery<TransformComponent>();
        _mobSightQuery = _entityManager.GetEntityQuery<DreamMobSightComponent>();

        _sawmill.Debug("Loading shaders...");
        BlockColorInstance = _protoManager.Index<ShaderPrototype>(OdShaderId.BlockColor).InstanceUnique();
        ColorInstance = _protoManager.Index<ShaderPrototype>(OdShaderId.Color).InstanceUnique();
        _blendModeInstances = new(6) {
            {BlendMode.Default, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendOverlay).InstanceUnique()}, //BLEND_DEFAULT (Same as BLEND_OVERLAY when there's no parent)
            {BlendMode.Overlay, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendOverlay).InstanceUnique()}, //BLEND_OVERLAY
            {BlendMode.Add, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendAdd).InstanceUnique()}, //BLEND_ADD
            {BlendMode.Subtract, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendSubtract).InstanceUnique()}, //BLEND_SUBTRACT
            {BlendMode.Multiply, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendMultiply).InstanceUnique()}, //BLEND_MULTIPLY
            {BlendMode.InsertOverlay, _protoManager.Index<ShaderPrototype>(OdShaderId.BlendInsetOverlay).InstanceUnique()} //BLEND_INSET_OVERLAY //TODO
        };

        // Set the default parameters for each blend mode
        foreach (var shader in _blendModeInstances.Values) {
            shader.SetParameter("colorMatrix", ColorMatrix.Identity.GetMatrix4());
            shader.SetParameter("offsetVector", ColorMatrix.Identity.GetOffsetVector());
            shader.SetParameter("isPlaneMaster", false);
        }

        _mapTextRenderer = new(_resourceCache, _tagManager);
    }

    protected override void Draw(in OverlayDrawArgs args) {
        using var _ = _prof.Group("Dream View Overlay");

        EntityUid? eye = _playerManager.LocalSession?.AttachedEntity;
        if (eye == null)
            return;

        //Main drawing of sprites happens here
        try {
            var viewportSize = (Vector2i)(args.Viewport.Size / args.Viewport.RenderScale);

            DrawAll(args, eye.Value, viewportSize);
        } catch (Exception e) {
            _sawmill.Error($"Error occurred while rendering frame. Error details:\n{e.Message}\n{e.StackTrace}");
        }

        _appearanceSystem.CleanUpUnusedFilters();
        _appearanceSystem.ResetFilterUsageFlags();

        RenderSourceLookup.Clear();

        _renderTargetPool.HandleEndOfFrame();

        //RendererMetaData objects get reused instead of garbage collected
        while (_rendererMetaDataToReturn.Count > 0)
            _rendererMetaDataRental.Push(_rendererMetaDataToReturn.Pop());
    }

    private void DrawAll(OverlayDrawArgs args, EntityUid eye, Vector2i viewportSize) {
        if (!_xformQuery.TryGetComponent(eye, out var eyeTransform))
            return;

        _mobSightQuery.TryGetComponent(eye, out var mobSight);
        var seeVis = mobSight?.SeeInvisibility ?? 127;
        var sight = mobSight?.Sight ?? 0;

        var worldHandle = args.WorldHandle;
        var worldAABB = args.WorldAABB;
        var mapControlId = (args.ViewportControl as ScalingViewport)?.MapControlId;

        var eyeCoords = GetLogicalMapCoordinates(eye, eyeTransform);
        if (!_mapSystem.TryFindGridAt(eyeCoords, out var gridUid, out var grid)) {
            RefreshRenderTargets(args.WorldHandle, viewportSize);

            _spriteContainer.Clear();
            _sortIndex = 0;
            CollectScreenObjects(seeVis, worldAABB.BottomLeft, mapControlId);
            _spriteContainer.Sort();

            ClearPlanes();
            ProcessSprites(worldHandle, viewportSize, worldAABB);
            DrawPlanes(worldHandle, worldAABB);

            worldHandle.DrawTexture(
                MouseMapRenderEnabled ? _mouseMapRenderTarget!.Texture : _baseRenderTarget!.Texture,
                args.WorldAABB.BottomLeft);
            return;
        }

        using (_prof.Group("lookup")) {
            //TODO use a sprite tree.
            //the scaling is to attempt to prevent pop-in, by getting sprites that are *just* offscreen
            _lookupSystem.GetEntitiesIntersecting(args.MapId, worldAABB.Scale(1.2f), EntitiesInView, MapLookupFlags);
        }

        LogSpriteCensus(args.MapId, worldAABB, seeVis);

        var eyeTile = _mapSystem.GetTileRef(gridUid, grid, eyeCoords);
        var tiles = CalculateTileVisibility(gridUid, grid, eyeTile, seeVis);

        RefreshRenderTargets(args.WorldHandle, viewportSize);

        CollectVisibleSprites(tiles, gridUid, grid, eyeTile, seeVis, sight, worldAABB, mapControlId);
        ClearPlanes();
        ProcessSprites(worldHandle, viewportSize, worldAABB);

        //Final draw
        DrawPlanes(worldHandle, worldAABB);

        //At this point all the sprites have been rendered to the base target, now we just draw it to the viewport!
        worldHandle.DrawTexture(
            MouseMapRenderEnabled ? _mouseMapRenderTarget!.Texture : _baseRenderTarget!.Texture,
            args.WorldAABB.BottomLeft);
    }

    private int _censusFrames;

    /// <summary>
    /// Periodic one-line census of the sprite pipeline, to pinpoint which stage loses
    /// entities when objects exist server-side but nothing renders. Each count is a
    /// stage: entities with a sprite component at all (replication), entities the
    /// spatial lookup found (lookup trees), entities passing the visibility gate, and
    /// how many of those are still waiting on their appearance (nothing to draw).
    /// </summary>
    private void LogSpriteCensus(MapId mapId, Box2 worldAABB, int seeVis) {
        if (++_censusFrames % 300 != 1)
            return;

        var total = 0;
        var onMap = 0;
        var inBox = 0;
        var samples = 0;
        var offMapSamples = 0;
        var sampleText = "";
        var mapHistogram = new Dictionary<MapId, int>();

        var detached = 0;
        var offMapRoots = 0;
        var metaQuery = _entityManager.GetEntityQuery<MetaDataComponent>();
        var all = _entityManager.AllEntityQueryEnumerator<DMISpriteComponent, TransformComponent>();
        while (all.MoveNext(out var uid, out _, out var xform)) {
            total++;
            if ((metaQuery.GetComponent(uid).Flags & MetaDataFlags.Detached) != 0)
                detached++;
            mapHistogram[xform.MapID] = mapHistogram.GetValueOrDefault(xform.MapID) + 1;

            if (xform.MapID != mapId) {
                if (xform.ParentUid == EntityUid.Invalid)
                    offMapRoots++;

                if (offMapSamples < 3 && xform.ParentUid != EntityUid.Invalid && xform.LocalPosition != System.Numerics.Vector2.Zero) {
                    // The interesting ones: real local coordinates, wrong map - their chain
                    // is rooted somewhere it shouldn't be. Walk to the root.
                    offMapSamples++;
                    var root = uid;
                    var depth = 0;
                    while (depth < 20 && _xformQuery.GetComponent(root).ParentUid != EntityUid.Invalid) {
                        root = _xformQuery.GetComponent(root).ParentUid;
                        depth++;
                    }

                    var rootHasSprite = _spriteQuery.HasComponent(root);
                    sampleText += $" [CHAIN {_entityManager.GetNetEntity(uid)} local={xform.LocalPosition} depth={depth} root={_entityManager.GetNetEntity(root)} rootSprite={rootHasSprite}]";
                }

                continue;
            }

            onMap++;
            var worldPos = _transformSystem.GetWorldPosition(uid);
            if (!worldAABB.Contains(worldPos)) {
                // These are the mystery: on the right map, but not where the view is.
                if (offMapSamples < 6) {
                    offMapSamples++;
                    sampleText += $" [MAP2-ELSEWHERE {uid} pos={worldPos} parent={xform.ParentUid}]";
                }

                continue;
            }

            inBox++;
            if (samples < 3) {
                samples++;
                sampleText += $" [IN {uid} pos={worldPos} parent={xform.ParentUid}]";
            }
        }

        var histogramText = string.Join(",", mapHistogram.OrderBy(pair => pair.Key.GetHashCode()).Select(pair => $"{pair.Key}:{pair.Value}"));

        // The chains above rooted at net entity 1 - inspect what that root actually is here.
        var rootText = "";
        if (_entityManager.TryGetEntity(new NetEntity(1), out var rootUid)) {
            var rootXform = _xformQuery.GetComponent(rootUid.Value);
            var compNames = string.Join("+", _entityManager.GetComponents(rootUid.Value).Select(c => c.GetType().Name).Take(8));
            rootText = $" net1: uid={rootUid} map={rootXform.MapID} parent={rootXform.ParentUid} comps={compNames}";
        }

        var inView = EntitiesInView.Count;
        var visible = 0;
        var noAppearance = 0;

        foreach (var entity in EntitiesInView) {
            if (!_spriteQuery.TryGetComponent(entity, out var sprite))
                continue;

            if (!_spriteSystem.IsVisible(sprite, _xformQuery.GetComponent(entity), seeVis, worldAABB))
                continue;

            visible++;
            if (sprite.Icon.Appearance == null)
                noAppearance++;
        }

        _sawmill.Debug(
            $"sprite census: map={mapId} aabb={worldAABB} dmiSprites={total} onMap={onMap} inBox={inBox} inView={inView} visible={visible} noAppearance={noAppearance} detached={detached} offMapRoots={offMapRoots} maps=({histogramText}){rootText}{sampleText}");
    }

    public Texture? RenderScreenObjectsForMapControl(DrawingHandleWorld handle, Vector2i viewportSize, string mapControlId) {
        var renderState = GetMapControlRenderState(mapControlId);
        RefreshRenderTargets(handle, viewportSize, renderState.Planes, ref renderState.BaseRenderTarget);

        _spriteContainer.Clear();
        _sortIndex = 0;

        CollectScreenObjects(127, Vector2.Zero, mapControlId);
        CenterMapControlSprites(viewportSize);
        _spriteContainer.Sort();

        var worldAABB = Box2.FromDimensions(Vector2.Zero, viewportSize / (float)IconSize);
        ClearPlanes(renderState.Planes);
        ProcessSprites(handle, viewportSize, worldAABB, renderState.Planes);
        DrawPlanes(handle, worldAABB, renderState.Planes, renderState.BaseRenderTarget, null, drawMouseMap: false);

        return renderState.BaseRenderTarget?.Texture;
    }

    private MapControlRenderState GetMapControlRenderState(string mapControlId) {
        if (_mapControlRenderStates.TryGetValue(mapControlId, out var state))
            return state;

        state = new();
        _mapControlRenderStates.Add(mapControlId, state);
        return state;
    }

    private void CenterMapControlSprites(Vector2i viewportSize) {
        Box2? contentBounds = null;

        foreach (RendererMetaData sprite in _spriteContainer) {
            if (sprite.IsPlaneMaster)
                continue;

            if (!TryGetMapControlSpriteBounds(sprite, out var spriteBounds))
                continue;

            contentBounds = contentBounds?.Union(spriteBounds) ?? spriteBounds;
        }

        if (contentBounds == null)
            return;

        var targetSize = viewportSize / (float)IconSize;
        var targetCenter = targetSize / 2.0f;
        var contentCenter = contentBounds.Value.Center;
        var offset = targetCenter - contentCenter;

        const float mapControlContentScale = 2.0f;
        var mapControlScale = Matrix3x2.CreateScale(mapControlContentScale);

        foreach (RendererMetaData sprite in _spriteContainer) {
            if (TryGetMapControlSpriteBounds(sprite, out _)) {
                sprite.Position += offset;
                sprite.SortPosition += offset;
                sprite.TransformToApply = mapControlScale * sprite.TransformToApply;
            }
        }
    }

    private bool TryGetMapControlSpriteBounds(RendererMetaData sprite, out Box2 bounds) {
        bounds = default;

        // Render target declarations and render relays are plumbing for the plane
        // system; using them for bounds makes one-tile map widgets look like the
        // whole default viewport.
        if (!string.IsNullOrEmpty(sprite.RenderTarget) || sprite.HasRenderSource)
            return false;

        var iconSize = sprite.MainIcon?.DMI?.IconSize;
        if (iconSize == null)
            return false;

        var size = iconSize.Value / (float)IconSize;
        bounds = Box2.FromDimensions(sprite.Position, size);
        return true;
    }

    //handles underlays, overlays, appearance flags, images. Adds them to the result list, so they can be sorted and drawn with DrawIcon()
    private void ProcessIconComponents(DreamIcon icon, Vector2 position, EntityUid uid, bool isScreen, ref int tieBreaker, List<RendererMetaData> result, sbyte seeVis, RendererMetaData? parentIcon = null, bool keepTogether = false, Vector3? turfCoords = null, ClientAppearanceSystem.Flick? flick = null, Vector2i boundOffset = default, Vector2? sortPosition = null) {
        if (icon.Appearance is null) //in the event that appearance hasn't loaded yet
            return;

        result.EnsureCapacity(result.Count + icon.Underlays.Count + icon.Overlays.Count + 1);
        RendererMetaData current = RentRendererMetaData();
        current.MainIcon = icon;
        current.SortIndex = _sortIndex++;
        current.AppearanceLayer = icon.Appearance.Layer;
        Vector2i iconSize = icon.DMI?.IconSize ?? new Vector2i(IconSize, IconSize);
        Vector2i pixelOffset = AppearancePositioning.GetPixelOffset(
            icon.Appearance,
            _interfaceManager.MapFormat,
            iconSize,
            boundOffset,
            parentIcon == null && !isScreen);

        current.Position = position + (pixelOffset / (float)IconSize);
        current.MapFormat = _interfaceManager.MapFormat;
        current.SortPosition = parentIcon?.SortPosition ?? sortPosition ?? position;

        if (parentIcon == null && !isScreen && _interfaceManager.MapFormat != MapFormat.TopDown)
            current.SortPosition += boundOffset / (float)IconSize;

        current.Uid = uid;
        current.ClickUid = uid;
        current.IsScreen = isScreen;
        current.TieBreaker = tieBreaker;
        current.RenderSource = icon.Appearance.RenderSource;
        current.RenderTarget = icon.Appearance.RenderTarget;
        current.AppearanceFlags = icon.Appearance.AppearanceFlags;
        current.BlendMode = icon.Appearance.BlendMode;
        current.Flick = flick;

        //reverse rotation transforms because of 180 flip from RenderTarget->world transform
        Matrix3x2 iconAppearanceTransformMatrix = new Matrix3x2(
            icon.Appearance.Transform[0], -icon.Appearance.Transform[2],
            -icon.Appearance.Transform[1], icon.Appearance.Transform[3],
            icon.Appearance.Transform[4], icon.Appearance.Transform[5]
        );

        if (parentIcon != null) {
            current.ClickUid = parentIcon.ClickUid;
            current.MouseOpacity = parentIcon.MouseOpacity;
            if ((icon.Appearance.AppearanceFlags & AppearanceFlags.ResetColor) != 0 || keepTogether) { //RESET_COLOR
                current.ColorToApply = icon.Appearance.Color;
                current.ColorMatrixToApply = icon.Appearance.ColorMatrix;
            } else {
                current.ColorToApply = parentIcon.ColorToApply * icon.Appearance.Color;
                ColorMatrix.Multiply(in parentIcon.ColorMatrixToApply, in icon.Appearance.ColorMatrix, out current.ColorMatrixToApply);
            }

            if ((icon.Appearance.AppearanceFlags & AppearanceFlags.ResetAlpha) != 0 || keepTogether) //RESET_ALPHA
                current.AlphaToApply = icon.Appearance.Alpha / 255.0f;
            else
                current.AlphaToApply = parentIcon.AlphaToApply * (icon.Appearance.Alpha / 255.0f);

            if ((icon.Appearance.AppearanceFlags & AppearanceFlags.ResetTransform) != 0 || keepTogether) //RESET_TRANSFORM
                current.TransformToApply = iconAppearanceTransformMatrix;
            else
                current.TransformToApply = iconAppearanceTransformMatrix * parentIcon.TransformToApply;

            if ((icon.Appearance.Plane < -10000)) //FLOAT_PLANE - Note: yes, this really is how it works. Yes it's dumb as shit.
                current.Plane = parentIcon.Plane + (icon.Appearance.Plane + 32767);
            else
                current.Plane = icon.Appearance.Plane;

            //FLOAT_LAYER - if this icon's layer is negative, it's a float layer so set it's layer equal to the parent object and sort through the float_layer shit later
            current.Layer = (icon.Appearance.Layer < 0) ? parentIcon.Layer : icon.Appearance.Layer;

            if (current.BlendMode == BlendMode.Default)
                current.BlendMode = parentIcon.BlendMode;
        } else {
            current.ColorToApply = icon.Appearance.Color;
            current.ColorMatrixToApply = icon.Appearance.ColorMatrix;
            current.AlphaToApply = icon.Appearance.Alpha / 255.0f;
            current.TransformToApply = iconAppearanceTransformMatrix;
            current.Plane = icon.Appearance.Plane;
            current.Layer = Math.Max(0, icon.Appearance.Layer); //float layers are invalid for icons with no parent
            current.MouseOpacity = icon.Appearance.MouseOpacity;
        }

        //special handling for EFFECTS_LAYER and BACKGROUND_LAYER
        //SO IT TURNS OUT EFFECTS_LAYER IS JUST A LIE *scream
        //and BACKGROUND_LAYER is basically the same behaviour as FLOAT_PLANE
        if (current.Layer >= 20000) {
            current.Layer -= 40000;
            current.IsScreen = false; //BACKGROUND_LAYER renders behind everything on that plane
        }

        keepTogether |= ((current.AppearanceFlags & AppearanceFlags.KeepTogether) != 0); //KEEP_TOGETHER

        // If the render-target starts with *, we don't render it to the base render target.
        // If it doesn't we create a placeholder RenderMetaData to position it correctly.
        // Ignore plane masters here, they're handled in DrawPlanes()
        if (!string.IsNullOrEmpty(current.RenderTarget) && current.RenderTarget[0] != '*' && !current.IsPlaneMaster) {
            RendererMetaData renderTargetPlaceholder = RentRendererMetaData();
            renderTargetPlaceholder.SortIndex = _sortIndex++;

            //transform, color, alpha, filters - they should all already have been applied, so we leave them null in the placeholder
            renderTargetPlaceholder.MainIcon = current.MainIcon;
            renderTargetPlaceholder.AppearanceLayer = current.AppearanceLayer;
            renderTargetPlaceholder.Position = current.Position;
            renderTargetPlaceholder.Uid = current.Uid;
            renderTargetPlaceholder.ClickUid = current.Uid;
            renderTargetPlaceholder.IsScreen = current.IsScreen;
            renderTargetPlaceholder.TieBreaker = current.TieBreaker;
            renderTargetPlaceholder.Plane = current.Plane;
            renderTargetPlaceholder.Layer = current.Layer;
            renderTargetPlaceholder.SortPosition = current.SortPosition;
            renderTargetPlaceholder.MapFormat = current.MapFormat;
            renderTargetPlaceholder.RenderSource = current.RenderTarget;
            renderTargetPlaceholder.MouseOpacity = current.MouseOpacity;
            renderTargetPlaceholder.AppearanceFlags = current.AppearanceFlags;
            result.Add(renderTargetPlaceholder);
        }

        //underlays - colour, alpha, and transform are inherited, but filters aren't
        //underlays are sorted in reverse order to overlays
        for(int underlayIndex = icon.Underlays.Count-1; underlayIndex >= 0; underlayIndex--) {
            DreamIcon underlay = icon.Underlays[underlayIndex];
            if (underlay.Appearance == null)
                continue;

            tieBreaker++;

            // KEEP_APART flag or on a different plane than the parent atom (implicitly treated as KEEP_APART)
            var keepApart = underlay.Appearance.Plane != icon.Appearance.Plane ||
                            (underlay.Appearance.AppearanceFlags & AppearanceFlags.KeepApart) != 0;

            if (!keepTogether || keepApart) { //KEEP_TOGETHER wasn't set on our parent, or KEEP_APART
                ProcessIconComponents(underlay, current.Position, uid, isScreen, ref tieBreaker, result, seeVis, current);
            } else {
                current.KeepTogetherGroup ??= new();
                ProcessIconComponents(underlay, current.Position, uid, isScreen, ref tieBreaker, current.KeepTogetherGroup, seeVis, current, keepTogether);
            }
        }

        tieBreaker++;
        current.TieBreaker = tieBreaker;

        //overlays - colour, alpha, and transform are inherited, but filters aren't
        foreach (DreamIcon overlay in icon.Overlays) {
            if (overlay.Appearance == null)
                continue;

            tieBreaker++;

            // KEEP_APART flag or on a different plane than the parent atom (implicitly treated as KEEP_APART)
            var keepApart = overlay.Appearance.Plane != icon.Appearance.Plane ||
                            (overlay.Appearance.AppearanceFlags & AppearanceFlags.KeepApart) != 0;

            if (!keepTogether || keepApart) { //KEEP_TOGETHER wasn't set on our parent, or KEEP_APART
                ProcessIconComponents(overlay, current.Position, uid, isScreen, ref tieBreaker, result, seeVis, current);
            } else {
                current.KeepTogetherGroup ??= new();
                ProcessIconComponents(overlay, current.Position, uid, isScreen, ref tieBreaker, current.KeepTogetherGroup, seeVis, current, keepTogether);
            }
        }

        //client images act as either an overlay or replace the main icon
        //notably they cannot be applied to overlays, so don't check for them if this is an under/overlay
        //note also that we use turfCoords and not current.Position because we want world-coordinates, not screen coordinates. This is only used for turfs.
        if(parentIcon == null && _imagesSystem.TryGetClientImages(current.Uid, turfCoords, out List<NetEntity>? attachedClientImages)){
            foreach(NetEntity ciNetEntity in attachedClientImages) {
                EntityUid imageEntity = _entityManager.GetEntity(ciNetEntity);
                if (!_spriteQuery.TryGetComponent(imageEntity, out var sprite))
                    continue;
                if(sprite.Icon.Appearance == null)
                    continue;
                if(sprite.Icon.Appearance.Override) {
                    current.MainIcon = sprite.Icon;
                    current.Position += (sprite.Icon.Appearance.GetTotalPixelOffset(_interfaceManager.MapFormat) / (float)IconSize);
                } else
                    ProcessIconComponents(sprite.Icon, current.Position, uid, isScreen, ref tieBreaker, result, seeVis, current);
            }
        }

        foreach (var visContent in icon.Appearance.VisContents) {
            EntityUid visContentEntity = _entityManager.GetEntity(visContent);
            if (!_spriteQuery.TryGetComponent(visContentEntity, out var sprite))
                continue;
            if (!_spriteSystem.IsVisible(sprite, null, seeVis, null))
                continue;

            ProcessIconComponents(sprite.Icon, current.Position, visContentEntity, isScreen, ref tieBreaker, result, seeVis, current, keepTogether);

            // TODO: click uid should be set to current.uid again
            // TODO: vis_flags
        }

        //maptext is basically just an image of rendered text added as an overlay
        if(icon.Appearance.Maptext != null){ //if has maptext
            RendererMetaData maptext = RentRendererMetaData();
            maptext.MainIcon = icon;
            maptext.SortIndex = _sortIndex++;
            maptext.AppearanceLayer = current.AppearanceLayer;
            maptext.Position = current.Position;
            maptext.Uid = current.Uid;
            maptext.ClickUid = current.Uid;
            maptext.IsScreen = current.IsScreen;
            tieBreaker++;
            maptext.TieBreaker = tieBreaker;
            maptext.Plane = current.Plane;
            maptext.Layer = current.Layer;
            maptext.SortPosition = current.SortPosition;
            maptext.MapFormat = current.MapFormat;
            maptext.RenderSource = null;
            maptext.RenderTarget = null;
            maptext.MouseOpacity = current.MouseOpacity;
            maptext.TransformToApply = current.TransformToApply;
            maptext.ColorToApply = current.ColorToApply;
            maptext.ColorMatrixToApply = current.ColorMatrixToApply;
            maptext.AlphaToApply = current.AlphaToApply;
            maptext.BlendMode = current.BlendMode;

            maptext.AppearanceFlags = current.AppearanceFlags;
            maptext.AppearanceFlags &= ~AppearanceFlags.PlaneMaster; //doesn't make sense for maptext

            maptext.Maptext = icon.Appearance.Maptext;
            maptext.MaptextSize = icon.Appearance.MaptextSize;
            maptext.Position += icon.Appearance.MaptextOffset/(float)IconSize;
            result.Add(maptext);
        }

        //query entity for particles component - check for parent to make sure this is the top level entity
        if(parentIcon is null && _particlesManager.TryGetParticleSystem(uid, out var particlesSystem)){
            current.Particles = particlesSystem;
        }

        //flatten KeepTogetherGroup. Done here so we get implicit recursive iteration down the tree.
        if (current.KeepTogetherGroup?.Count > 0) {
            List<RendererMetaData> flatKeepTogetherGroup = new List<RendererMetaData>(current.KeepTogetherGroup.Count);

            foreach (RendererMetaData ktItem in current.KeepTogetherGroup) {
                if (ktItem.KeepTogetherGroup != null)
                    flatKeepTogetherGroup.AddRange(ktItem.KeepTogetherGroup);

                flatKeepTogetherGroup.Add(ktItem);
                ktItem.KeepTogetherGroup = null; //might need to be Clear()
            }

            current.KeepTogetherGroup = flatKeepTogetherGroup;
        }

        result.Add(current);
    }

    public ShaderInstance GetBlendAndColorShader(RendererMetaData iconMetaData, bool ignoreColor = false, bool useOverlayMode = false) {
        BlendMode blendMode = useOverlayMode ? BlendMode.Overlay : iconMetaData.BlendMode;

        ColorMatrix colorMatrix;
        if (ignoreColor)
            colorMatrix = ColorMatrix.Identity;
        else
            colorMatrix = iconMetaData.ColorMatrixToApply;

        var blendAndColor = _blendModeInstances[blendMode];
        if (!iconMetaData.IsPlaneMaster && colorMatrix.Equals(ColorMatrix.Identity)) // We can get away with no duplication
            return blendAndColor;

        // RT's batching is a little broken and so we must duplicate the shader if we modify its parameters
        blendAndColor = blendAndColor.Duplicate();
        blendAndColor.SetParameter("colorMatrix", colorMatrix.GetMatrix4());
        blendAndColor.SetParameter("offsetVector", colorMatrix.GetOffsetVector());
        blendAndColor.SetParameter("isPlaneMaster", iconMetaData.IsPlaneMaster);
        return blendAndColor;
    }

    public void DrawIcon(DrawingHandleWorld handle, Vector2i renderTargetSize, RendererMetaData iconMetaData, Vector2 positionOffset) {
        DreamIcon? icon = iconMetaData.MainIcon;
        if (icon == null)
            return;

        //KEEP_TOGETHER groups
        if (iconMetaData.KeepTogetherGroup?.Count > 0) {
            // TODO: Calculate an appropriate size based on overlays/underlays, offsets and transforms.
            // For now, just generate a buffer of 128 pixels around the main icon...
            Vector2i ktSize = (256, 256) + iconMetaData.MainIcon?.DMI?.IconSize ?? (0,0);
            iconMetaData.TextureOverride = ProcessKeepTogether(handle, iconMetaData, ktSize);
            positionOffset -= ((ktSize/IconSize) - Vector2.One) * new Vector2(0.5f); //correct for KT group texture offset
        }

        //Maptext
        if (!string.IsNullOrWhiteSpace(iconMetaData.Maptext)) {
            var maptextSize = iconMetaData.MaptextSize!.Value;
            if (maptextSize.X == 0)
                maptextSize.X = 32;
            if (maptextSize.Y == 0)
                maptextSize.Y = 32;

            var renderTarget = _renderTargetPool.Rent(maptextSize);

            _mapTextRenderer.RenderToTarget(handle, renderTarget, iconMetaData.Maptext);
            _renderTargetPool.ReturnAtEndOfFrame(renderTarget);
            iconMetaData.TextureOverride = renderTarget.Texture;
        }

        var frame = iconMetaData.GetTexture(this, handle);
        var pixelPosition = (iconMetaData.Position + positionOffset) * IconSize;

        //if frame is null, this doesn't require a draw, so return NOP
        if (frame == null)
            return;

        if (iconMetaData.MainIcon != null)
            pixelPosition += iconMetaData.MainIcon.TextureRenderOffset;

        handle.UseShader(GetBlendAndColorShader(iconMetaData, ignoreColor: true));

        handle.SetTransform(CalculateDrawingMatrix(iconMetaData.TransformToApply, pixelPosition, frame.Size, renderTargetSize));

        Color colorToApply = iconMetaData.ColorToApply;
        colorToApply.A *= iconMetaData.AlphaToApply;

        handle.DrawTextureRect(frame, Box2.FromDimensions(Vector2.Zero, frame.Size), colorToApply);

        if (iconMetaData.Particles is not null) {
            handle.UseShader(GetBlendAndColorShader(iconMetaData, ignoreColor: true));
            iconMetaData.Particles.Draw(handle, CalculateDrawingMatrix(iconMetaData.TransformToApply, pixelPosition, iconMetaData.Particles.RenderSize, renderTargetSize));
        }
    }

    /// <summary>
    /// Recreate all our render targets if our viewport size has changed.
    /// Also clears the mouse map and base render target.
    /// </summary>
    private void RefreshRenderTargets(DrawingHandleWorld handle, Vector2i size) {
        RefreshRenderTargets(handle, size, Planes, ref _baseRenderTarget, ref _mouseMapRenderTarget);
    }

    private void RefreshRenderTargets(DrawingHandleWorld handle, Vector2i size, Dictionary<int, DreamPlane> planes, ref IRenderTexture? baseRenderTarget) {
        if (baseRenderTarget == null || baseRenderTarget.Size != size) {
            baseRenderTarget?.Dispose();
            baseRenderTarget = _clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8Srgb), name: "Base Render Target");

            foreach (var (planeId, plane) in planes) {
                plane.SetMainRenderTarget(_clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8Srgb), name: $"Plane {planeId}"));
            }
        }
    }

    private void RefreshRenderTargets(DrawingHandleWorld handle, Vector2i size, Dictionary<int, DreamPlane> planes, ref IRenderTexture? baseRenderTarget, ref IRenderTexture? mouseMapRenderTarget) {
        if (baseRenderTarget == null || baseRenderTarget.Size != size) {
            baseRenderTarget?.Dispose();
            mouseMapRenderTarget?.Dispose();
            baseRenderTarget = _clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8Srgb), name: "Base Render Target");
            mouseMapRenderTarget = _clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8Srgb), name: "MouseMap");

            foreach (var (planeId, plane) in planes) {
                plane.SetMainRenderTarget(_clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8Srgb), name: $"Plane {planeId}"));
            }
        } else {
            // Clear the mouse map lookup dictionary
            MouseMapLookup.Clear();
        }
    }

    private void ClearPlanes() {
        ClearPlanes(Planes);
    }

    private void ClearPlanes(Dictionary<int, DreamPlane> planes) {
        List<int>? removePlanes = null;
        foreach (var (planeIndex, plane) in planes) {

            // We can remove the plane if there was nothing on it last frame
            if (plane.Sprites.Count == 0 && plane.Master == null) {
                plane.Dispose();
                removePlanes ??= new();
                removePlanes.Add(planeIndex);
                continue;
            }

            plane.Clear();
        }

        if (removePlanes == null)
            return;

        foreach (var planeIndex in removePlanes) {
            planes.Remove(planeIndex);
        }
    }

    private DreamPlane GetPlane(int planeIndex, Vector2i viewportSize) {
        return GetPlane(Planes, planeIndex, viewportSize);
    }

    private DreamPlane GetPlane(Dictionary<int, DreamPlane> planes, int planeIndex, Vector2i viewportSize) {
        if (planes.TryGetValue(planeIndex, out var plane))
            return plane;

        var renderTarget = _clyde.CreateRenderTarget(viewportSize, new(RenderTargetColorFormat.Rgba8Srgb), name: $"Plane {planeIndex}");

        plane = new(renderTarget);
        planes.Add(planeIndex, plane);
        _sawmill.Verbose($"Created plane {planeIndex}");
        return plane;
    }

    private void ProcessSprites(DrawingHandleWorld handle, Vector2i viewportSize, Box2 worldAABB) {
        ProcessSprites(handle, viewportSize, worldAABB, Planes);
    }

    private void ProcessSprites(DrawingHandleWorld handle, Vector2i viewportSize, Box2 worldAABB, Dictionary<int, DreamPlane> planes) {
        using var _ = _prof.Group("process sprites / draw render targets");
        HashSet<string>? clearedRenderTargets = null;

        //all sprites with render targets get handled first - these are ordered by sprites.Sort(), so we can just iterate normally
        foreach (var sprite in _spriteContainer) {
            var plane = GetPlane(planes, sprite.Plane, viewportSize);

            if (!string.IsNullOrEmpty(sprite.RenderTarget)) {
                //if this sprite has a render target, draw it to a slate instead. If it needs to be drawn on the map, a second sprite instance will already have been created for that purpose
                if (!RenderSourceLookup.TryGetValue(sprite.RenderTarget, out var tmpRenderTarget)) {
                    var size = sprite.IsPlaneMaster ? viewportSize : sprite.MainIcon?.DMI?.IconSize ?? viewportSize;
                    tmpRenderTarget = _renderTargetPool.Rent(size);
                    RenderSourceLookup.Add(sprite.RenderTarget, tmpRenderTarget);
                    _renderTargetPool.ReturnAtEndOfFrame(tmpRenderTarget);
                }

                if (sprite.IsPlaneMaster) { //if this is also a plane master
                    sprite.Position = Vector2.Zero; //plane masters should not have a position offset
                    plane.Master = sprite;
                    plane.SetTemporaryRenderTarget(tmpRenderTarget);
                } else { //if not a plane master, draw the sprite to the render target
                    //note we don't draw this to the mouse-map because that's handled when the RenderTarget is used as a source later
                    clearedRenderTargets ??= new();
                    DrawOnRenderTarget(handle, tmpRenderTarget, sprite, clearedRenderTargets.Add(sprite.RenderTarget));
                }
            } else { //We are no longer dealing with RenderTargets, just regular old planes, so we collect the draw actions for batching
                //if this is a plane master then we don't render it, we just set it as the plane's master
                if (sprite.IsPlaneMaster) {
                    sprite.Position = Vector2.Zero; //plane masters should not have a position offset
                    plane.Master = sprite;

                    continue;
                }

                //add this sprite for rendering
                plane.Sprites.Add(sprite);
            }
        }
    }

    /// <summary>
    /// Used by <see cref="ProcessSprites"/> to render an icon onto its render_target.
    /// In a separate method to prevent unused closure allocations.
    /// </summary>
    private void DrawOnRenderTarget(DrawingHandleWorld handle, IRenderTarget renderTarget, RendererMetaData sprite, bool clearTarget) {
        handle.RenderInRenderTarget(renderTarget, () => {
            //draw the sprite centered on the RenderTarget
            DrawIcon(handle, renderTarget.Size, sprite, -sprite.Position);
        }, clearTarget ? new Color() : null);
    }

    private void DrawPlanes(DrawingHandleWorld handle, Box2 worldAABB) {
        DrawPlanes(handle, worldAABB, Planes, _baseRenderTarget, _mouseMapRenderTarget, drawMouseMap: true);
    }

    private void DrawPlanes(DrawingHandleWorld handle, Box2 worldAABB, Dictionary<int, DreamPlane> planes, IRenderTexture? baseRenderTarget, IRenderTexture? mouseMapRenderTarget, bool drawMouseMap) {
        if (baseRenderTarget == null)
            return;

        using (var _ = _prof.Group("draw planes map")) {
            handle.RenderInRenderTarget(baseRenderTarget, () => {
                foreach (int planeIndex in planes.Keys.Order()) {
                    var plane = planes[planeIndex];

                    plane.Draw(this, handle, worldAABB);

                    if (plane.Master != null) {
                        // Don't draw this to the base render target if it has a RenderTarget starting with '*'
                        if (plane.Master.RenderTarget?.StartsWith('*') is true)
                            continue;

                        plane.Master.TextureOverride = plane.RenderTarget.Texture;
                        DrawIcon(handle, baseRenderTarget.Size, plane.Master, Vector2.Zero);
                    } else {
                        handle.UseShader(null);
                        handle.SetTransform(CreateRenderTargetFlipMatrix(baseRenderTarget.Size, Vector2.Zero));
                        handle.DrawTextureRect(plane.RenderTarget.Texture, Box2.FromTwoPoints(Vector2.Zero, baseRenderTarget.Size));
                    }
                }
            }, new Color());
        }

        if (drawMouseMap && mouseMapRenderTarget != null) {
            // TODO: Can this only be done once the user clicks?
            using (_prof.Group("draw planes mouse map")) {
                handle.RenderInRenderTarget(mouseMapRenderTarget, () => {
                    foreach (int planeIndex in planes.Keys.Order())
                        planes[planeIndex].DrawMouseMap(handle, this, mouseMapRenderTarget.Size, worldAABB);
                }, new Color());
            }
        }
    }

    private void CollectVisibleSprites(ViewAlgorithm.Tile?[,] tiles, EntityUid gridUid, MapGridComponent grid, TileRef eyeTile, sbyte seeVis, SightFlags sight, Box2 worldAABB, string? mapControlId) {
        _spriteContainer.Clear();
        _sortIndex = 0;

        // This exists purely because the tiebreaker var needs to exist somewhere
        // It's set to 0 again before every unique call to ProcessIconComponents
        int tValue;

        // Visible turf sprites
        foreach (var tile in tiles) {
            if (tile == null)
                continue;
            if (!tile.IsVisible && (sight & SightFlags.SeeTurfs) == 0)
                continue;

            Vector2i tilePos = eyeTile.GridIndices + (tile.DeltaX, tile.DeltaY);
            TileRef tileRef = _mapSystem.GetTileRef(gridUid, grid, tilePos);
            MapCoordinates worldPos = _mapSystem.GridTileToWorld(gridUid, grid, tilePos);
            var flick = _appearanceSystem.GetTurfFlick(tilePos.X, tilePos.Y, (int) worldPos.MapId);

            tValue = 0;
            //pass the turf coords for client.images lookup
            Vector3 turfCoords = new Vector3(tileRef.X, tileRef.Y, (int) worldPos.MapId);
            ProcessIconComponents(_appearanceSystem.GetTurfIcon((uint)tileRef.Tile.TypeId), worldPos.Position - Vector2.One, EntityUid.Invalid, false, ref tValue, _spriteContainer, seeVis, turfCoords: turfCoords, flick: flick);
        }

        // Visible entities
        using (var _ = _prof.Group("process entities")) {
            foreach (EntityUid entity in EntitiesInView) {
                // TODO use a sprite tree.
                if (!_spriteQuery.TryGetComponent(entity, out var sprite))
                    continue;

                var transform = _xformQuery.GetComponent(entity);
                if (!_spriteSystem.IsVisible(sprite, transform, seeVis, worldAABB))
                    continue;

                var worldPos = _transformSystem.GetWorldPosition(transform);
                var sortPos = GetLogicalWorldPosition(entity, transform);

                // Check for visibility if the eye doesn't have SEE_OBJS or SEE_MOBS
                // TODO: Differentiate between objs and mobs
                if ((sight & (SightFlags.SeeObjs|SightFlags.SeeMobs)) == 0 && _tileInfo != null) {
                    var tilePos = _mapSystem.WorldToTile(gridUid, grid, sortPos) - eyeTile.GridIndices + _interfaceManager.View.Center + 1;
                    if (tilePos.X < 0 || tilePos.Y < 0 || tilePos.X >= _tileInfo.GetLength(0) || tilePos.Y >= _tileInfo.GetLength(1))
                        continue;

                    var tile = tiles[tilePos.X, tilePos.Y];
                    if (tile?.IsVisible is not true)
                        continue;
                }

                var flick = _appearanceSystem.GetMovableFlick(entity);

                tValue = 0;
                ProcessIconComponents(sprite.Icon, worldPos - new Vector2(0.5f), entity, false, ref tValue, _spriteContainer, seeVis, flick: flick, boundOffset: sprite.BoundOffset, sortPosition: sortPos - new Vector2(0.5f));
            }
        }

        CollectScreenObjects(seeVis, worldAABB.BottomLeft, mapControlId);

        using (_prof.Group("sort sprites")) {
            _spriteContainer.Sort();
        }
    }

    private void CollectScreenObjects(sbyte seeVis, Vector2 viewOffset, string? mapControlId) {
        if (ScreenOverlayEnabled) {
            using var _ = _prof.Group("screen objects");

            List<(EntityUid Uid, DMISpriteComponent Sprite, ScreenLocation ScreenLocation, Vector2i IconSize)> screenObjects = new();
            ScreenLocationBounds screenBounds = new(0, 0, _interfaceManager.View.Width, _interfaceManager.View.Height);

            int totalScreenObjects = 0;
            int nullSpriteOrLocation = 0;
            int invisibleObjects = 0;
            int wrongMapControl = 0;
            int matchingObjects = 0;
            foreach (EntityUid uid in _screenOverlaySystem.ScreenObjects) {
                totalScreenObjects++;
                if (!_entityManager.TryGetComponent(uid, out DMISpriteComponent? sprite) || sprite.ScreenLocation == null) {
                    nullSpriteOrLocation++;
                    continue;
                }
                if (!_spriteSystem.IsVisible(sprite, null, seeVis, null)) {
                    invisibleObjects++;
                    continue;
                }
                if (!string.Equals(sprite.ScreenLocation.MapControl, mapControlId, StringComparison.OrdinalIgnoreCase)) {
                    wrongMapControl++;
                    continue;
                }
                matchingObjects++;

                ScreenLocation screenLocation = sprite.ScreenLocation;
                Vector2i dmiIconSize = sprite.Icon.DMI?.IconSize ?? new(IconSize, IconSize);
                screenObjects.Add((uid, sprite, screenLocation, dmiIconSize));
                if (!screenLocation.AnchorToScreenBounds)
                    screenBounds = screenBounds.Include(screenLocation.GetScreenBounds(_interfaceManager.View, IconSize, dmiIconSize));
            }

            foreach ((EntityUid uid, DMISpriteComponent sprite, ScreenLocation screenLocation, Vector2i dmiIconSize) in screenObjects) {
                Vector2 position = screenLocation.GetViewPosition(viewOffset, _interfaceManager.View, IconSize, dmiIconSize, screenBounds);
                Vector2 iconSize = sprite.Icon.DMI == null ? Vector2.Zero : sprite.Icon.DMI.IconSize / (float)IconSize;
                for (int x = 0; x < screenLocation.RepeatX; x++) {
                    for (int y = 0; y < screenLocation.RepeatY; y++) {
                        int tValue = 0;
                        ProcessIconComponents(sprite.Icon, position + iconSize * new Vector2(x, y), uid, true, ref tValue, _spriteContainer, seeVis);
                    }
                }
            }
        }
    }

    private sealed class MapControlRenderState {
        public IRenderTexture? BaseRenderTarget;
        public readonly Dictionary<int, DreamPlane> Planes = new();
    }

    private MapCoordinates GetLogicalMapCoordinates(EntityUid uid, TransformComponent transform) {
        var coords = _transformSystem.GetMapCoordinates(uid, transform);
        return _atomGlideSystem.TryGetLogicalPosition(uid, transform, out var logicalPosition)
            ? new MapCoordinates(logicalPosition, coords.MapId)
            : coords;
    }

    private Vector2 GetLogicalWorldPosition(EntityUid uid, TransformComponent transform) {
        return _atomGlideSystem.TryGetLogicalPosition(uid, transform, out var logicalPosition)
            ? logicalPosition
            : _transformSystem.GetWorldPosition(transform);
    }

    private RendererMetaData RentRendererMetaData() {
        RendererMetaData result;
        if (_rendererMetaDataRental.Count == 0)
            result = new RendererMetaData();
        else {
            result = _rendererMetaDataRental.Pop();
            result.Reset();
        }

        _rendererMetaDataToReturn.Push(result);
        return result;
    }

    /// <summary>
    /// Collect all of an icon's keep-together group and render them into one texture.
    /// </summary>
    private Texture ProcessKeepTogether(DrawingHandleWorld handle, RendererMetaData iconMetaData, Vector2i size) {
        //store the parent's transform, color, blend, and alpha - then clear them for drawing to the render target
        Matrix3x2 ktParentTransform = iconMetaData.TransformToApply;
        Color ktParentColor = iconMetaData.ColorToApply;
        float ktParentAlpha = iconMetaData.AlphaToApply;
        BlendMode ktParentBlendMode = iconMetaData.BlendMode;

        iconMetaData.TransformToApply = Matrix3x2.Identity;
        iconMetaData.ColorToApply = Color.White;
        iconMetaData.AlphaToApply = 1f;
        iconMetaData.BlendMode = BlendMode.Default;

        List<RendererMetaData> ktItems = new List<RendererMetaData>(iconMetaData.KeepTogetherGroup!.Count + 1) {
            iconMetaData
        };
        ktItems.AddRange(iconMetaData.KeepTogetherGroup);
        iconMetaData.KeepTogetherGroup.Clear();

        ktItems.Sort();
        //draw it onto an additional render target that we can return immediately for correction of transform
        IRenderTexture tempTexture = _renderTargetPool.Rent(size);

        handle.RenderInRenderTarget(tempTexture, () => {
            foreach (RendererMetaData ktItem in ktItems) {
                //draw the icon in the centre of the KT render target, based on the main icon position
                DrawIcon(handle, tempTexture.Size, ktItem, -iconMetaData.Position+((tempTexture.Size/IconSize) - Vector2.One) * new Vector2(0.5f));
            }
        }, Color.Transparent);

        //but keep the handle to the final KT group's render target so we don't override it later in the render cycle
        IRenderTexture ktTexture = _renderTargetPool.Rent(tempTexture.Size);
        handle.RenderInRenderTarget(ktTexture, () => {
            handle.UseShader(null);
            handle.SetTransform(CreateRenderTargetFlipMatrix(tempTexture.Size, Vector2.Zero));
            handle.DrawTextureRect(tempTexture.Texture, new Box2(Vector2.Zero, tempTexture.Size));
        }, Color.Transparent);

        _renderTargetPool.ReturnAtEndOfFrame(tempTexture);

        //now restore the original color, alpha, blend, and transform so they can be applied to the render target as a whole
        iconMetaData.TransformToApply = ktParentTransform;
        iconMetaData.ColorToApply = ktParentColor;
        iconMetaData.AlphaToApply = ktParentAlpha;
        iconMetaData.BlendMode = ktParentBlendMode;

        _renderTargetPool.ReturnAtEndOfFrame(ktTexture);
        return ktTexture.Texture;
    }

    /// <summary>
    /// Creates a transformation matrix that counteracts RT's
    /// <see cref="DrawingHandleBase.RenderInRenderTarget(IRenderTarget,Action,System.Nullable{Robust.Shared.Maths.Color})"/> quirks
    /// <br/>
    /// If you are using render targets, you will almost certainly want to use this
    /// </summary>
    /// <param name="renderTargetSize">Size of the render target</param>
    /// <param name="renderPosition">The translation to draw the icon at</param>
    /// <remarks>Due to RT applying transformations out of order, render the icon at Vector2.Zero</remarks>
    public static Matrix3x2 CreateRenderTargetFlipMatrix(Vector2i renderTargetSize, Vector2 renderPosition) {
        // RT flips the texture when doing a RenderInRenderTarget(), so we use _flipMatrix to reverse it
        // We must also handle translations here, since RT applies its own transform in an unexpected order
        return FlipMatrix * Matrix3x2.CreateTranslation(renderPosition.X, renderTargetSize.Y - renderPosition.Y);
    }

    public static Matrix3x2 CalculateDrawingMatrix(Matrix3x2 transform, Vector2 pixelPosition, Vector2i frameSize, Vector2i renderTargetSize) {
        //extract scale component of transform
        Vector2 scaleFactors = new Vector2(
            MathF.Sqrt(MathF.Pow(transform.M11,2) + MathF.Pow(transform.M12,2)),
            MathF.Sqrt(MathF.Pow(transform.M21,2) + MathF.Pow(transform.M22,2))
        );
        transform.M11 /= scaleFactors.X;
        transform.M12 /= scaleFactors.X;
        transform.M21 /= scaleFactors.Y;
        transform.M22 /= scaleFactors.Y;

        return
            Matrix3x2.CreateTranslation(-frameSize/2)  //translate to origin
            * transform                                       //rotate and translate
            * Matrix3x2.CreateTranslation(frameSize/2)       //translate back to original position
            * Matrix3x2.CreateScale(scaleFactors)               //scale
            * CreateRenderTargetFlipMatrix(renderTargetSize, pixelPosition-((scaleFactors-Vector2.One)*frameSize/2)); //flip and apply scale-corrected translation
    }
}

#region Render Toggle Commands
public sealed class ToggleScreenOverlayCommand : IConsoleCommand {
    // ReSharper disable once StringLiteralTypo
    public string Command => "togglescreenoverlay";
    public string Description => "Toggle rendering of screen objects";
    public string Help => "";

    public void Execute(IConsoleShell shell, string argStr, string[] args) {
        if (args.Length != 0) {
            shell.WriteError("This command does not take any arguments!");
            return;
        }

        IOverlayManager overlayManager = IoCManager.Resolve<IOverlayManager>();
        if (overlayManager.TryGetOverlay(typeof(DreamViewOverlay), out var overlay) &&
            overlay is DreamViewOverlay screenOverlay) {
            screenOverlay.ScreenOverlayEnabled = !screenOverlay.ScreenOverlayEnabled;
        }
    }
}

public sealed class ToggleMouseOverlayCommand : IConsoleCommand {
    // ReSharper disable once StringLiteralTypo
    public string Command => "togglemouseoverlay";
    public string Description => "Toggle rendering of mouse click area for screen objects";
    public string Help => "";

    public void Execute(IConsoleShell shell, string argStr, string[] args) {
        if (args.Length != 0) {
            shell.WriteError("This command does not take any arguments!");
            return;
        }

        IOverlayManager overlayManager = IoCManager.Resolve<IOverlayManager>();
        if (overlayManager.TryGetOverlay(typeof(DreamViewOverlay), out var overlay) &&
            overlay is DreamViewOverlay screenOverlay) {
            screenOverlay.MouseMapRenderEnabled = !screenOverlay.MouseMapRenderEnabled;
        }
    }
}
#endregion
