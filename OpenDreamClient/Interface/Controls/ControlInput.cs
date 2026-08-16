using System.Diagnostics.CodeAnalysis;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.IoC;
using Robust.Shared.Maths;
using static Robust.Client.UserInterface.StylesheetHelpers;

namespace OpenDreamClient.Interface.Controls;

internal sealed class ControlInput(ControlDescriptor controlDescriptor, ControlWindow window) : InterfaceControl(controlDescriptor, window) {
    private LineEdit _textBox = default!;
    private Color? _appliedTextColor;

    private ControlDescriptorInput InputDescriptor => (ControlDescriptorInput)ControlDescriptor;

    protected override Control CreateUIElement() {
        _textBox = new LineEdit();
        _textBox.OnTextEntered += TextBox_OnSubmit;

        return _textBox;
    }

    private void TextBox_OnSubmit(LineEdit.LineEditEventArgs lineEditEventArgs) {
        if (InputDescriptor.NoCommand.Value)
            return;

        ResetText();

        var command = InputDescriptor.Command.Value;
        if (command.StartsWith('!')) {
            InterfaceManager.RunCommand(lineEditEventArgs.Text);
        } else {
            InterfaceManager.RunCommand(command + lineEditEventArgs.Text);
        }
    }

    protected override void UpdateElementDescriptor() {
        base.UpdateElementDescriptor();

        UpdateTextColor();
        ResetText();
    }

    /// <summary>
    /// Applies the DMF text-color to the LineEdit.
    ///
    /// LineEdit resolves its colour from the "font-color" style property with no
    /// per-instance override, so a skin that darkens the input bar was getting
    /// DreamStylesheet's black-on-black. Robust does allow a per-subtree stylesheet,
    /// so we append one higher-priority LineEdit rule to the base sheet.
    /// </summary>
    private void UpdateTextColor() {
        var textColor = ControlDescriptor.TextColor.Value;
        Color? wanted = textColor != Color.Transparent ? textColor : null;
        if (wanted == _appliedTextColor)
            return;

        _appliedTextColor = wanted;
        if (wanted == null) {
            _textBox.Stylesheet = null;
            return;
        }

        var baseSheet = IoCManager.Resolve<IUserInterfaceManager>().Stylesheet;
        var rules = new List<StyleRule>(baseSheet?.Rules ?? []) {
            // Appended last: later rules win at equal specificity.
            Element<LineEdit>()
                .Prop("font-color", wanted.Value)
                .Prop("cursor-color", wanted.Value),
        };

        _textBox.Stylesheet = new Stylesheet(rules);
    }

    public override bool TryGetProperty(string property, [NotNullWhen(true)] out IDMFProperty? value) {
        switch (property) {
            case "text":
                value = new DMFPropertyString(_textBox.Text);
                return true;
            default:
                return base.TryGetProperty(property, out value);
        }
    }

    public override void SetProperty(string property, string value, bool manualWinset = false) {
        switch (property) {
            case "focus":
                var focusValue = new DMFPropertyBool(value);
                if (focusValue.Value)
                    _textBox.GrabKeyboardFocus();
                break;
            case "text":
                _textBox.Text = value;
                break;
            default:
                base.SetProperty(property, value, manualWinset);
                break;
        }
    }

    private void ResetText() {
        var command = InputDescriptor.Command.Value;

        if (command.StartsWith('!')) {
            _textBox.Text = command[1..];
        } else {
            _textBox.Clear();
        }
    }
}
