using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using Robust.Shared.Utility;

namespace OpenDreamClient.Rendering;

/// <summary>Counters for the mouse-map diagnostic (opendream.debug_mousemap).</summary>
internal sealed class MouseMapStats {
    public int SkippedPlanes;
    public int SkippedSprites;
    public int SpriteTransparent;
    public int SpritePassMouse;
    public int SpriteNoTexture;
    public int Registered;
    public readonly List<string> Notes = new();

    public readonly Dictionary<int, int> RegisteredPerPlane = new();

    public void Note(string note) {
        if (Notes.Count < 12)
            Notes.Add(note);
    }

    public void CountPlane(int planeIndex) {
        RegisteredPerPlane.TryGetValue(planeIndex, out var n);
        RegisteredPerPlane[planeIndex] = n + 1;
    }
}

internal sealed class DreamPlane(IRenderTexture mainRenderTarget) : IDisposable {
    public IRenderTexture RenderTarget => _temporaryRenderTarget ?? mainRenderTarget;
    public RendererMetaData? Master;
    public bool Enabled = true;

    public readonly List<RendererMetaData> Sprites = new();

    private IRenderTexture? _temporaryRenderTarget;

    public void Clear() {
        Master = null;
        Sprites.Clear();
        _temporaryRenderTarget = null;
    }

    public void Dispose() {
        mainRenderTarget.Dispose();
        Clear();
    }

    /// <summary>
    /// Sets this plane's main render target<br/>
    /// Persists through calls to <see cref="Clear()"/>
    /// </summary>
    public void SetMainRenderTarget(IRenderTexture renderTarget) {
        mainRenderTarget.Dispose();
        mainRenderTarget = renderTarget;
    }

    /// <summary>
    /// Sets this plane's render target until the next <see cref="Clear()"/>
    /// </summary>
    public void SetTemporaryRenderTarget(IRenderTexture renderTarget) {
        DebugTools.Assert(_temporaryRenderTarget == null, "Temporary render target has already been set");
        _temporaryRenderTarget = renderTarget;
    }

    /// <summary>
    /// Clears this plane's render target, then draws all the plane's icons onto it
    /// </summary>
    public void Draw(DreamViewOverlay overlay, DrawingHandleWorld handle, Box2 worldAABB) {
        // Draw all icons
        handle.RenderInRenderTarget(mainRenderTarget, () => {
            if (!Enabled) // Inside the RenderInRenderTarget() to ensure it gets cleared
                return;

            foreach (var sprite in Sprites) {
                var positionOffset = -worldAABB.BottomLeft;

                if (sprite.HasRenderSource && overlay.RenderSourceLookup.TryGetValue(sprite.RenderSource!, out var renderSourceTexture)) {
                    sprite.TextureOverride = renderSourceTexture.Texture;
                }

                overlay.DrawIcon(handle, mainRenderTarget.Size, sprite, positionOffset);
            }
        }, new Color());

        if (_temporaryRenderTarget != null) {
            // Draw again, but with the color applied
            handle.RenderInRenderTarget(_temporaryRenderTarget, () => {
                if (Master == null || !Enabled)
                    return;

                Master.TextureOverride = mainRenderTarget.Texture;
                var texture = Master.GetTexture(overlay, handle);
                Master.TextureOverride = null;
                if (texture == null)
                    return;

                handle.UseShader(overlay.GetBlendAndColorShader(Master, useOverlayMode: true));
                handle.SetTransform(DreamViewOverlay.CreateRenderTargetFlipMatrix(_temporaryRenderTarget.Size, Master.MainIcon?.TextureRenderOffset ?? Vector2.Zero));
                handle.DrawTextureRect(texture, new Box2(Vector2.Zero, texture.Size), Color.ToSrgb(Master.ColorToApply));
            }, new Color());
        }
    }

    /// <summary>
    /// Draws this plane's mouse map onto the current render target
    /// </summary>
    public void DrawMouseMap(DrawingHandleWorld handle, DreamViewOverlay overlay, Vector2i renderTargetSize, Box2 worldAABB, MouseMapStats? stats = null, int planeIndex = 0) {
        // NOTE: dropping this plane-level gate entirely is wrong - it lets the
        // lighting and overlay-light planes into the mouse map, where they eat clicks
        // (a flashlight cone becomes clickable, and mobs under it stop being). The
        // gate stays until it is understood WHICH planes carry the mobs.
        if (Master?.MouseOpacity == MouseOpacity.Transparent || !Enabled) {
            if (stats != null && Sprites.Count > 0) {
                stats.SkippedPlanes++;
                stats.SkippedSprites += Sprites.Count;
                stats.Note(Master?.MouseOpacity == MouseOpacity.Transparent
                    ? $"p{planeIndex}:master-transparent({Sprites.Count})"
                    : $"p{planeIndex}:disabled({Sprites.Count})");
            }

            return;
        }

        handle.UseShader(overlay.BlockColorInstance);
        foreach (var sprite in Sprites) {
            if (sprite.MouseOpacity == MouseOpacity.Transparent || sprite.ShouldPassMouse) {
                if (stats != null) {
                    if (sprite.ShouldPassMouse)
                        stats.SpritePassMouse++;
                    else
                        stats.SpriteTransparent++;
                }

                continue;
            }

            var texture = sprite.MainIcon?.LastRenderedTexture;
            if (texture == null) {
                if (stats != null)
                    stats.SpriteNoTexture++;
                continue;
            }

            if (stats != null) {
                stats.Registered++;
                stats.CountPlane(planeIndex);
            }

            // For mouse_opacity = 2, discard transparency but keep the size.
            var textureSize = texture.Size;
            if (sprite.MouseOpacity == MouseOpacity.Opaque) {
                texture = Texture.White;
            }

            var pos = (sprite.Position - worldAABB.BottomLeft) * overlay.IconSize;
            if (sprite.MainIcon != null)
                pos += sprite.MainIcon.TextureRenderOffset;

            // Match DrawIcon: a keep-together group is drawn into an oversized buffer
            // and shifted to centre it. Without the same shift the clickable area
            // lands several tiles away, which made every KT mob - humans, monkeys -
            // unclickable, and examining one hit the turf underneath instead.
            pos -= sprite.KeepTogetherPixelOffset;

            int hash = sprite.GetHashCode();
            var colorR = (byte)(hash & 0xFF);
            var colorG = (byte)((hash >> 8) & 0xFF);
            var colorB = (byte)((hash >> 16) & 0xFF);
            Color targetColor = new Color(colorR, colorG, colorB); //TODO - this could result in mis-clicks due to hash-collision since we ditch a whole byte.
            overlay.MouseMapLookup[targetColor] = sprite;
            handle.SetTransform(DreamViewOverlay.CalculateDrawingMatrix(sprite.TransformToApply, pos, textureSize, renderTargetSize));
            // Pre-encode: the readback compares raw bytes against MouseMapLookup keys
            handle.DrawTextureRect(texture, new Box2(Vector2.Zero, textureSize), Color.ToSrgb(targetColor));
        }
    }
}
