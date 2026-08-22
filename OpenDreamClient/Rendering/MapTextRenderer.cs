using System.Diagnostics.Contracts;
using System.Globalization;
using System.Text;
using OpenDreamClient.Interface.Html;
using OpenDreamClient.Resources;
using OpenDreamClient.Resources.ResourceTypes;
using System.IO;
using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using Robust.Client.ResourceManagement;
using Robust.Client.UserInterface.RichText;
using Robust.Shared.ContentPack;
using Robust.Shared.Utility;

namespace OpenDreamClient.Rendering;

/// <summary>
/// Helper for rendering maptext to a render target.
/// Adapted from RobustToolbox's RichTextEntry.
/// </summary>
public sealed class MapTextRenderer {
    [Dependency] private IResourceCache _resourceCache = default!;
    [Dependency] private MarkupTagManager _tagManager = default!;
    [Dependency] private IDreamResourceManager _dreamResourceManager = default!;
    [Dependency] private readonly IResourceManagerInternal _resourceManager = default!;

    private const float Scale = 1f;

    /// Fallback size in points, used until the map control reports its own font-size.
    private const int FallbackFontSize = 8;

    private static readonly ResPath DefaultFontPath = new("/Fonts/NotoSans-Regular.ttf");

    /// <summary>
    /// font-family name to the loaded font, or null while a lookup is outstanding or
    /// after one failed. SS13 ships its map fonts as DM resources
    /// (interface/fonts/Grand9K_Pixel.ttf and friends) and refers to them by family
    /// name, so the name has to be resolved back to a resource before it can be drawn.
    /// </summary>
    private readonly Dictionary<string, FontResource?> _fontFamilies = new(StringComparer.OrdinalIgnoreCase);

    private readonly HashSet<string> _fontFamiliesRequested = new(StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Built fonts by family/size. Every span asks for a font and word-wrap walks the
    /// message twice more, so building a VectorFont per lookup meant several allocations
    /// per maptext per frame. Only fully-resolved families are cached; a family whose
    /// lookup is still outstanding must not have its fallback stick.
    /// </summary>
    private readonly Dictionary<(string? Family, int Size), Font> _fontCache = new();

    /// <summary>
    /// Class name to its declaration block, from the map control's `style` param. SS13
    /// keeps nearly all of its maptext styling there rather than inline: MAPTEXT() emits
    /// only &lt;span class='maptext'&gt;, and runechat adds `center` plus a size class. With
    /// no stylesheet the common case draws in the fallback face, left-aligned.
    /// </summary>
    private readonly Dictionary<string, string> _classRules = new(StringComparer.OrdinalIgnoreCase);

    private string _styleSheetSource = string.Empty;

    /// The map control's own font-family/font-size, which all maptext inherits.
    /// The size is in points, the unit both BYOND and Robust's font sizing take.
    private string? _mapFontFamily;
    private int _mapFontSize = FallbackFontSize;

    private readonly Color _defaultColor = Color.White;

    /// The face maptext falls back to: the map control's own font, not NotoSans.
    private Font DefaultFont => GetFont(_mapFontFamily, _mapFontSize);

    /// <summary>
    /// Adopts the map control's font and stylesheet. Both are skin properties rather
    /// than anything the game sends per-atom, so they are pushed in whenever the
    /// interface (re)loads.
    /// </summary>
    public void SetMapStyle(string styleSheet, string fontFamily, int fontSizePoints) {
        if (!string.Equals(styleSheet, _styleSheetSource, StringComparison.Ordinal)) {
            _styleSheetSource = styleSheet;
            ParseStyleSheet(styleSheet);
        }

        var family = string.IsNullOrWhiteSpace(fontFamily) ? null : fontFamily.Trim().Trim('\'', '"').Trim();
        var size = fontSizePoints > 0 ? fontSizePoints : FallbackFontSize;
        if (family == _mapFontFamily && size == _mapFontSize)
            return;

        _mapFontFamily = family;
        _mapFontSize = size;
        _fontCache.Clear();
    }

    /// <summary>
    /// Pulls bare class selectors out of a skin stylesheet. Anything else - element
    /// selectors like `img.icon`, descendant selectors - has no counterpart in a maptext
    /// span, so it is skipped rather than half-applied.
    /// </summary>
    private void ParseStyleSheet(string css) {
        _classRules.Clear();

        var i = 0;
        while (i < css.Length) {
            var open = css.IndexOf('{', i);
            if (open < 0)
                break;

            var close = css.IndexOf('}', open + 1);
            if (close < 0)
                break;

            var body = css[(open + 1)..close];
            foreach (var selector in css[i..open].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)) {
                if (selector.Length < 2 || selector[0] != '.')
                    continue;

                var name = selector[1..];
                if (name.AsSpan().IndexOfAny(" 	.#:>[".AsSpan()) >= 0)
                    continue;

                // Later rules for the same class append rather than replace, so the last
                // declaration of a property wins the way a real cascade would resolve it.
                _classRules[name] = _classRules.TryGetValue(name, out var existing)
                    ? existing + ";" + body
                    : body;
            }

            i = close + 1;
        }
    }

    /// <summary>
    /// The declaration blocks that apply to a node, in cascade order: each of its
    /// classes, then its inline style, so `style` overrides `class`.
    /// </summary>
    private IEnumerable<string> EnumerateDeclarations(MarkupNode node) {
        if (node.Attributes.TryGetValue("class", out var classParameter) &&
            classParameter.StringValue is { } classes) {
            foreach (var name in classes.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)) {
                if (_classRules.TryGetValue(name, out var body))
                    yield return body;
            }
        }

        if (node.Attributes.TryGetValue("style", out var styleParameter) &&
            styleParameter.StringValue is { } style)
            yield return style;
    }

    /// <summary>
    /// Maptext sizes are carried in points, because that is what BYOND and Robust both
    /// take: FontManager hands FreeType the size as a point value against a 96 DPI base,
    /// so a point is 4/3 of a pixel at either end and no conversion belongs in between.
    ///
    /// Getting this right is not cosmetic. SS13's map fonts are pixel fonts drawn at one
    /// exact pixel size and declared at the matching point size - Grand9K Pixel at 6pt
    /// rasterises to 8 pixels per em, which reproduces its shipped metrics exactly
    /// (advance 5 for 'e', 6 for 'M', 2 for 'i', 12 for a line). Rasterise it a size off
    /// and every glyph lands between pixels, which is what makes maptext look blurry.
    /// </summary>
    private static int PixelsToPoints(float pixels) => Math.Max(1, (int)MathF.Round(pixels * 0.75f));

    private static ISawmill Sawmill => Logger.GetSawmill("opendream.maptext");

    private readonly record struct TextOutline(Color Color, int Size);

    private sealed class MapTextContext {
        public readonly MarkupDrawingContext Drawing = new();
        public readonly Stack<TextOutline?> Outline = new();
        /// Inherited font-family, so a nested span that only sets font-size keeps the face.
        public readonly Stack<string?> Family = new();
        /// CSS line-height multiplier. SS13's pixel fonts declare their own (TinyUnicode
        /// 0.75, Spess Font 1.4) because the faces carry more leading than the design
        /// wants, so ignoring it spaces multi-line maptext wrongly.
        public readonly Stack<float> LineHeight = new();
        /// Whether the run is underlined, from <u> or text-decoration.
        public readonly Stack<bool> Underline = new();
    }

    private enum TextAlignment {
        Left,
        Center,
        Right
    }

    /// <summary>
    /// The size maptext would draw at, wrapped at <paramref name="maxWidth"/> (0 for no
    /// wrapping). This is what client.MeasureText() reports, and SS13 sizes every
    /// runechat box from it, so it has to agree with what RenderToTarget then draws.
    /// </summary>
    public Vector2i Measure(string maptext, int maxWidth) {
        var message = new FormattedMessage();
        HtmlParser.Parse(StringFormatDecoder.RemoveFormatting(maptext), message);

        var (height, lineBreaks) = ProcessWordWrap(message, maxWidth > 0 ? maxWidth : float.MaxValue);

        var width = 0f;
        foreach (var lineWidth in GetLineWidths(message, lineBreaks))
            width = MathF.Max(width, lineWidth);

        return new Vector2i((int)MathF.Ceiling(width), height);
    }

    // TODO: This is probably unoptimal and could cache a lot of things between frames
    public void RenderToTarget(DrawingHandleWorld handle, IRenderTexture texture, string maptext) {
        handle.RenderInRenderTarget(texture, () => {
            handle.SetTransform(DreamViewOverlay.CreateRenderTargetFlipMatrix(texture.Size, Vector2.Zero));

            var message = new FormattedMessage();
            HtmlParser.Parse(StringFormatDecoder.RemoveFormatting(maptext), message);

            var (height, lineBreaks) = ProcessWordWrap(message, texture.Size.X);
            var alignment = GetTextAlignment(message);
            var lineWidths = GetLineWidths(message, lineBreaks);
            var context = CreateContext();

            var currentLine = 0;
            // Y is only settled once the first span has been read, since the line height
            // is the drawing font's, not the fallback face's.
            var baseLine = new Vector2(GetAlignedX(texture.Size.X, lineWidths, currentLine, alignment), 0);
            var placedFirstLine = false;
            var lineBreakIndex = 0;
            var globalBreakCounter = 0;

            foreach (var node in message) {
                var text = ProcessNode(node, context);
                if (!context.Drawing.Color.TryPeek(out var color))
                    color = _defaultColor;
                if (!context.Drawing.Font.TryPeek(out var font))
                    font = DefaultFont;
                context.Outline.TryPeek(out var outline);
                context.Underline.TryPeek(out var underline);
                var lineHeight = LineHeightOf(font, context);

                foreach (var rune in text.EnumerateRunes()) {
                    if (!placedFirstLine) {
                        // The baseline sits a descent above the bottom of its line box.
                        // Without that the whole block hangs a descent too low and the
                        // target edge shears the tail off every g, p and y.
                        baseLine.Y = height - lineHeight + font.GetDescent(Scale);
                        placedFirstLine = true;
                    }

                    if (lineBreakIndex < lineBreaks.Count && lineBreaks[lineBreakIndex] == globalBreakCounter) {
                        currentLine += 1;
                        baseLine = new(GetAlignedX(texture.Size.X, lineWidths, currentLine, alignment), baseLine.Y - lineHeight);
                        lineBreakIndex += 1;
                    }

                    var metric = font.GetCharMetrics(rune, Scale);
                    Vector2 mod = new Vector2(0);
                    if (metric.HasValue)
                        mod.Y += metric.Value.BearingY - (metric.Value.Height - metric.Value.BearingY);

                    if (outline is { } textOutline) {
                        for (var y = -textOutline.Size; y <= textOutline.Size; y++) {
                            for (var x = -textOutline.Size; x <= textOutline.Size; x++) {
                                if (x == 0 && y == 0)
                                    continue;

                                font.DrawChar(handle, rune, baseLine + mod + new Vector2(x, y), Scale, textOutline.Color);
                            }
                        }
                    }

                    var advance = font.DrawChar(handle, rune, baseLine + mod, Scale, color);

                    if (underline) {
                        // Drawn per glyph so the rule runs unbroken through spaces, and
                        // sized off the face so it stays proportional at any font-size.
                        var thickness = MathF.Max(1f, MathF.Round(font.GetLineHeight(Scale) / 12f));
                        var top = baseLine.Y - MathF.Max(1f, MathF.Round(font.GetDescent(Scale) / 2f));
                        handle.DrawRect(new Box2(baseLine.X, top - thickness, baseLine.X + advance, top), color);
                    }

                    baseLine.X += advance;

                    globalBreakCounter += 1;
                }
            }
        // Clear to the premultiplied identity, not Color.Transparent - that is WHITE
        // with zero alpha, and this target is composited as a premultiplied source,
        // where a texel contributes its colour regardless of alpha.
        }, Color.Black.WithAlpha(0));
    }

    private static float GetAlignedX(float width, IReadOnlyList<float> lineWidths, int line, TextAlignment alignment) {
        if (alignment == TextAlignment.Left || line >= lineWidths.Count)
            return 0;

        return alignment switch {
            TextAlignment.Center => MathF.Max(0, (width - lineWidths[line]) / 2),
            TextAlignment.Right => MathF.Max(0, width - lineWidths[line]),
            _ => 0
        };
    }

    private TextAlignment GetTextAlignment(FormattedMessage message) {
        var alignment = TextAlignment.Left;

        foreach (var node in message) {
            if (node.Attributes.TryGetValue("align", out var alignParameter) &&
                alignParameter.StringValue is { } align)
                alignment = ParseAlignment(align);

            // Runechat centres itself with `class='center'`, so a stylesheet lookup is
            // the only way to find the alignment of the most common maptext there is.
            foreach (var declarations in EnumerateDeclarations(node)) {
                foreach (var declaration in declarations.Split(';', StringSplitOptions.RemoveEmptyEntries)) {
                    var parts = declaration.Split(':', 2, StringSplitOptions.TrimEntries);
                    if (parts.Length == 2 && parts[0].Equals("text-align", StringComparison.OrdinalIgnoreCase))
                        alignment = ParseAlignment(parts[1]);
                }
            }
        }

        return alignment;
    }

    private static TextAlignment ParseAlignment(string value) {
        return value.Trim().ToLowerInvariant() switch {
            "center" => TextAlignment.Center,
            "right" => TextAlignment.Right,
            _ => TextAlignment.Left
        };
    }

    private List<float> GetLineWidths(FormattedMessage message, IReadOnlyList<int> lineBreaks) {
        var context = CreateContext();

        var result = new List<float> {0};
        var lineBreakIndex = 0;
        var globalBreakCounter = 0;

        foreach (var node in message) {
            var text = ProcessNode(node, context);
            if (!context.Drawing.Font.TryPeek(out var font))
                font = DefaultFont;

            foreach (var rune in text.EnumerateRunes()) {
                if (lineBreakIndex < lineBreaks.Count && lineBreaks[lineBreakIndex] == globalBreakCounter) {
                    result.Add(0);
                    lineBreakIndex += 1;
                }

                if (font.TryGetCharMetrics(rune, Scale, out var metric))
                    result[^1] += metric.Advance;

                globalBreakCounter += 1;
            }
        }

        return result;
    }

    private MapTextContext CreateContext() {
        var context = new MapTextContext();
        context.Drawing.Color.Push(_defaultColor);
        context.Family.Push(null);
        context.Drawing.Font.Push(DefaultFont);
        context.Outline.Push(null);
        context.LineHeight.Push(1f);
        context.Underline.Push(false);
        return context;
    }

    private string ProcessNode(MarkupNode node, MapTextContext context) {
        // If a nodes name is null it's a text node.
        if (node.Name == null)
            return node.Value.StringValue ?? "";

        // <u> is the tag SS13 reaches for when a clickable maptext button is hovered,
        // so it has to nest and inherit like any other styled element rather than being
        // dropped as an unknown tag.
        if (node.Name is "span" or "div" or "u") {
            if (!node.Closing) {
                PushStyledContext(node, context, forceUnderline: node.Name == "u");
                return "";
            }

            context.Drawing.Font.Pop();
            context.Family.Pop();
            context.Drawing.Color.Pop();
            context.Outline.Pop();
            context.LineHeight.Pop();
            context.Underline.Pop();
            return "";
        }

        //Skip the node if there is no markup tag for it.
        if (!_tagManager.TryGetMarkupTagHandler(node.Name, null, out var tag))
            return "";

        if (!node.Closing) {
            tag.PushDrawContext(node, context.Drawing);
            return tag.TextBefore(node);
        }

        tag.PopDrawContext(node, context.Drawing);
        return tag.TextAfter(node);
    }

    private void PushStyledContext(MarkupNode node, MapTextContext context, bool forceUnderline = false) {
        var color = context.Drawing.Color.Peek();
        var font = context.Drawing.Font.Peek();
        var outline = context.Outline.Peek();

        // Size and family are resolved together: either one alone still has to produce
        // a whole font, and both inherit from the enclosing span when unset.
        var family = context.Family.Peek();
        var size = font is VectorFont inherited ? inherited.Size : _mapFontSize;
        var lineHeight = context.LineHeight.Peek();
        var underline = context.Underline.Peek() || forceUnderline;
        var styled = false;

        foreach (var declarations in EnumerateDeclarations(node)) {
            foreach (var declaration in declarations.Split(';', StringSplitOptions.RemoveEmptyEntries)) {
                var parts = declaration.Split(':', 2, StringSplitOptions.TrimEntries);
                if (parts.Length != 2)
                    continue;

                switch (parts[0].ToLowerInvariant()) {
                    case "color":
                        color = ParseColor(parts[1]) ?? color;
                        break;
                    case "font-size":
                        size = ParseFontSize(parts[1]) ?? size;
                        styled = true;
                        break;
                    case "font-family":
                        family = ParseFontFamily(parts[1]) ?? family;
                        styled = true;
                        break;
                    case "line-height":
                        lineHeight = ParseLineHeight(parts[1]) ?? lineHeight;
                        break;
                    case "text-decoration":
                    case "text-decoration-line":
                        underline = parts[1].Contains("underline", StringComparison.OrdinalIgnoreCase);
                        break;
                    case "-dm-text-outline":
                        outline = ParseTextOutline(parts[1]) ?? outline;
                        break;
                }
            }
        }

        if (styled)
            font = GetFont(family, size);

        context.Family.Push(family);
        context.Drawing.Font.Push(font);
        context.Drawing.Color.Push(color);
        context.Outline.Push(outline);
        context.LineHeight.Push(lineHeight);
        context.Underline.Push(underline);
    }

    /// The height of a line drawn by a span: its font's leading, scaled by its CSS multiplier.
    private static float LineHeightOf(Font font, MapTextContext context) {
        var multiplier = context.LineHeight.TryPeek(out var m) && m > 0 ? m : 1f;
        return font.GetLineHeight(Scale) * multiplier;
    }

    /// <summary>
    /// Builds a font for a family/size pair, falling back to the default face while a
    /// family is still being fetched (or if it has no matching resource).
    /// </summary>
    private Font GetFont(string? family, int size) {
        size = Math.Max(1, size);
        // An unstyled span inherits the map control's own font-family, the way BYOND
        // resolves it, rather than dropping to the engine's built-in face.
        family ??= _mapFontFamily;

        if (_fontCache.TryGetValue((family, size), out var cached))
            return cached;

        FontResource? resource = null;
        var resolved = family == null;
        if (family != null) {
            if (_fontFamilies.TryGetValue(family, out resource))
                resolved = true;
            else
                RequestFontFamily(family);
        }

        var font = new VectorFont(resource ?? _resourceCache.GetResource<FontResource>(DefaultFontPath), size);

        // Only cache a settled answer. Caching the fallback while a lookup is still in
        // flight would pin every maptext to the wrong face for the rest of the session.
        if (resolved)
            _fontCache[(family, size)] = font;

        return font;
    }

    /// <summary>
    /// Resolves a family name to a DM font resource. BYOND registers embedded fonts by
    /// the family name they declare, which we cannot read back here, so the name is
    /// mapped to candidate resource paths instead - "Spess Font" ships as SpessFont.ttf
    /// and "Grand9K Pixel" as Grand9K_Pixel.ttf, hence both the stripped and the
    /// underscored spellings.
    /// </summary>
    private void RequestFontFamily(string family) {
        if (!_fontFamiliesRequested.Add(family))
            return; // Already looking, or already failed

        var names = new List<string>();
        void AddName(string name) {
            if (!names.Contains(name))
                names.Add(name);
        }

        AddName(family);
        AddName(family.Replace(" ", "_"));
        AddName(family.Replace(" ", ""));

        var candidates = new List<string>();
        foreach (var dir in new[] { "interface/fonts/", "fonts/", "" }) {
            foreach (var name in names) {
                foreach (var ext in new[] { ".ttf", ".otf" })
                    candidates.Add(dir + name + ext);
            }
        }

        TryCandidate(family, candidates, 0);
    }

    private void TryCandidate(string family, List<string> candidates, int index) {
        if (index >= candidates.Count) {
            _fontFamilies[family] = null; // Nothing matched; stay on the default face
            Sawmill.Debug($"No font resource found for maptext font-family \"{family}\"");
            return;
        }

        var path = candidates[index];
        _dreamResourceManager.LookupResourceAsync(path,
            resourceId => _dreamResourceManager.LoadResourceAsync<DreamResource>(resourceId, resource => {
                try {
                    // FontResource only ever reads from a content root, so the DM
                    // resource's bytes are mounted into the VFS rather than written to
                    // the download cache, which lives outside it.
                    var mountPath = new ResPath($"/OpenDream/MapFonts/{SanitizeFileName(family)}.ttf");
                    _resourceManager.MountStreamAt(new MemoryStream(resource.CopyData()), mountPath);
                    _fontFamilies[family] = _resourceCache.GetResource<FontResource>(mountPath);
                    // A family resolving mid-session invalidates every fallback font
                    // handed out while the lookup was in flight.
                    _fontCache.Clear();
                } catch (Exception e) {
                    _fontFamilies[family] = null;
                    Sawmill.Warning($"Failed to load maptext font \"{family}\" from {path}: {e.Message}");
                }
            }),
            () => TryCandidate(family, candidates, index + 1));
    }

    private static string SanitizeFileName(string name) {
        var buffer = new char[name.Length];
        for (var i = 0; i < name.Length; i++)
            buffer[i] = char.IsLetterOrDigit(name[i]) ? name[i] : '_';

        return new string(buffer);
    }

    private static Color? ParseColor(string value) {
        value = value.Trim();
        if (Color.TryFromName(value, out var color))
            return color;

        // RobustToolbox v288 changed TryFromHex to the bool/out-param form.
        return Color.TryFromHex(value, out var hexColor) ? hexColor : null;
    }

    /// <summary>
    /// font-family takes a comma-separated list of names, each optionally quoted.
    /// Only the first is used - there is no fallback chain to walk.
    /// </summary>
    private static string? ParseFontFamily(string value) {
        var first = value.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (first.Length == 0)
            return null;

        var name = first[0].Trim().Trim('\'', '"').Trim();
        return string.IsNullOrEmpty(name) ? null : name;
    }

    private static int? ParseFontSize(string value) {
        value = value.Trim().ToLowerInvariant();
        var isPixels = value.EndsWith("px");
        if (isPixels || value.EndsWith("pt"))
            value = value[..^2];

        if (!float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var result))
            return null;

        // A bare number is points, same as the skin's own font-size param.
        return isPixels ? PixelsToPoints(result) : Math.Max(1, (int)MathF.Round(result));
    }

    /// <summary>
    /// line-height as a plain multiplier. A length is resolved against the size it was
    /// declared alongside, which is all SS13 ever uses it for.
    /// </summary>
    private static float? ParseLineHeight(string value) {
        value = value.Trim().ToLowerInvariant();
        if (value is "normal" or "")
            return 1f;

        if (value.EndsWith("%"))
            return float.TryParse(value[..^1], NumberStyles.Float, CultureInfo.InvariantCulture, out var percent)
                ? percent / 100f
                : null;

        if (value.EndsWith("px") || value.EndsWith("pt"))
            value = value[..^2];

        return float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var result) && result > 0
            ? result
            : null;
    }

    private static TextOutline? ParseTextOutline(string value) {
        var parts = value.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 0)
            return null;

        var sizePart = parts[0].ToLowerInvariant();
        if (sizePart.EndsWith("px"))
            sizePart = sizePart[..^2];

        if (!int.TryParse(sizePart, NumberStyles.Integer, CultureInfo.InvariantCulture, out var size) || size <= 0)
            return null;

        var color = parts.Length > 1
            ? ParseColor(string.Join(' ', parts[1..])) ?? Color.Black
            : Color.Black;

        return new(color, size);
    }

    private (int, List<int>) ProcessWordWrap(FormattedMessage message, float maxSizeX) {
        // This method is gonna suck due to complexity.
        // Bear with me here.
        // I am so deeply sorry for the person adding stuff to this in the future.

        var lineBreaks = new List<int>();
        // The first line's height is whichever span actually draws it, so it is
        // discovered rather than assumed; subsequent lines are added as breaks land.
        float? firstLineHeight = null;
        var height = 0f;

        int? breakLine;
        var wordWrap = new WordWrap(maxSizeX);
        var context = CreateContext();

        // Go over every node.
        // Nodes can change the markup drawing context and return additional text.
        // It's also possible for nodes to return inline controls. They get treated as one large rune.
        foreach (var node in message) {
            var text = ProcessNode(node, context);

            if (!context.Drawing.Font.TryPeek(out var font))
                font = DefaultFont;

            // And go over every character.
            foreach (var rune in text.EnumerateRunes()) {
                firstLineHeight ??= LineHeightOf(font, context);

                if (ProcessRune(rune, out breakLine))
                    continue;

                // Uh just skip unknown characters I guess.
                if (!font.TryGetCharMetrics(rune, Scale, out var metrics))
                    continue;

                if (ProcessMetric(metrics, out breakLine))
                    return (TotalHeight(), lineBreaks);
            }
        }

        breakLine = wordWrap.FinalizeText();
        CheckLineBreak(breakLine);
        return (TotalHeight(), lineBreaks);

        int TotalHeight() =>
            (int)MathF.Ceiling(height + (firstLineHeight ?? DefaultFont.GetLineHeight(Scale)));

        bool ProcessRune(Rune rune, out int? outBreakLine) {
            wordWrap.NextRune(rune, out breakLine, out var breakNewLine, out var skip);
            CheckLineBreak(breakLine);
            CheckLineBreak(breakNewLine);
            outBreakLine = breakLine;
            return skip;
        }

        bool ProcessMetric(CharMetrics metrics, out int? outBreakLine) {
            wordWrap.NextMetrics(metrics, out breakLine, out var abort);
            CheckLineBreak(breakLine);
            outBreakLine = breakLine;
            return abort;
        }

        void CheckLineBreak(int? line) {
            if (line is { } l) {
                lineBreaks.Add(l);
                if (!context.Drawing.Font.TryPeek(out var font))
                    font = DefaultFont;

                height += LineHeightOf(font, context);
            }
        }
    }

    /// <summary>
    /// Helper utility struct for word-wrapping calculations.
    /// </summary>
    private struct WordWrap {
        private readonly float _maxSizeX;

        private float _maxUsedWidth;
        private Rune _lastRune;

        // Index we put into the LineBreaks list when a line break should occur.
        private int _breakIndexCounter;

        private int _nextBreakIndexCounter;

        // If the CURRENT processing word ends up too long, this is the index to put a line break.
        private (int index, float lineSize)? _wordStartBreakIndex;

        // Word size in pixels.
        private int _wordSizePixels;

        // The horizontal position of the text cursor.
        private int _posX;

        // If a word is larger than maxSizeX, we split it.
        // We need to keep track of some data to split it into two words.
        private (int breakIndex, int wordSizePixels)? _forceSplitData = null;

        public WordWrap(float maxSizeX) {
            this = default;
            _maxSizeX = maxSizeX;
            _lastRune = new Rune('A');
        }

        public void NextRune(Rune rune, out int? breakLine, out int? breakNewLine, out bool skip) {
            _breakIndexCounter = _nextBreakIndexCounter;
            _nextBreakIndexCounter += rune.Utf16SequenceLength;

            breakLine = null;
            breakNewLine = null;
            skip = false;

            if (IsWordBoundary(_lastRune, rune) || rune == new Rune('\n')) {
                // Word boundary means we know where the word ends.
                if (_posX > _maxSizeX && _lastRune != new Rune(' ')) {
                    DebugTools.Assert(_wordStartBreakIndex.HasValue,
                        "wordStartBreakIndex can only be null if the word begins at a new line, in which case this branch shouldn't be reached as the word would be split due to being longer than a single line.");
                    //Ensure the assert had a chance to run and then just return
                    if (!_wordStartBreakIndex.HasValue)
                        return;

                    // We ran into a word boundary and the word is too big to fit the previous line.
                    // So we insert the line break BEFORE the last word.
                    breakLine = _wordStartBreakIndex!.Value.index;
                    _maxUsedWidth = Math.Max(_maxUsedWidth, _wordStartBreakIndex.Value.lineSize);
                    _posX = _wordSizePixels;
                }

                // Start a new word since we hit a word boundary.
                //wordSize = 0;
                _wordSizePixels = 0;
                _wordStartBreakIndex = (_breakIndexCounter, _posX);
                _forceSplitData = null;

                // Just manually handle newlines.
                if (rune == new Rune('\n')) {
                    _maxUsedWidth = Math.Max(_maxUsedWidth, _posX);
                    _posX = 0;
                    _wordStartBreakIndex = null;
                    skip = true;
                    breakNewLine = _breakIndexCounter;
                }
            }

            _lastRune = rune;
        }

        public void NextMetrics(in CharMetrics metrics, out int? breakLine, out bool abort) {
            abort = false;
            breakLine = null;

            // Increase word size and such with the current character.
            var oldWordSizePixels = _wordSizePixels;
            _wordSizePixels += metrics.Advance;
            // TODO: Theoretically, does it make sense to break after the glyph's width instead of its advance?
            //   It might result in some more tight packing but I doubt it'd be noticeable.
            //   Also definitely even more complex to implement.
            _posX += metrics.Advance;

            if (_posX <= _maxSizeX)
                return;

            _forceSplitData ??= (_breakIndexCounter, oldWordSizePixels);

            // Oh hey we get to break a word that doesn't fit on a single line.
            if (_wordSizePixels > _maxSizeX) {
                var (breakIndex, splitWordSize) = _forceSplitData.Value;
                if (splitWordSize == 0) {
                    // Happens if there's literally not enough space for a single character so uh...
                    // Yeah just don't.
                    abort = true;
                    return;
                }

                // Reset forceSplitData so that we can split again if necessary.
                _forceSplitData = null;
                breakLine = breakIndex;
                _wordSizePixels -= splitWordSize;
                _wordStartBreakIndex = null;
                _maxUsedWidth = Math.Max(_maxUsedWidth, _maxSizeX);
                _posX = _wordSizePixels;
            }
        }

        public int? FinalizeText() {
            // This needs to happen because word wrapping doesn't get checked for the last word.
            if (_posX > _maxSizeX) {
                if (!_wordStartBreakIndex.HasValue) {
                    throw new Exception(
                        "wordStartBreakIndex can only be null if the word begins at a new line," +
                        "in which case this branch shouldn't be reached as" +
                        "the word would be split due to being longer than a single line.");
                }

                return _wordStartBreakIndex.Value.index;
            } else {
                return null;
            }
        }

        [Pure]
        private static bool IsWordBoundary(Rune a, Rune b) {
            return a == new Rune(' ') || b == new Rune(' ') || a == new Rune('-') || b == new Rune('-');
        }
    }
}
