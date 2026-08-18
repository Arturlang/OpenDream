using OpenDreamClient.Interface.Controls;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Client.Input;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Client.UserInterface.CustomControls;
using Robust.Shared.IoC;
using Robust.Shared.Maths;
using Robust.Shared.Log;
using System.Numerics;

namespace OpenDreamClient.Interface;

internal sealed class BrowsePopup {
    public event Action? Closed;

    public readonly ControlBrowser Browser;
    public readonly ControlWindow WindowElement;

    private readonly ChromelessBrowseWindow _window;
    private bool _closed;

    private IInputManager? _inputManager;
    private bool _nativeDragging;
    private Vector2i _nativeDragOffset;

    public BrowsePopup(string name, Vector2i size) {
        WindowDescriptor popupWindowDescriptor = new WindowDescriptor(name,
            new() {
                new ControlDescriptorBrowser {
                    Id = new DMFPropertyString("browser"),
                    Size = new DMFPropertySize(size),
                    Anchor1 = new DMFPropertyPos(0, 0),
                    Anchor2 = new DMFPropertyPos(100, 100)
                }
            }) {
                Size = new DMFPropertySize(size),
                IsPane = new DMFPropertyBool(true)
            };

        WindowElement = new ControlWindow(popupWindowDescriptor);
        WindowElement.CreateChildControls();

        _window = new ChromelessBrowseWindow(name, size, WindowElement.UIElement);
        _window.OnClose += OnWindowClosed;
        _window.OnResized += OnWindowResized;

        Browser = (ControlBrowser)WindowElement.ChildControls[0];
        Browser.NativeDragStarted += StartNativeDrag;
        Browser.NativeDragEnded += EndNativeDrag;
    }

    /// <summary>
    /// Begins moving the window from real mouse input instead of letting the page drag
    /// itself. Raised on the game thread (ControlBrowser marshals the page's beacon).
    ///
    /// Release also comes from the page: clicks consumed by UI controls never reach the
    /// input manager's key state, so IsKeyDown(MouseLeft) reads false during the entire
    /// drag and cannot be used to detect the release.
    /// </summary>
    private void StartNativeDrag() {
        if (_closed)
            return;

        _inputManager ??= IoCManager.Resolve<IInputManager>();

        var mouse = (Vector2i)_inputManager.MouseScreenPosition.Position;
        _nativeDragOffset = mouse - _window.GlobalPixelPosition;
        _nativeDragging = true;
        Logger.GetSawmill("opendream.popup").Debug(
            $"native drag start: mouse={mouse} window={_window.GlobalPixelPosition} offset={_nativeDragOffset}");
    }

    private void EndNativeDrag() {
        if (_nativeDragging)
            Logger.GetSawmill("opendream.popup").Debug("native drag end");

        _nativeDragging = false;
    }

    /// <summary>
    /// Advances a native drag. Called every frame by the interface manager, on the game
    /// thread. Moving the window from real mouse input has no page round-trips, unlike
    /// TGUI's own screenX-derived drag, whose backing geometry races the mouse events
    /// that follow each move and stutters.
    /// </summary>
    public void ProcessNativeDrag() {
        if (!_nativeDragging || _inputManager == null)
            return;

        if (_closed) {
            _nativeDragging = false;
            return;
        }

        var mouse = (Vector2i)_inputManager.MouseScreenPosition.Position;
        SetPosition(mouse - _nativeDragOffset);
    }

    public void Open() {
        _window.OpenHiddenCentered();
        UpdateBrowserGeometry();
    }

    public void Close() {
        _window.Close();
    }

    public void SetProperty(string property, string value) {
        switch (property) {
            case "pos":
                SetPosition(new DMFPropertyPos(value).Vector);
                break;
            case "size":
                SetSize(new DMFPropertySize(value).Vector);
                break;
            case "is-visible":
                SetVisible(new DMFPropertyBool(value).Value);
                break;
            case "can-resize":
                _window.Resizable = new DMFPropertyBool(value).Value;
                break;
            case "can-close":
            case "titlebar":
                // TGUI owns the visible chrome for browse popups.
                break;
            default:
                WindowElement.SetProperty(property, value, manualWinset: true);
                break;
        }
    }

    public bool TryGetProperty(string property, out IDMFProperty? value) {
        switch (property) {
            case "pos":
                value = new DMFPropertyPos(_window.GlobalPixelPosition);
                return true;
            case "size":
            case "inner-size":
            case "outer-size":
                value = new DMFPropertySize(_window.Size);
                return true;
            case "is-visible":
                value = new DMFPropertyBool(_window.Visible && _window.IsOpen);
                return true;
            case "can-resize":
                value = new DMFPropertyBool(_window.Resizable);
                return true;
            case "can-close":
                value = new DMFPropertyBool(true);
                return true;
            default:
                return WindowElement.TryGetProperty(property, out value);
        }
    }

    private void SetPosition(Vector2i position) {
        LayoutContainer.SetPosition(_window, PixelToParentUiPosition(position));
        UpdateBrowserGeometry();
    }

    private void SetSize(Vector2i size) {
        size = new Vector2i(Math.Max(size.X, 150), Math.Max(size.Y, 50));
        _window.SetSize = size;
        // Engine plumbing, not a content winset: fully-anchored controls ignore manual
        // size winsets, but these panes must track the popup window's real size.
        WindowElement.SetProperty("size", $"{size.X}x{size.Y}");
        Browser.SetProperty("size", $"{size.X}x{size.Y}");
        UpdateBrowserGeometry();
    }

    private void SetVisible(bool visible) {
        _window.Visible = visible;
        if (visible && _window is { IsOpen: false })
            _window.OpenCentered();

        UpdateBrowserGeometry();
    }

    private void UpdateBrowserGeometry() {
        Browser.SetGeometryOrigin(_window.GlobalPixelPosition);
    }

    private void OnWindowResized() {
        var size = _window.Size;
        var pixelSize = new Vector2i((int)size.X, (int)size.Y);
        WindowElement.SetProperty("size", $"{pixelSize.X}x{pixelSize.Y}");
        Browser.SetProperty("size", $"{pixelSize.X}x{pixelSize.Y}");
        UpdateBrowserGeometry();
    }

    private Vector2 PixelToParentUiPosition(Vector2i pixelPosition) {
        var parentPixelPosition = _window.Parent?.GlobalPixelPosition ?? Vector2i.Zero;
        var relativePixelPosition = pixelPosition - parentPixelPosition;
        var uiScale = _window.UIScale;

        return new Vector2(relativePixelPosition.X / uiScale, relativePixelPosition.Y / uiScale);
    }

    private void OnWindowClosed() {
        if (_closed)
            return;

        _closed = true;
        Browser.ShutdownBrowser();
        Closed?.Invoke();
    }

    private sealed class ChromelessBrowseWindow : BaseWindow {
        public ChromelessBrowseWindow(string name, Vector2i size, Control contents) {
            Name = name;
            SetSize = size;
            MinSize = new Vector2(150, 50);
            MouseFilter = MouseFilterMode.Stop;
            Resizable = true;
            AddChild(contents);
        }

        public void OpenHiddenCentered() {
            Measure(Vector2Helpers.Infinity);

            if (!IsOpen)
                UserInterfaceManager.WindowRoot.AddChild(this);

            RecenterWindow(new Vector2(0.5f, 0.5f));
            Visible = false;
        }

        protected override DragMode GetDragModeFor(Vector2 relativeMousePos) {
            const int dragMarginSize = 6;

            if (!Resizable)
                return DragMode.None;

            var mode = DragMode.None;
            if (relativeMousePos.Y < dragMarginSize)
                mode = DragMode.Top;
            else if (relativeMousePos.Y > Size.Y - dragMarginSize)
                mode = DragMode.Bottom;

            if (relativeMousePos.X < dragMarginSize)
                mode |= DragMode.Left;
            else if (relativeMousePos.X > Size.X - dragMarginSize)
                mode |= DragMode.Right;

            return mode;
        }
    }
}
