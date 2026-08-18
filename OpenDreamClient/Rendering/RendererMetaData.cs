using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using OpenDreamClient.Rendering.Particles;

namespace OpenDreamClient.Rendering;

internal sealed class RendererMetaData : IComparable<RendererMetaData> {
    public DreamIcon? MainIcon;
    public Vector2 Position;
    public Vector2 SortPosition;
    public MapFormat MapFormat;
    public int Plane; //true plane value may be different from appearance plane value, due to special flags
    public float Layer; //ditto for layer
    public float AppearanceLayer;
    public EntityUid Uid;
    public EntityUid ClickUid; //the UID of the object clicks on this should be passed to (ie, for overlays)
    public bool IsScreen;
    public int TieBreaker; //Used for biasing render order (ie, for overlays)
    public int SortIndex; //Preserves BYOND-visible insertion order when all other ordering matches
    public Color ColorToApply;
    public ColorMatrix ColorMatrixToApply;
    public float AlphaToApply;
    public Matrix3x2 TransformToApply;
    public string? RenderSource;
    public string? RenderTarget;
    public List<RendererMetaData>? KeepTogetherGroup;
    public AppearanceFlags AppearanceFlags;
    public BlendMode BlendMode;
    public MouseOpacity MouseOpacity;
    public Texture? TextureOverride;
    public string? Maptext;
    public Vector2i? MaptextSize;
    public ParticleSystem? Particles;
    public ClientAppearanceSystem.Flick? Flick;

    public bool IsPlaneMaster => (AppearanceFlags & AppearanceFlags.PlaneMaster) != 0;
    public bool HasRenderSource => !string.IsNullOrEmpty(RenderSource);
    public bool ShouldPassMouse => HasRenderSource && (AppearanceFlags & AppearanceFlags.PassMouse) != 0;

    public RendererMetaData() {
        Reset();
    }

    public void Reset() {
        MainIcon = null;
        Position = Vector2.Zero;
        SortPosition = Vector2.Zero;
        MapFormat = MapFormat.TopDown;
        Plane = 0;
        Layer = 0;
        AppearanceLayer = 0;
        Uid = EntityUid.Invalid;
        ClickUid = EntityUid.Invalid;
        IsScreen = false;
        TieBreaker = 0;
        SortIndex = 0;
        ColorToApply = Color.White;
        ColorMatrixToApply = ColorMatrix.Identity;
        AlphaToApply = 1.0f;
        TransformToApply = Matrix3x2.Identity;
        RenderSource = "";
        RenderTarget = "";
        KeepTogetherGroup = null; //don't actually need to allocate this 90% of the time
        AppearanceFlags = AppearanceFlags.None;
        BlendMode = BlendMode.Default;
        MouseOpacity = MouseOpacity.Transparent;
        TextureOverride = null;
        Maptext = null;
        MaptextSize = null;
        Particles = null;
    }

    public Texture? GetTexture(DreamViewOverlay viewOverlay, DrawingHandleWorld handle) {
        if (MainIcon == null)
            return null;

        var texture = MainIcon.GetTexture(viewOverlay, handle, this, TextureOverride, Flick);
        MainIcon.LastRenderedTexture = texture;
        return texture;
    }

    public int CompareTo(RendererMetaData? other) {
        if (other == null)
            return 1;

        //Render target and source ordering is done first.
        //Anything with a render target goes first
        int val = (!string.IsNullOrEmpty(RenderTarget)).CompareTo(!string.IsNullOrEmpty(other.RenderTarget));
        if (val != 0) {
            return -val;
        }

        //Anything with a render source which points to a render target must come *after* that render_target
        if (HasRenderSource && RenderSource == other.RenderTarget) {
            return 1;
        }

        //We now return to your regularly scheduled sprite render order

        //Plane
        val =  Plane.CompareTo(other.Plane);
        if (val != 0) {
            return val;
        }

        //Plane master objects go first for any given plane
        val = IsPlaneMaster.CompareTo(other.IsPlaneMaster);
        if (val != 0) {
            return -val; //sign flip because we want 1 < -1
        }

        //sub-plane (ie, HUD vs not HUD)
        val = IsScreen.CompareTo(other.IsScreen);
        if (val != 0) {
            return val;
        }

        if (MapFormat == MapFormat.TopDown || IsScreen) {
            val = Layer.CompareTo(other.Layer);
            if (val != 0) {
                return val;
            }
        } else {
            // Side-map draws in tile rows from north to south; southern rows are in
            // front. Rows come from the sprite's visual position, floored to whole
            // tiles, so a glide keeps the mover in its departure row until it has
            // visually arrived. Within a row, layer decides - and X never does: BYOND
            // doesn't depth-sort horizontally, and doing so drew a departed tile's
            // floor content over westward-gliding mobs.
            val = MathF.Floor(other.SortPosition.Y - 0.5f).CompareTo(MathF.Floor(SortPosition.Y - 0.5f));
            if (val != 0) {
                return val;
            }

            val = Layer.CompareTo(other.Layer);
            if (val != 0) {
                return val;
            }
        }

        //Finally, tie-breaker - in BYOND, this is order of creation of the sprites
        //for us, we use EntityUID, with a tie-breaker (for underlays/overlays)
        val = Uid.CompareTo(other.Uid);
        if (val != 0) {
            return val;
        }

        //FLOAT_LAYER must be sorted local to the thing they're floating on, and since all overlays/underlays share their parent's UID, we
        //can do that here.
        if (AppearanceLayer < -1 && other.AppearanceLayer < -1) { //if these are FLOAT_LAYER, sort amongst them
            val = AppearanceLayer.CompareTo(other.AppearanceLayer);
            if (val != 0) {
                return val;
            }
        }

        val = TieBreaker.CompareTo(other.TieBreaker);
        if (val != 0) {
            return val;
        }

        return SortIndex.CompareTo(other.SortIndex);
    }
}
