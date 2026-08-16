using System.Diagnostics.CodeAnalysis;
using System.Linq;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.GameObjects;
using Robust.Shared.IoC;
using Robust.Shared.Maths;
using static Robust.Client.UserInterface.StylesheetHelpers;

namespace OpenDreamClient.Interface.Controls;

internal sealed class ControlInput(ControlDescriptor controlDescriptor, ControlWindow window) : InterfaceControl(controlDescriptor, window) {
    private LineEdit _textBox = default!;
    private Color? _appliedTextColor;

    private IEntitySystemManager? _entitySystems;
    private List<string>? _completionMatches;
    private int _completionIndex;
    private bool _applyingCompletion;

    private ControlDescriptorInput InputDescriptor => (ControlDescriptorInput)ControlDescriptor;

    protected override Control CreateUIElement() {
        _textBox = new LineEdit();
        _textBox.OnTextEntered += TextBox_OnSubmit;
        _textBox.OnTextChanged += TextBox_OnTextChanged;
        _textBox.OnTabComplete += TextBox_OnTabComplete;

        return _textBox;
    }

    private void TextBox_OnTextChanged(LineEdit.LineEditEventArgs args) {
        // Any edit that isn't ours invalidates an in-progress completion cycle.
        if (!_applyingCompletion)
            _completionMatches = null;
    }

    /// <summary>
    /// BYOND-style verb completion: Tab completes the typed prefix to an executable verb's
    /// command name, further Tabs cycle through the other matches.
    /// </summary>
    private void TextBox_OnTabComplete(LineEdit.LineEditEventArgs args) {
        // An input with a fixed command (say bars etc.) doesn't take verb names.
        if (!string.IsNullOrEmpty(InputDescriptor.Command.Value))
            return;

        if (_completionMatches == null) {
            var prefix = _textBox.Text;
            if (string.IsNullOrWhiteSpace(prefix))
                return;

            _entitySystems ??= IoCManager.Resolve<IEntitySystemManager>();
            if (!_entitySystems.TryGetEntitySystem<ClientVerbSystem>(out var verbSystem))
                return;

            var matches = verbSystem.GetExecutableVerbs()
                .Select(verb => verb.VerbInfo.GetCommandName())
                .Where(name => name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                .Distinct()
                .Order(StringComparer.OrdinalIgnoreCase)
                .ToList();

            if (matches.Count == 0)
                return;

            _completionMatches = matches;
            _completionIndex = 0;
        } else {
            _completionIndex = (_completionIndex + 1) % _completionMatches.Count;
        }

        var completion = _completionMatches[_completionIndex];

        _applyingCompletion = true;
        _textBox.Text = completion;
        _textBox.CursorPosition = completion.Length;
        _applyingCompletion = false;
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
