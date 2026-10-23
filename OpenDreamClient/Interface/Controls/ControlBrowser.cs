using System.Globalization;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web;
using OpenDreamShared;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamClient.Resources;
using OpenDreamClient.Resources.ResourceTypes;
using OpenDreamShared.Dream;
using OpenDreamShared.Network.Messages;
using Robust.Client.Graphics;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Client.WebView;
using Robust.Shared.Asynchronous;
using Robust.Shared.Configuration;
using Robust.Shared.Console;
using Robust.Shared.ContentPack;
using Robust.Shared.Network;
using Robust.Shared.Utility;

namespace OpenDreamClient.Interface.Controls;

internal sealed partial class ControlBrowser : InterfaceControl {
    /// <summary>
    /// Reports uncaught script errors back to the client log.
    ///
    /// CEF's console output is not exposed through IWebViewControl, so a page that dies on a
    /// script error is otherwise completely silent - you only see the browser's own error text.
    /// This routes them through the byond:// interception that is already in place.
    /// </summary>
    private const string BrowserErrorShim = """
        <script>
        (function() {
            if (window.__opendreamErrorShim)
                return;

            window.__opendreamErrorShim = true;

            function report(kind, message, source, line) {
                try {
                    var text = kind + ": " + String(message);
                    if (source)
                        text += " (" + String(source) + (line ? ":" + String(line) : "") + ")";

                    // Fire-and-forget; the client cancels the navigation and logs the query.
                    var img = new Image();
                    img.src = "byond://odlog?text=" + encodeURIComponent(text);
                } catch (e) {
                    // Never let the reporter itself throw.
                }
            }

            window.addEventListener("error", function(event) {
                if (event && event.message)
                    report("script error", event.message, event.filename, event.lineno);
                else if (event && event.target && event.target.src)
                    report("resource error", "failed to load " + event.target.src);
            }, true);

            window.addEventListener("unhandledrejection", function(event) {
                report("unhandled rejection", event && event.reason ? event.reason : "unknown");
            });

            var originalConsoleError = window.console && window.console.error;
            if (originalConsoleError) {
                window.console.error = function() {
                    report("console.error", Array.prototype.join.call(arguments, " "));
                    return originalConsoleError.apply(window.console, arguments);
                };
            }

            // The page's message entrypoint gets assigned later (window.update = ...), and a
            // throw inside it is masked because the caller is an injected URL-less script.
            // Trapping the assignment lets us wrap the real function and report the actual
            // exception - name, message, stack and the offending input - from inside the page.
            (function() {
                var realUpdate;
                var wrappedUpdate = function() {
                    try {
                        return realUpdate.apply(this, arguments);
                    } catch (e) {
                        var input;
                        try { input = String(arguments[0]).slice(0, 400); } catch (e2) { input = "?"; }
                        report("update() threw",
                            String(e && e.name) + ": " + String(e && e.message) +
                            "\n  input: " + input +
                            "\n  stack: " + String(e && e.stack).slice(0, 1200));
                        throw e;
                    }
                };

                try {
                    Object.defineProperty(window, "update", {
                        configurable: true,
                        get: function() { return realUpdate && wrappedUpdate; },
                        set: function(fn) { realUpdate = fn; }
                    });
                } catch (e) {
                }
            })();
        })();
        </script>
        """;

    // Reports the page's load event, so a popup whose page never sets its own visibility can be shown
    private const string BrowserLoadShim = """
        <script>
        (function() {
            if (window.__opendreamLoadShim)
                return;
            window.__opendreamLoadShim = true;
            window.addEventListener("load", function() {
                (new Image()).src = "byond://odloaded";
            });
        })();
        </script>
        """;

    private const string BrowserStorageShim = """
        <script>
        (function() {
            if (window.__opendreamStorageShim)
                return;

            window.__opendreamStorageShim = true;

            function key(name) {
                return "opendream:byondstorage:" + String(name);
            }

            function notifyUpdated() {
                if (typeof Event === "function") {
                    document.dispatchEvent(new Event("byondstorageupdated"));
                    return;
                }

                var event = document.createEvent("Event");
                event.initEvent("byondstorageupdated", false, false);
                document.dispatchEvent(event);
            }

            window.hubStorage = {
                getItem: function(name) {
                    try {
                        return Promise.resolve(window.localStorage.getItem(key(name)));
                    } catch (err) {
                        return Promise.resolve(null);
                    }
                },
                setItem: function(name, value) {
                    try {
                        window.localStorage.setItem(key(name), String(value));
                    } finally {
                        notifyUpdated();
                    }

                    return Promise.resolve();
                },
                removeItem: function(name) {
                    try {
                        window.localStorage.removeItem(key(name));
                    } finally {
                        notifyUpdated();
                    }

                    return Promise.resolve();
                },
                clear: function() {
                    try {
                        var prefix = key("");
                        for (var i = window.localStorage.length - 1; i >= 0; i--) {
                            var storageKey = window.localStorage.key(i);
                            if (storageKey && storageKey.indexOf(prefix) === 0)
                                window.localStorage.removeItem(storageKey);
                        }
                    } finally {
                        notifyUpdated();
                    }

                    return Promise.resolve();
                }
            };

            notifyUpdated();
        })();
        </script>
        """;

    private const string BrowserGeometryShimTemplate = """
        <script>
        (function() {
            if (window.__opendreamGeometryShim)
                return;

            var geometry = { x: __OPENDREAM_GEOMETRY_X__, y: __OPENDREAM_GEOMETRY_Y__ };
            var screenDims = { w: __OPENDREAM_SCREEN_W__, h: __OPENDREAM_SCREEN_H__ };

            window.__opendreamGeometryShim = {
                set: function(x, y, w, h) {
                    geometry.x = Number(x) || 0;
                    geometry.y = Number(y) || 0;
                    if (Number(w) > 0)
                        screenDims.w = Number(w);
                    if (Number(h) > 0)
                        screenDims.h = Number(h);
                }
            };

            function defineWindowNumber(name, getter) {
                try {
                    Object.defineProperty(window, name, {
                        configurable: true,
                        get: getter
                    });
                } catch (err) {
                }
            }

            defineWindowNumber("screenLeft", function() { return geometry.x; });
            defineWindowNumber("screenTop", function() { return geometry.y; });
            defineWindowNumber("screenX", function() { return geometry.x; });
            defineWindowNumber("screenY", function() { return geometry.y; });

            try {
                Object.defineProperty(MouseEvent.prototype, "screenX", {
                    configurable: true,
                    get: function() { return geometry.x + this.clientX; }
                });
                Object.defineProperty(MouseEvent.prototype, "screenY", {
                    configurable: true,
                    get: function() { return geometry.y + this.clientY; }
                });
            } catch (err) {
            }

            // Under offscreen rendering, CEF reports the embedded control's dimensions as
            // the screen. TGUI clamps every window to screen.availWidth/Height, so a tiny
            // or zero "screen" shrinks each window it opens down to nothing.
            function defineScreenNumber(name, getter) {
                try {
                    Object.defineProperty(window.screen, name, {
                        configurable: true,
                        get: getter
                    });
                } catch (err) {
                }
            }

            defineScreenNumber("width", function() { return screenDims.w; });
            defineScreenNumber("height", function() { return screenDims.h; });
            defineScreenNumber("availWidth", function() { return screenDims.w; });
            defineScreenNumber("availHeight", function() { return screenDims.h; });
            defineScreenNumber("availLeft", function() { return 0; });
            defineScreenNumber("availTop", function() { return 0; });

            // Hand titlebar drags to the client instead of letting TGUI drag itself.
            // TGUI's JS drag derives positions from MouseEvent.screenX, which we fake as
            // injected-geometry + clientX - and the injection races the mouse events that
            // follow each window move, so the window oscillates while dragged. The client
            // moving the panel from real mouse input has no feedback loop at all.
            //
            // The client cannot see the button release itself (clicks consumed by UI
            // controls never reach the input manager's key state), so the page reports it.
            // During a native drag the window follows the cursor, keeping the cursor over
            // this page, so mouseup arrives here reliably.
            var odNativeDragging = false;

            function odDragBeacon(what) {
                (new Image()).src = "byond://oddrag?e=" + what;
            }

            function odEndNativeDrag() {
                if (!odNativeDragging)
                    return;

                odNativeDragging = false;
                odDragBeacon("end");
            }

            window.addEventListener("mousedown", function(ev) {
                if (!ev.target || !ev.target.closest)
                    return;

                // A stray mousedown while we think a drag is active means the release was
                // missed (e.g. it happened outside the game window) - recover first.
                odEndNativeDrag();

                var dragZone = ev.target.closest(".TitleBar__dragZone");
                var altDrag = ev.altKey && ev.target.closest(".Window__rest");
                if (!dragZone && !altDrag)
                    return;

                // Swallow every button here: TGUI's own drag handler doesn't filter by
                // button, and its screenX-based drag is the stuttery thing being replaced.
                ev.stopImmediatePropagation();
                ev.preventDefault();

                if (ev.button === 0) {
                    odNativeDragging = true;
                    odDragBeacon("start");
                }
            }, true);

            window.addEventListener("mouseup", function(ev) {
                if (ev.button === 0)
                    odEndNativeDrag();
            }, true);

            window.addEventListener("blur", odEndNativeDrag);

            var nativeControls = {};
            var nativeControlFrame;
            var originalWinset;
            var originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
            var lastMeasuredElement;
            var lastMeasuredElementTime = 0;
            var nativeControlMaintenanceTimer;
            window.__opendreamNativeControls = nativeControls;

            Element.prototype.getBoundingClientRect = function() {
                var rect = originalGetBoundingClientRect.apply(this, arguments);
                lastMeasuredElement = this;
                lastMeasuredElementTime = performance.now();
                return rect;
            };

            function parsePair(value, separator) {
                if (typeof value !== "string")
                    return null;

                var parts = value.split(separator);
                if (parts.length !== 2)
                    return null;

                return {
                    x: Number(parts[0]) || 0,
                    y: Number(parts[1]) || 0
                };
            }

            function updateOwnGeometry(id, params) {
                if (id !== Byond.windowId || !params || typeof params !== "object" || !params.pos)
                    return;

                var position = parsePair(params.pos, ",");
                if (!position)
                    return;

                window.__opendreamGeometryShim.set(position.x, position.y);
            }

            function copyParams(params) {
                var copy = {};
                for (var key in params) {
                    if (Object.prototype.hasOwnProperty.call(params, key))
                        copy[key] = params[key];
                }

                return copy;
            }

            function makeParamsKey(params) {
                return [
                    params.parent || "",
                    params.id || "",
                    params.type || "",
                    params.pos || "",
                    params.size || "",
                    params["opendream-clip-offset"] || "",
                    params["opendream-full-size"] || ""
                ].join("|");
            }

            function sendNativeControlWinset(id, params, entry) {
                if (entry) {
                    var key = makeParamsKey(params);
                    if (entry.lastSentKey === key)
                        return;

                    entry.lastSentKey = key;
                }

                originalWinset.call(Byond, id, params);
            }

            function observeNativeControlElement(entry, element) {
                if (entry.element === element)
                    return;

                if (entry.resizeObserver) {
                    entry.resizeObserver.disconnect();
                    entry.resizeObserver = null;
                }

                entry.element = element;
                if (window.ResizeObserver) {
                    entry.resizeObserver = new ResizeObserver(scheduleNativeControlUpdate);
                    entry.resizeObserver.observe(element);
                }
            }

            function hasNativeControls() {
                for (var id in nativeControls) {
                    if (Object.prototype.hasOwnProperty.call(nativeControls, id))
                        return true;
                }

                return false;
            }

            function ensureNativeControlMaintenance() {
                if (nativeControlMaintenanceTimer)
                    return;

                nativeControlMaintenanceTimer = setInterval(function() {
                    if (!hasNativeControls()) {
                        clearInterval(nativeControlMaintenanceTimer);
                        nativeControlMaintenanceTimer = null;
                        return;
                    }

                    scheduleNativeControlUpdate();
                }, 125);
            }

            function intersectRects(a, b) {
                var left = Math.max(a.left, b.left);
                var top = Math.max(a.top, b.top);
                var right = Math.min(a.right, b.right);
                var bottom = Math.min(a.bottom, b.bottom);

                return {
                    left: left,
                    top: top,
                    right: right,
                    bottom: bottom,
                    width: Math.max(0, right - left),
                    height: Math.max(0, bottom - top)
                };
            }

            function getVisibleRect(element, rect) {
                var visible = {
                    left: rect.left,
                    top: rect.top,
                    right: rect.right,
                    bottom: rect.bottom,
                    width: rect.right - rect.left,
                    height: rect.bottom - rect.top
                };

                for (var parent = element.parentElement; parent; parent = parent.parentElement) {
                    var style = window.getComputedStyle(parent);
                    var overflow = style.overflow + style.overflowX + style.overflowY;
                    if (overflow.indexOf("hidden") !== -1 ||
                            overflow.indexOf("auto") !== -1 ||
                            overflow.indexOf("scroll") !== -1 ||
                            overflow.indexOf("overlay") !== -1 ||
                            overflow.indexOf("clip") !== -1) {
                        visible = intersectRects(visible, originalGetBoundingClientRect.call(parent));
                    }
                }

                visible = intersectRects(visible, {
                    left: 0,
                    top: 0,
                    right: window.innerWidth,
                    bottom: window.innerHeight
                });

                return visible;
            }

            function findElementForNativeControl(params) {
                var position = parsePair(params.pos, ",");
                var size = parsePair(params.size, "x");
                if (!position || !size)
                    return null;

                var scale = window.devicePixelRatio || 1;
                var expectedLeft = position.x / scale;
                var expectedTop = position.y / scale;
                var expectedWidth = size.x / scale;
                var expectedHeight = size.y / scale;
                var best = null;
                var bestScore = 8;
                var elements = document.body ? document.body.getElementsByTagName("div") : [];

                for (var i = 0; i < elements.length; i++) {
                    var element = elements[i];
                    var rect = originalGetBoundingClientRect.call(element);
                    var width = rect.right - rect.left;
                    var height = rect.bottom - rect.top;
                    if (width <= 0 || height <= 0)
                        continue;

                    var score = Math.abs(rect.left - expectedLeft) +
                        Math.abs(rect.top - expectedTop) +
                        Math.abs(width - expectedWidth) +
                        Math.abs(height - expectedHeight);

                    if (score < bestScore) {
                        best = element;
                        bestScore = score;
                    }
                }

                return best;
            }

            function updateNativeControl(id, entry) {
                if (!originalWinset)
                    return;

                var element = entry.element;
                if (!element || !document.body || !document.body.contains(element)) {
                    element = findElementForNativeControl(entry.params);
                    if (element)
                        observeNativeControlElement(entry, element);
                }

                if (!element) {
                    sendNativeControlWinset(id, entry.params, entry);
                    return;
                }

                var scale = window.devicePixelRatio || 1;
                var rect = originalGetBoundingClientRect.call(element);
                var visible = getVisibleRect(element, rect);
                var params = copyParams(entry.params);

                if (visible.width <= 0 || visible.height <= 0) {
                    entry.lastRect = {
                        left: rect.left,
                        top: rect.top,
                        right: rect.right,
                        bottom: rect.bottom,
                        width: rect.right - rect.left,
                        height: rect.bottom - rect.top
                    };
                    entry.lastVisible = visible;
                    entry.lastSentParams = { parent: "" };
                    sendNativeControlWinset(id, { parent: "" }, entry);
                    return;
                }

                params.pos = Math.round(visible.left * scale) + "," + Math.round(visible.top * scale);
                params.size = Math.round(visible.width * scale) + "x" + Math.round(visible.height * scale);
                params["opendream-clip-offset"] = Math.round((visible.left - rect.left) * scale) + "," + Math.round((visible.top - rect.top) * scale);
                params["opendream-full-size"] = Math.round((rect.right - rect.left) * scale) + "x" + Math.round((rect.bottom - rect.top) * scale);

                entry.lastRect = {
                    left: rect.left,
                    top: rect.top,
                    right: rect.right,
                    bottom: rect.bottom,
                    width: rect.right - rect.left,
                    height: rect.bottom - rect.top
                };
                entry.lastVisible = visible;
                entry.lastSentParams = copyParams(params);
                entry.lastElementTag = element.tagName;
                entry.lastElementClass = element.className || "";

                sendNativeControlWinset(id, params, entry);
            }

            function removeNativeControl(id) {
                var entry = nativeControls[id];
                if (!entry) {
                    originalWinset.call(Byond, id, { parent: "" });
                    return;
                }

                requestAnimationFrame(function() {
                    var current = nativeControls[id];
                    var element = current && current.element;
                    if (element && document.body && document.body.contains(element)) {
                        updateNativeControl(id, current);
                        return;
                    }

                    if (current && current.resizeObserver)
                        current.resizeObserver.disconnect();

                    delete nativeControls[id];
                    originalWinset.call(Byond, id, { parent: "" });
                });
            }

            function scheduleNativeControlUpdate() {
                if (nativeControlFrame)
                    return;

                nativeControlFrame = requestAnimationFrame(function() {
                    nativeControlFrame = null;
                    updateNativeControls();
                });
            }

            function updateNativeControls() {
                for (var id in nativeControls) {
                    if (Object.prototype.hasOwnProperty.call(nativeControls, id))
                        updateNativeControl(id, nativeControls[id]);
                }
            }

            function updateNativeControlsForScroll() {
                scheduleNativeControlUpdate();
            }

            function installNativeControlWinsetHook() {
                if (!window.Byond || typeof Byond.winset !== "function") {
                    setTimeout(installNativeControlWinsetHook, 0);
                    return;
                }

                if (Byond.__opendreamNativeControlWinsetHook)
                    return;

                originalWinset = Byond.winset;
                Byond.__opendreamNativeControlWinsetHook = true;
                Byond.winset = function(id, params) {
                    updateOwnGeometry(id, params);

                    if (params && typeof params === "object" && params.pos && params.size) {
                        var entry = nativeControls[id] || {};
                        var measuredElement = performance.now() - lastMeasuredElementTime < 50
                            ? lastMeasuredElement
                            : null;
                        entry.params = copyParams(params);
                        var element = measuredElement || findElementForNativeControl(params) || entry.element;
                        if (element)
                            observeNativeControlElement(entry, element);
                        nativeControls[id] = entry;
                        ensureNativeControlMaintenance();
                        updateNativeControl(id, entry);
                        return;
                    }

                    if (params && typeof params === "object" && params.parent === "") {
                        removeNativeControl(id);
                        return;
                    }

                    return originalWinset.apply(this, arguments);
                };
            }

            installNativeControlWinsetHook();
            window.addEventListener("scroll", updateNativeControlsForScroll, true);
            window.addEventListener("resize", scheduleNativeControlUpdate);
        })();
        </script>
        """;

    private static readonly Dictionary<string, string> FileExtensionMimeTypes = new() {
        { "css", "text/css" },
        { "html", "text/html" },
        { "htm", "text/html" },
        { "png", "image/png" },
        { "svg", "image/svg+xml" },
        { "jpeg", "image/jpeg" },
        { "jpg", "image/jpeg" },
        { "js", "application/javascript" },
        { "json", "application/json" },
        { "ttf", "font/ttf" },
        { "woff2", "font/woff2" },
        { "txt", "text/plain" }
    };

    private const uint RefTypeMask = 0xFF000000;
    private const uint RefIdMask = 0x00FFFFFF;
    private const uint DreamResourceIconRefType = 0x0C000000;
    private const uint DreamResourceRefType = 0x27000000;

    [Dependency] private IClyde _clyde = default!;
    [Dependency] private ITaskManager _taskManager = default!;
    [Dependency] private IConfigurationManager _cfg = default!;
    [Dependency] private IResourceManager _resourceManager = default!;
    [Dependency] private IClientNetManager _netManager = default!;
    [Dependency] private IDreamResourceManager _dreamResource = default!;

    private readonly ISawmill _sawmill = Logger.GetSawmill("opendream.browser");

    private PanelContainer _panel = default!;
    private WebViewControl _webView = default!;
    private Vector2i _geometryOrigin;

    /// <summary>
    /// Whether a winget result can be spliced into a JS literal as-is.
    ///
    /// Not a parser (System.Text.Json is blocked by the content sandbox), and it doesn't
    /// need one: structured values here only ever come from our own IDMFProperty.AsJson()
    /// implementations, so classifying the first token is enough to reject the raw DMF
    /// forms ("400,120", "640x480", "none") that are not JSON.
    /// </summary>
    private static bool LooksLikeJson(string value) {
        if (string.IsNullOrEmpty(value))
            return false;

        switch (value[0]) {
            case '{':
            case '[':
            case '"':
                return true;
        }

        if (value is "true" or "false" or "null")
            return true;

        // A bare number is JSON; "400,120" or "3x4" is not.
        var seenDot = false;
        for (var i = value[0] == '-' ? 1 : 0; i < value.Length; i++) {
            var c = value[i];
            if (c == '.' && !seenDot) {
                seenDot = true;
                continue;
            }

            if (c is < '0' or > '9')
                return false;
        }

        return true;
    }

    /// <summary>
    /// Surfaces a script error reported by <see cref="BrowserErrorShim"/>.
    /// </summary>
    /// <param name="query">The query portion of byond://odlog?text=...</param>
    private void HandleBrowserLog(string query) {
        var text = HttpUtility.ParseQueryString(query).Get("text");
        if (string.IsNullOrEmpty(text))
            return;

        _sawmill.Error($"[{ControlDescriptor.Id.Value}] {text}");
    }

    private Stream AddBrowserShims(Stream stream) {
        using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true, leaveOpen: false);
        var html = reader.ReadToEnd();
        var skipStorageShim = _cfg.GetCVar(OpenDreamCVars.DisableBrowserStorageShim);
        if (!skipStorageShim)
            html = DisableRemoteTguiStorageCdn(html);

        if (html.Contains("window.__opendreamStorageShim", StringComparison.Ordinal) &&
            html.Contains("window.__opendreamGeometryShim", StringComparison.Ordinal) &&
            html.Contains("window.__opendreamErrorShim", StringComparison.Ordinal) &&
            html.Contains("window.__opendreamLoadShim", StringComparison.Ordinal))
            return new MemoryStream(Encoding.UTF8.GetBytes(html));

        var shims = string.Empty;
        // First, so it is installed before anything else on the page can throw.
        if (!html.Contains("window.__opendreamErrorShim", StringComparison.Ordinal))
            shims += BrowserErrorShim;
        if (!html.Contains("window.__opendreamLoadShim", StringComparison.Ordinal))
            shims += BrowserLoadShim;
        if (!skipStorageShim && !html.Contains("window.__opendreamStorageShim", StringComparison.Ordinal))
            shims += BrowserStorageShim;
        if (!_cfg.GetCVar(OpenDreamCVars.DisableBrowserGeometryShim) &&
            !html.Contains("window.__opendreamGeometryShim", StringComparison.Ordinal)) {
            var screenSize = GetScreenSize();

            shims += BrowserGeometryShimTemplate
                .Replace("__OPENDREAM_GEOMETRY_X__", _geometryOrigin.X.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
                .Replace("__OPENDREAM_GEOMETRY_Y__", _geometryOrigin.Y.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
                .Replace("__OPENDREAM_SCREEN_W__", screenSize.X.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
                .Replace("__OPENDREAM_SCREEN_H__", screenSize.Y.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal);
        }

        var insertIndex = html.IndexOf("<head>", StringComparison.OrdinalIgnoreCase);
        if (insertIndex >= 0) {
            insertIndex += "<head>".Length;
            html = html.Insert(insertIndex, shims);
        } else {
            html = shims + html;
        }

        return new MemoryStream(Encoding.UTF8.GetBytes(html));
    }

    private static string DisableRemoteTguiStorageCdn(string html) {
        const string StorageCdnMetaPrefix = "<meta id=\"tgui:storagecdn\" content=\"";

        var metaIndex = html.IndexOf(StorageCdnMetaPrefix, StringComparison.OrdinalIgnoreCase);
        if (metaIndex < 0)
            return html;

        var valueStart = metaIndex + StorageCdnMetaPrefix.Length;
        var valueEnd = html.IndexOf('"', valueStart);
        if (valueEnd < 0)
            return html;

        return html[..valueStart] + html[valueEnd..];
    }

    public ControlBrowser(ControlDescriptor controlDescriptor, ControlWindow window)
        : base(controlDescriptor, window) {
        IoCManager.InjectDependencies(this);
    }

    protected override Control CreateUIElement() {
        _panel = new PanelContainer {
            Children = {
                (_webView = new WebViewControl {AlwaysActive = true})
            }
        };

        _webView.AddResourceRequestHandler(RequestHandler);
        _webView.AddBeforeBrowseHandler(BeforeBrowseHandler);
        _webView.OnVisibilityChanged += (args) => {
            if (args.Visible) {
                OnShowEvent();
            } else {
                OnHideEvent();
            }
        };

        if(ControlDescriptor.IsVisible.Value)
            OnShowEvent();
        else
            OnHideEvent();

        return _panel;
    }

    protected override void UpdateElementDescriptor() {
        base.UpdateElementDescriptor();

        _panel.PanelOverride = new StyleBoxFlat(Color.White); // Always white background
    }

    /// <summary>
    /// Raised when the page requests a native window drag (mousedown on a TGUI titlebar).
    /// </summary>
    public event Action? NativeDragStarted;

    /// <summary>
    /// Raised when the page reports the drag's button release.
    /// </summary>
    public event Action? NativeDragEnded;

    /// <summary>
    /// Raised when the page's load event fires.
    /// </summary>
    public event Action? PageLoaded;

    private void HandleNativeDragBeacon(string query) {
        var what = HttpUtility.ParseQueryString(query).Get("e");

        // Beacons arrive on a CEF thread, where Robust's thread-local IoC (and most of
        // Robust) is off-limits - marshal to the game thread before anyone acts on this.
        _taskManager.RunOnMainThread(() => {
            if (what == "start")
                NativeDragStarted?.Invoke();
            else
                NativeDragEnded?.Invoke();
        });
    }

    private static int _injectionSequence;

    /// <summary>
    /// Central funnel for every script we inject into this browser.
    ///
    /// A syntax error in an injected script cannot be caught by anything inside that script
    /// (the try/catch wrapper never compiles), and the browser masks it as "Script error."
    /// at :0. Sequence-logging each injection lets a masked error in the log be correlated
    /// with the exact script that preceded it.
    /// </summary>
    private void InjectScript(string script, string context) {
        if (_webView.Disposed)
            return;

        var sequence = Interlocked.Increment(ref _injectionSequence);
        _sawmill.Debug($"inject #{sequence} ({context}) [{ControlDescriptor.Id.Value}]: {script[..Math.Min(script.Length, 400)]}");

        try {
            _webView.ExecuteJavaScript(script);
        } catch (Exception e) when (e.GetType().Name == "ObjectDisposedException") {
            // The window can close while injected scripts are still queued.
        } catch (InvalidOperationException e) {
            _sawmill.Debug($"Ignoring injected script ({context}) to an unavailable web view: {e.Message}");
        }
    }

    public override void Output(string value, string? jsFunction) {
        if (jsFunction == null) return;

        InjectScript(BrowserBridgeScript.FormatOutputCall(jsFunction, value), "output");
    }

    public void SetFileSource(ResPath? filepath) {
        if (filepath != null) {
            // hostname must be the localhost IP for TGUI to work properly
            _webView.Url = "http://127.0.0.1/" + filepath;
        } else {
            _webView.Url = "about:blank";
        }
    }

    public void ShutdownBrowser() {
        _webView.Url = "about:blank";
        _webView.AlwaysActive = false;
    }

    public void SetGeometryOrigin(Vector2i position) {
        _geometryOrigin = position;
        var screenSize = GetScreenSize();

        InjectScript("window.__opendreamGeometryShim && window.__opendreamGeometryShim.set(" +
                     $"{position.X.ToString(CultureInfo.InvariantCulture)}, {position.Y.ToString(CultureInfo.InvariantCulture)}, " +
                     $"{screenSize.X.ToString(CultureInfo.InvariantCulture)}, {screenSize.Y.ToString(CultureInfo.InvariantCulture)});", "geometry");
    }

    /// <summary>
    /// The size reported as window.screen inside offscreen-rendered pages.
    ///
    /// TGUI "windows" are panels inside the game window, and TGUI both clamps and centers
    /// them against screen.availWidth/Height - so the game window's client area is the
    /// correct "screen". Reporting the monitor here centered popups against the desktop,
    /// shoving them off-center whenever the client wasn't fullscreen.
    /// </summary>
    private Vector2i GetScreenSize() {
        var mainWindow = _clyde.MainWindow.Size;
        if (mainWindow.X > 0 && mainWindow.Y > 0)
            return mainWindow;

        // No window yet (headless?) - anything positive beats a zero-sized "screen".
        return new Vector2i(1920, 1080);
    }

    private void BeforeBrowseHandler(IBeforeBrowseContext context) {
        // An exception in here will freeze up / crash CEF, so catch any
        try {
            if (string.IsNullOrEmpty(_webView.Url))
                return;

            Uri oldUri = new Uri(_webView.Url);
            Uri newUri = new Uri(context.Url);

            bool isLocalTopicNavigation = newUri is { Scheme: "http", Host: "127.0.0.1" } &&
                newUri.Query != string.Empty &&
                (newUri.AbsolutePath == oldUri.AbsolutePath || newUri.AbsolutePath == "/");

            if (newUri.Scheme == "byond" || isLocalTopicNavigation) {
                context.DoCancel();

                switch (newUri.Host) {
                    case "winset":
                        HandleEmbeddedWinset(newUri.Query);
                        return;
                    case "winget":
                        HandleEmbeddedWinget(newUri.Query);
                        return;
                    case "odlog":
                        HandleBrowserLog(newUri.Query);
                        return;
                    case "oddrag":
                        HandleNativeDragBeacon(newUri.Query);
                        return;
                    default: {
                        var msg = new MsgTopic { Query = newUri.Query };
                        _netManager.ClientSendMessage(msg);
                        break;
                    }
                }
            }
        } catch (Exception e) {
            _sawmill.Error($"Exception in BeforeBrowseHandler: {e}");
        }
    }

    private void RequestHandler(IRequestHandlerContext context) {
        // An exception in here will crash RT (and not log it because it's uncaught)
        try {
            Uri newUri = new Uri(context.Url);

            // The shims report through an <img> src, which arrives here as a resource
            // request rather than as a navigation, so BeforeBrowseHandler never sees it.
            if (newUri.Scheme == "byond") {
                switch (newUri.Host) {
                    case "odlog":
                        HandleBrowserLog(newUri.Query);
                        context.DoCancel();
                        return;
                    case "oddrag":
                        HandleNativeDragBeacon(newUri.Query);
                        context.DoCancel();
                        return;
                    case "odloaded":
                        // Arrives on a CEF thread, see HandleNativeDragBeacon
                        _taskManager.RunOnMainThread(() => PageLoaded?.Invoke());
                        context.DoCancel();
                        return;
                }
            }

            // Pages fall back to an XHR against DreamSeeker's HTTP server for topics too long for a byond:// URL
            // (tgui does this past 2048 characters). A query on the page's own path is a topic, not a file.
            if (newUri is {Scheme: "http", Host: "127.0.0.1"} && newUri.Query != string.Empty &&
                !string.IsNullOrEmpty(_webView.Url) &&
                (newUri.AbsolutePath == new Uri(_webView.Url).AbsolutePath || newUri.AbsolutePath == "/")) {
                var query = newUri.Query;
                // Arrives on a CEF thread, see HandleNativeDragBeacon
                _taskManager.RunOnMainThread(() => _netManager.ClientSendMessage(new MsgTopic { Query = query }));
                context.DoRespondStream(Stream.Null, "text/plain", HttpStatusCode.OK);
                return;
            }

            if (newUri is {Scheme: "http", Host: "127.0.0.1"}) {
                Stream stream;
                HttpStatusCode status;
                var resource = new ResPath(newUri.AbsolutePath);
                var path = HttpUtility.UrlDecode(resource.CanonPath); // files are saved in decoded form

                if (resource.Filename.Equals("favicon.ico", StringComparison.OrdinalIgnoreCase)) {
                    stream = Stream.Null;
                    status = HttpStatusCode.NotFound;
                } else if (TryServeIconResourceUrl(newUri, out stream)) {
                    status = HttpStatusCode.OK;
                } else if (!_dreamResource.EnsureCacheFile(path)) {
                    stream = Stream.Null;
                    status = HttpStatusCode.NotFound;
                } else {
                    try {
                        // Shared read: the cache file may be rewritten while a browser holds it open.
                        stream = _resourceManager.UserData.Open(
                            _dreamResource.GetCacheFilePath(path),
                            FileMode.Open,
                            FileAccess.Read,
                            FileShare.ReadWrite | FileShare.Delete);
                        status = HttpStatusCode.OK;
                    } catch (FileNotFoundException) {
                        stream = Stream.Null;
                        status = HttpStatusCode.NotFound;
                    } catch (Exception e) {
                        _sawmill.Error($"Exception while loading file from {path}:\n{e}");
                        stream = Stream.Null;
                        status = HttpStatusCode.InternalServerError;
                    }
                }

                var mimeType = TryParseResourceRef(newUri.AbsolutePath, out _) && newUri.Query != string.Empty
                    ? "image/png"
                    : FileExtensionMimeTypes.GetValueOrDefault(resource.Extension, "application/octet-stream");
                if (status == HttpStatusCode.OK && mimeType == "text/html")
                    stream = AddBrowserShims(stream);


                context.DoRespondStream(stream, mimeType, status);
            }
        } catch (Exception e) {
            _sawmill.Error($"Exception in RequestHandler: {e}");
            context.DoCancel();
        }
    }

    private bool TryServeIconResourceUrl(Uri uri, out Stream stream) {
        stream = Stream.Null;

        if (uri.Query == string.Empty || !TryParseResourceRef(uri.AbsolutePath, out var resourceId))
            return false;

        DMIResource? dmi = null;
        TaskCompletionSource loadedResource = new();

        _dreamResource.LoadResourceAsync<DMIResource>(resourceId, resource => {
            dmi = resource;
            loadedResource.SetResult();
        });

        if (!loadedResource.Task.Wait(TimeSpan.FromSeconds(5))) {
            _sawmill.Error($"Timed out loading icon resource {uri.AbsolutePath} for browser image {uri}");
            return false;
        }

        var queryParams = HttpUtility.ParseQueryString(uri.Query);
        var state = queryParams.Get("state");
        var direction = ParseIconDirection(queryParams.Get("dir"));
        var frame = ParseIconFrame(queryParams.Get("frame"));

        if (dmi == null) {
            _sawmill.Error($"Browser icon resource {uri.AbsolutePath} resolved to null for {uri}");
            return false;
        }

        var png = dmi.GetStateAsPng(state, direction, frame);
        if (png == null) {
            _sawmill.Error($"Browser icon resource {uri.AbsolutePath} could not render state=\"{state}\" dir={direction} frame={frame + 1} for {uri}. Known states: {dmi.DescribeStatesForLog()}");
            return false;
        }

        _sawmill.Debug($"Served browser icon resource {uri.AbsolutePath} state=\"{state}\" dir={direction} frame={frame + 1} length={png.Length}");

        stream = new MemoryStream(png);
        return true;
    }

    private static bool TryParseResourceRef(string path, out int resourceId) {
        resourceId = 0;
        var resourceRef = Uri.UnescapeDataString(path).TrimStart('/');

        if (!resourceRef.StartsWith('[') || !resourceRef.EndsWith(']'))
            return false;

        var refText = resourceRef[1..^1];
        if (!refText.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ||
            !uint.TryParse(refText[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var refValue))
            return false;

        var refType = refValue & RefTypeMask;
        if (refType is not (DreamResourceIconRefType or DreamResourceRefType))
            return false;

        resourceId = (int)(refValue & RefIdMask);
        return true;
    }

    private static AtomDirection ParseIconDirection(string? direction) {
        if (!byte.TryParse(direction, NumberStyles.Integer, CultureInfo.InvariantCulture, out var directionValue))
            return AtomDirection.South;

        return (AtomDirection)directionValue;
    }

    private static int ParseIconFrame(string? frame) {
        if (!int.TryParse(frame, NumberStyles.Integer, CultureInfo.InvariantCulture, out var frameValue))
            return 0;

        // BYOND icon URL helpers use 1-based frame numbers.
        return Math.Max(frameValue - 1, 0);
    }

    /// <summary>
    /// Handles an embedded winset
    /// <code>byond://winset?command=.quit</code>
    /// </summary>
    /// <param name="query">The query portion of the embedded winset</param>
    private void HandleEmbeddedWinset(string query) {
        // Strip the question mark out before parsing
        // Also replace ';' with '&' because they're both usable here
        var queryParams = HttpUtility.ParseQueryString(query.Substring(1).Replace(';', '&'));

        // We need to extract the control element (if one was included).
        // BYOND's browser helpers use "id" here, older OpenDream callers used "element".
        string? element = queryParams.Get("element") ?? queryParams.Get("id");
        queryParams.Remove("element");
        queryParams.Remove("id");

        // Wrap each parameter in quotes so the entire value is used
        foreach (var paramKey in queryParams.AllKeys) {
            if (paramKey == null)
                continue;

            var paramValue = queryParams[paramKey];
            if (paramValue == null)
                continue;

            queryParams.Set(paramKey, $"\"{paramValue}\"");
        }

        // Reassemble the query params without element then convert to winset syntax
        var modifiedQuery = queryParams.ToString();
        modifiedQuery = HttpUtility.UrlDecode(modifiedQuery);
        modifiedQuery = modifiedQuery!.Replace('&', ';'); // TODO: More robust parsing

        // We can finally call winset
        InterfaceManager.WinSet(element, modifiedQuery);
    }

    /// <summary>
    /// Handles an embedded winget
    /// </summary>
    /// <param name="query">The query portion of the embedded winget</param>
    // Example: byond://winget?id=browseroutput&property=size&callback=JSFunction
    // (Not in the XML comment because '&' breaks that apparently)
    private void HandleEmbeddedWinget(string query) {
        // Strip the question mark out before parsing
        // Also replace ';' with '&' because they're both usable here
        var queryParams = HttpUtility.ParseQueryString(query.Substring(1).Replace(';', '&'));

        if (queryParams.Get("id") is not { } elementId ||
            queryParams.Get("property") is not { } property ||
            queryParams.Get("callback") is not { } callback) {
            _sawmill.Error($"Required arg 'id', 'property', or 'callback' not provided in embedded winget ({query})");
            return;
        }

        // tg/TGUI's Byond.winget('output') asks for "*" but uses only the size field
        // to resize the browseroutput pane. Keep that legacy shape instead of handing
        // the browser a huge descriptor object that changes the panel layout path.
        var outputSizeOnly = elementId == "output" && property == "*";
        if (outputSizeOnly)
            property = "size";

        // Multiple properties can be queried in a single winget with "&property=size,view-size"
        var properties = property.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var jsonBuilder = new StringBuilder(); // Build the JSON object that the callback receives

        if (properties.Length == 1 && properties[0] == "*") {
            jsonBuilder.Append(InterfaceManager.WinGet(elementId, "*", forceJson: true));
        } else {
            jsonBuilder.Append("{ ");
            foreach (var wingetting in properties) {
                if (jsonBuilder.Length > 2)
                    jsonBuilder.Append(", ");

                jsonBuilder.Append('"');
                jsonBuilder.Append(HttpUtility.JavaScriptStringEncode(wingetting));
                jsonBuilder.Append("\": ");
                var result = InterfaceManager.WinGet(elementId, wingetting, forceJson: !outputSizeOnly);

                // The result is spliced into a JS object literal, so anything that is not
                // actually JSON must be quoted - an unquoted "400,120" is a syntax error
                // that kills the whole injected script, uncatchably.
                var treatAsJson = !outputSizeOnly && LooksLikeJson(result);

                jsonBuilder.Append(string.IsNullOrEmpty(result)
                    ? "\"\""
                    : treatAsJson
                        ? result
                        : $"\"{HttpUtility.JavaScriptStringEncode(result)}\"");
            }

            jsonBuilder.Append(" }");
        }

        // Execute the callback
        var json = jsonBuilder.ToString();
        InjectScript(BrowserBridgeScript.WrapInjectedCall(callback, json), "winget-callback");
    }

    private void OnShowEvent() {
        ControlDescriptorBrowser controlDescriptor = (ControlDescriptorBrowser)ControlDescriptor;
        if (!string.IsNullOrWhiteSpace(controlDescriptor.OnShowCommand.Value)) {
            InterfaceManager.RunCommand(controlDescriptor.OnShowCommand.AsRaw());
        }
    }

    private void OnHideEvent() {
        ControlDescriptorBrowser controlDescriptor = (ControlDescriptorBrowser)ControlDescriptor;
        if (!string.IsNullOrWhiteSpace(controlDescriptor.OnHideCommand.Value)) {
            InterfaceManager.RunCommand(controlDescriptor.OnHideCommand.AsRaw());
        }
    }
}

public sealed class BrowseWinCommand : IConsoleCommand {
    public string Command => "browsewin";
    public string Description => "";
    public string Help => "";

    public void Execute(IConsoleShell shell, string argStr, string[] args) {
        if (args.Length != 1) {
            shell.WriteError("Incorrect amount of arguments! Must be a single one.");
            return;
        }

        var parameters = new BrowserWindowCreateParameters(1280, 720) {Url = args[0]};

        var cef = IoCManager.Resolve<IWebViewManager>();
        cef.CreateBrowserWindow(parameters);
    }
}
