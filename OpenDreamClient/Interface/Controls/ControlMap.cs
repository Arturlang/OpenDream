using System.Diagnostics.CodeAnalysis;
using OpenDreamClient.Input;
using OpenDreamClient.Interface.Controls.UI;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using OpenDreamClient.Rendering;
using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.Input;

namespace OpenDreamClient.Interface.Controls;

public sealed partial class ControlMap(ControlDescriptor controlDescriptor, ControlWindow window) : InterfaceControl(controlDescriptor, window) {
    public ScalingViewport Viewport { get; private set; } = default!;

    [Dependency] private IEntitySystemManager _entitySystemManager = default!;
    private MouseInputSystem? _mouseInput;
    private ClientAppearanceSystem? _appearanceSystem;

    /// Public so the maptext renderer can read the map's stylesheet and font: BYOND
    /// resolves maptext styling against the map control, not against the atom.
    public ControlDescriptorMap MapDescriptor => (ControlDescriptorMap)ElementDescriptor;

    private ClientObjectReference? _atomUnderMouse;

    protected override void UpdateElementDescriptor() {
        base.UpdateElementDescriptor();

        Viewport.MapControlId = MapDescriptor.IsDefault.Value ? null : Id.Value;
        Viewport.MapControlClipOffset = MapDescriptor.OpenDreamClipOffset.Vector;
        Viewport.MapControlFullSize = MapDescriptor.OpenDreamFullSize.Vector;
        Viewport.Visible = MapDescriptor.IsVisible.Value;

        Viewport.StretchMode = MapDescriptor.ZoomMode.Value switch {
            "blur" => ScalingViewportStretchMode.Bilinear,
            "distort" => ScalingViewportStretchMode.Nearest,

            // TODO: "tries to keep the look of individual pixels,
            //          but will adjust to non-integer zooms (like 1.1x) by blending neighboring pixels"
            "normal" or _ => ScalingViewportStretchMode.Nearest
        };

        UpdateViewRange(InterfaceManager.View);
    }

    /// <param name="bounds">The region to display in tiles, relative to the view's bottom-left. BYOND grows the map
    /// past the view to fit screen objects placed outside it. Defaults to just the view.</param>
    public void UpdateViewRange(ViewRange view, ScreenLocationBounds? bounds = null) {
        // The default map keeps showing the screen objects outside its view across skin updates
        if (bounds == null && MapDescriptor.IsDefault.Value)
            bounds = InterfaceManager.DefaultMapBounds;

        var viewWidth = (float)Math.Max(view.Width, 1);
        var viewHeight = (float)Math.Max(view.Height, 1);
        if (bounds is { } b) {
            viewWidth = Math.Max(b.Right - b.Left, 1);
            viewHeight = Math.Max(b.Top - b.Bottom, 1);
        }

        Viewport.ViewportSize = new Vector2i(
            (int)MathF.Round(viewWidth * InterfaceManager.IconSize),
            (int)MathF.Round(viewHeight * InterfaceManager.IconSize));
        if (MapDescriptor.IconSize.Value != 0) {
            // BYOND supports a negative number here (flips the view), but we're gonna enforce a positive number instead
            var iconSize = Math.Max(MapDescriptor.IconSize.Value, 1);

            Viewport.SetWidth = iconSize * viewWidth;
            Viewport.SetHeight = iconSize * viewHeight;
        } else {
            // icon-size of 0 means stretch to fit the available space
            Viewport.SetWidth = float.NaN;
            Viewport.SetHeight = float.NaN;
        }
    }

    protected override Control CreateUIElement() {
        Viewport = new ScalingViewport { MouseFilter = Control.MouseFilterMode.Stop };
        Viewport.OnKeyBindDown += OnViewportKeyBindEvent;
        Viewport.OnKeyBindUp += OnViewportKeyBindEvent;
        Viewport.OnMouseMove += OnViewportMouseMoveEvent;
        Viewport.OnMouseExited += OnViewportMouseExitedEvent;
        Viewport.OnVisibilityChanged += (args) => {
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

        UpdateViewRange(InterfaceManager.View);

        return new PanelContainer { StyleClasses = {"MapBackground"}, Children = { Viewport } };
    }

    private void OnViewportKeyBindEvent(GUIBoundKeyEventArgs e) {
        if (e.Function == EngineKeyFunctions.Use || e.Function == EngineKeyFunctions.TextCursorSelect ||
            e.Function == EngineKeyFunctions.UIRightClick || e.Function == OpenDreamKeyFunctions.MouseMiddle ||
            e.Function == OpenDreamKeyFunctions.MouseButton4 || e.Function == OpenDreamKeyFunctions.MouseButton5) {
            _entitySystemManager.Resolve(ref _mouseInput);

            if (_mouseInput.HandleViewportEvent(Viewport, e, ControlDescriptor)) {
                e.Handle();
            }
        }
    }

    private void OnViewportMouseMoveEvent(GUIMouseMoveEventArgs e) {
        if (_mouseInput == null)
            return;

        var underMouse = _mouseInput.GetAtomUnderMouse(Viewport, e.RelativePixelPosition, e.GlobalPixelPosition);
        UpdateAtomUnderMouse(underMouse?.Atom, e.RelativePixelPosition, underMouse?.IconPosition ?? Vector2i.Zero);
    }

    private void OnViewportMouseExitedEvent(GUIMouseHoverEventArgs e) {
        UpdateAtomUnderMouse(null, Vector2.Zero, Vector2i.Zero);
    }

    public void OnShowEvent() {
        ControlDescriptorMap controlDescriptor = (ControlDescriptorMap)ControlDescriptor;
        if (!string.IsNullOrWhiteSpace(controlDescriptor.OnShowCommand.Value)) {
            InterfaceManager.RunCommand(controlDescriptor.OnShowCommand.AsRaw());
        }
    }

    public void OnHideEvent() {
        ControlDescriptorMap controlDescriptor = (ControlDescriptorMap)ControlDescriptor;
        if (!string.IsNullOrWhiteSpace(controlDescriptor.OnHideCommand.Value)) {
            InterfaceManager.RunCommand(controlDescriptor.OnHideCommand.AsRaw());
        }
    }

    public override bool TryGetProperty(string property, [NotNullWhen(true)] out IDMFProperty? value) {
        switch (property) {
            case "view-size": // Size of the final viewport (resized and all) rather than the whole container
                value = new DMFPropertyVec2(Viewport.GetDrawBox().Size);
                return true;
            case "mouse-pos":
            case "inner-mouse-pos":
                var mousePos = IoCManager.Resolve<IUserInterfaceManager>().MousePositionScaled.Position;
                mousePos -= Viewport.GlobalPosition;

                value = new DMFPropertyVec2(mousePos);
                return true;
            // Keys reach the map's macros whenever no other control holds keyboard focus
            case "focus":
                value = new DMFPropertyBool(IoCManager.Resolve<IUserInterfaceManager>().KeyboardFocused == null);
                return true;
            default:
                return base.TryGetProperty(property, out value);
        }
    }

    public override void SetProperty(string property, string value, bool manualWinset = false) {
        switch (property) {
            // tgui's chat and stat panels hand focus back with map.focus=true after every click, so movement keeps
            // working; taking it means releasing whatever control (a browser, an input) has the keyboard
            case "focus":
                if (new DMFPropertyBool(value).Value)
                    IoCManager.Resolve<IUserInterfaceManager>().KeyboardFocused?.ReleaseKeyboardFocus();
                break;
            default:
                base.SetProperty(property, value, manualWinset);
                break;
        }
    }

    private void UpdateAtomUnderMouse(ClientObjectReference? atom, Vector2 relativePos, Vector2i iconPos) {
        if (!_atomUnderMouse.Equals(atom)) {
            _entitySystemManager.Resolve(ref _appearanceSystem);
            var name = (atom != null) ? _appearanceSystem.GetNameUnformatted(atom.Value) : string.Empty;
            Window?.SetStatus(name);

            if (_atomUnderMouse != null)
                _mouseInput?.HandleAtomMouseExited(Viewport, _atomUnderMouse.Value);
            if (atom != null) {
                _mouseInput?.HandleAtomMouseEntered(Viewport, relativePos, atom.Value, iconPos);
            }
        } else if (atom.HasValue) {
            _mouseInput?.HandleAtomMouseMove(Viewport, relativePos, atom.Value, iconPos);
        }

        _atomUnderMouse = atom;
    }
}
