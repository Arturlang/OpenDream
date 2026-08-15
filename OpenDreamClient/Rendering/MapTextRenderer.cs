using System.Diagnostics.Contracts;
using System.Globalization;
using System.Text;
using OpenDreamClient.Interface.Html;
using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using Robust.Client.ResourceManagement;
using Robust.Client.UserInterface.RichText;
using Robust.Shared.Utility;

namespace OpenDreamClient.Rendering;

/// <summary>
/// Helper for rendering maptext to a render target.
/// Adapted from RobustToolbox's RichTextEntry.
/// </summary>
public sealed class MapTextRenderer(IResourceCache resourceCache, MarkupTagManager tagManager) {
    private const float Scale = 1f;

    private readonly VectorFont _defaultFont =
        new(resourceCache.GetResource<FontResource>("/Fonts/NotoSans-Regular.ttf"), 8);

    private readonly Color _defaultColor = Color.White;

    private readonly record struct TextOutline(Color Color, int Size);

    private sealed class MapTextContext {
        public readonly MarkupDrawingContext Drawing = new();
        public readonly Stack<TextOutline?> Outline = new();
    }

    private enum TextAlignment {
        Left,
        Center,
        Right
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
            var lineHeight = _defaultFont.GetLineHeight(Scale);
            var context = CreateContext();

            var currentLine = 0;
            var baseLine = new Vector2(GetAlignedX(texture.Size.X, lineWidths, currentLine, alignment), height - lineHeight);
            var lineBreakIndex = 0;
            var globalBreakCounter = 0;

            foreach (var node in message) {
                var text = ProcessNode(node, context);
                if (!context.Drawing.Color.TryPeek(out var color))
                    color = _defaultColor;
                if (!context.Drawing.Font.TryPeek(out var font))
                    font = _defaultFont;
                context.Outline.TryPeek(out var outline);

                foreach (var rune in text.EnumerateRunes()) {
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
                    baseLine.X += advance;

                    globalBreakCounter += 1;
                }
            }
        }, Color.Transparent);
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
        foreach (var node in message) {
            if (node.Attributes.TryGetValue("align", out var alignParameter) &&
                alignParameter.StringValue is { } align)
                return ParseAlignment(align);

            if (node.Attributes.TryGetValue("style", out var styleParameter) &&
                styleParameter.StringValue is { } style) {
                foreach (var declaration in style.Split(';', StringSplitOptions.RemoveEmptyEntries)) {
                    var parts = declaration.Split(':', 2, StringSplitOptions.TrimEntries);
                    if (parts.Length == 2 && parts[0].Equals("text-align", StringComparison.OrdinalIgnoreCase))
                        return ParseAlignment(parts[1]);
                }
            }
        }

        return TextAlignment.Left;
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
                font = _defaultFont;

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
        context.Drawing.Font.Push(_defaultFont);
        context.Outline.Push(null);
        return context;
    }

    private string ProcessNode(MarkupNode node, MapTextContext context) {
        // If a nodes name is null it's a text node.
        if (node.Name == null)
            return node.Value.StringValue ?? "";

        if (node.Name is "span" or "div") {
            if (!node.Closing) {
                PushStyledContext(node, context);
                return "";
            }

            context.Drawing.Font.Pop();
            context.Drawing.Color.Pop();
            context.Outline.Pop();
            return "";
        }

        //Skip the node if there is no markup tag for it.
        if (!tagManager.TryGetMarkupTagHandler(node.Name, null, out var tag))
            return "";

        if (!node.Closing) {
            tag.PushDrawContext(node, context.Drawing);
            return tag.TextBefore(node);
        }

        tag.PopDrawContext(node, context.Drawing);
        return tag.TextAfter(node);
    }

    private void PushStyledContext(MarkupNode node, MapTextContext context) {
        var color = context.Drawing.Color.Peek();
        var font = context.Drawing.Font.Peek();
        var outline = context.Outline.Peek();

        if (node.Attributes.TryGetValue("style", out var styleParameter) &&
            styleParameter.StringValue is { } style) {
            foreach (var declaration in style.Split(';', StringSplitOptions.RemoveEmptyEntries)) {
                var parts = declaration.Split(':', 2, StringSplitOptions.TrimEntries);
                if (parts.Length != 2)
                    continue;

                switch (parts[0].ToLowerInvariant()) {
                    case "color":
                        color = ParseColor(parts[1]) ?? color;
                        break;
                    case "font-size":
                        font = ParseFontSize(parts[1]) is { } fontSize
                            ? new VectorFont(resourceCache.GetResource<FontResource>("/Fonts/NotoSans-Regular.ttf"), fontSize)
                            : font;
                        break;
                    case "-dm-text-outline":
                        outline = ParseTextOutline(parts[1]) ?? outline;
                        break;
                }
            }
        }

        context.Drawing.Font.Push(font);
        context.Drawing.Color.Push(color);
        context.Outline.Push(outline);
    }

    private static Color? ParseColor(string value) {
        value = value.Trim();
        if (Color.TryFromName(value, out var color))
            return color;

        // RobustToolbox v288 changed TryFromHex to the bool/out-param form.
        return Color.TryFromHex(value, out var hexColor) ? hexColor : null;
    }

    private static int? ParseFontSize(string value) {
        value = value.Trim().ToLowerInvariant();
        if (value.EndsWith("pt") || value.EndsWith("px"))
            value = value[..^2];

        return float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var result)
            ? Math.Max(1, (int)MathF.Round(result))
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
        var height = _defaultFont.GetLineHeight(Scale);

        int? breakLine;
        var wordWrap = new WordWrap(maxSizeX);
        var context = CreateContext();

        // Go over every node.
        // Nodes can change the markup drawing context and return additional text.
        // It's also possible for nodes to return inline controls. They get treated as one large rune.
        foreach (var node in message) {
            var text = ProcessNode(node, context);

            if (!context.Drawing.Font.TryPeek(out var font))
                font = _defaultFont;

            // And go over every character.
            foreach (var rune in text.EnumerateRunes()) {
                if (ProcessRune(rune, out breakLine))
                    continue;

                // Uh just skip unknown characters I guess.
                if (!font.TryGetCharMetrics(rune, Scale, out var metrics))
                    continue;

                if (ProcessMetric(metrics, out breakLine))
                    return (height, lineBreaks);
            }
        }

        breakLine = wordWrap.FinalizeText();
        CheckLineBreak(breakLine);
        return (height, lineBreaks);

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
                    font = _defaultFont;

                height += font.GetLineHeight(Scale);
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
