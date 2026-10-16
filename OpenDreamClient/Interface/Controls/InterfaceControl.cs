using System.Diagnostics.CodeAnalysis;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Client.Graphics;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;

namespace OpenDreamClient.Interface.Controls;

public abstract class InterfaceControl : InterfaceElement {
    public readonly Control UIElement;
    public bool IsDefault => ControlDescriptor.IsDefault.Value;
    public DMFPropertySize Size => ControlDescriptor.Size;
    public DMFPropertyPos Pos => ControlDescriptor.Pos;
    public DMFPropertyPos? Anchor1 => ControlDescriptor.Anchor1;
    public DMFPropertyPos? Anchor2 => ControlDescriptor.Anchor2;

    /// <summary>
    /// True when both anchors span the whole parent (0,0 to 100,100), meaning the
    /// anchor layout fully dictates this control's position and size.
    /// </summary>
    protected bool IsFullyAnchored =>
        Anchor1 is { X: 0, Y: 0 } && Anchor2 is { X: 100, Y: 100 };

    /// <summary>
    /// The position that anchor1 and anchor2 anchor themselves to.
    /// Updates when this control's size/pos is winset,
    /// or when this control's size is 0 and a sibling control's size/pos is winset
    /// </summary>
    public Vector2i AnchorPosition = Vector2i.Zero;

    protected ControlDescriptor ControlDescriptor => (ControlDescriptor) ElementDescriptor;
    protected readonly ControlWindow? Window;

    [SuppressMessage("ReSharper", "VirtualMemberCallInConstructor")]
    protected InterfaceControl(ControlDescriptor controlDescriptor, ControlWindow? window) : base(controlDescriptor) {
        IoCManager.InjectDependencies(this);

        Window = window;
        UIElement = CreateUIElement();
        UIElement.Name = ElementDescriptor.Id.AsRaw();

        SetProperty("size", ControlDescriptor.Size.AsRaw());
        SetProperty("pos", ControlDescriptor.Pos.AsRaw());

        UpdateElementDescriptor();
    }

    protected abstract Control CreateUIElement();

    protected override void UpdateElementDescriptor() {
        UIElement.Name = ControlDescriptor.Id.Value;

        //transparent is default because it's white with 0 alpha, and DMF color can't have none-255 alpha
        var background = ControlDescriptor.BackgroundColor.Value;
        StyleBox? styleBox = (background != Color.Transparent)
            ? new StyleBoxFlat {BackgroundColor = background}
            : null;

        // BYOND draws every border style as a 1px frame; #646464 is what DreamSeeker uses for "line"
        if (ControlDescriptor.Border.Value is "line" or "sunken" or "raised" && UIElement is PanelContainer or LineEdit) {
            styleBox = new StyleBoxFlat {
                BackgroundColor = background != Color.Transparent ? background : (UIElement is LineEdit ? Color.White : Color.Transparent),
                BorderColor = Color.FromHex("#646464"),
                BorderThickness = new Thickness(1)
            };
        }

        switch (UIElement) {
            case PanelContainer panel:
                panel.PanelOverride = styleBox;
                break;
            case LineEdit lineEdit:
                lineEdit.StyleBoxOverride = styleBox;
                break;
            case Button button:
                button.StyleBoxOverride = styleBox;
                break;
        }

        Color? textColor = (ControlDescriptor.TextColor.Value != Color.Transparent)
            ? ControlDescriptor.TextColor.Value
            : null;

        switch (UIElement) {
            case Button button:
                button.Label.FontColorOverride = textColor;
                break;
        }

        UIElement.Visible = ControlDescriptor.IsVisible.Value;
        // TODO: enablement
        //UIControl.IsEnabled = !_controlDescriptor.IsDisabled;
    }

    public override bool TryGetProperty(string property, [NotNullWhen(true)] out IDMFProperty? value) {
        switch (property) {
            case "size":
                // Prefer the live arranged size: SetSize only reflects the last anchor
                // recomputation, which goes stale whenever the layout has since changed.
                // BYOND reports the current size, and content depends on that - e.g.
                // tgui-panel wingets the legacy output's size and winsets it onto the
                // chat browser; a stale value there permanently mis-sizes the chat.
                // Size doesn't update while the element is hidden or detached, so fall
                // back to SetSize for controls that were never laid out.
                value = UIElement.Size != Vector2.Zero
                    ? new DMFPropertySize((Vector2i)UIElement.Size)
                    : new DMFPropertySize(UIElement.SetSize);
                return true;
            case "pos":
                value = new DMFPropertyPos(UIElement.Position);
                return true;
            default:
                return base.TryGetProperty(property, out value);
        }
    }

    public override void SetProperty(string property, string value, bool manualWinset = false) {
        switch (property) {
            case "size":
                // A fully-anchored control's size is dictated by its anchors; accepting a
                // manual size would bake the difference into the anchor offsets (the
                // descriptor size feeds UpdateAnchors). Content relies on this being a
                // no-op: tgui-panel wingets the legacy output's size and winsets it onto
                // the chat browser while the window is still resizing during boot, and a
                // stale value here permanently squished the chat panel into the left of
                // its pane.
                if (manualWinset && IsFullyAnchored)
                    return;

                var size = new DMFPropertySize(value);
                ControlDescriptor.Size = size;

                // A size of 0 takes up the remaining space of the window as defined by the DMF
                if (size.X == 0 && Window != null)
                    size.X = Window.Size.X - ControlDescriptor.Pos.X;
                if (size.Y == 0 && Window != null)
                    size.Y = Window.Size.Y - ControlDescriptor.Pos.Y;

                value = size.AsRaw(); // May have been modified by the above
                UIElement.SetSize = size.Vector;

                if (manualWinset)
                    Window?.UpdateAnchorPosition(this);
                break;
            case "pos":
                var pos = new DMFPropertyPos(value);
                ControlDescriptor.Pos = pos;

                LayoutContainer.SetMarginLeft(UIElement, pos.X);
                LayoutContainer.SetMarginTop(UIElement, pos.Y);

                if (manualWinset)
                    Window?.UpdateAnchorPosition(this);
                break;
        }

        base.SetProperty(property, value, manualWinset);
    }

    public virtual void Output(string value, string? data) {
    }
}
