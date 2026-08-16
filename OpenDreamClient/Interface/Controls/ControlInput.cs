using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Numerics;
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
    private IUserInterfaceManager? _uiManager;
    private Popup? _completionPopup;
    private ItemList? _completionList;
    private List<string>? _completionMatches;
    private int _completionIndex = -1;
    private bool _applyingCompletion;

    private const int CompletionMaxVisibleRows = 8;
    private const float CompletionRowHeight = 24;

    private ControlDescriptorInput InputDescriptor => (ControlDescriptorInput)ControlDescriptor;

    protected override Control CreateUIElement() {
        _textBox = new LineEdit();
        _textBox.OnTextEntered += TextBox_OnSubmit;
        _textBox.OnTextChanged += TextBox_OnTextChanged;
        _textBox.OnTabComplete += TextBox_OnTabComplete;

        return _textBox;
    }

    private void TextBox_OnTextChanged(LineEdit.LineEditEventArgs args) {
        // Any edit that isn't ours invalidates an in-progress completion.
        if (_applyingCompletion)
            return;

        _completionMatches = null;
        _completionIndex = -1;
        _completionPopup?.Close();
    }

    /// <summary>
    /// BYOND-style verb completion. Tab completes the typed prefix to an executable verb's
    /// command name: a single match completes immediately, multiple matches extend to their
    /// longest common prefix and open a list to pick from (click, or keep pressing Tab to
    /// cycle). Any manual edit dismisses the list.
    /// </summary>
    private void TextBox_OnTabComplete(LineEdit.LineEditEventArgs args) {
        // An input with a fixed command (say bars etc.) doesn't take verb names.
        if (!string.IsNullOrEmpty(InputDescriptor.Command.Value))
            return;

        // Cycling an already-open list.
        if (_completionMatches != null && _completionPopup is {Visible: true}) {
            _completionIndex = (_completionIndex + 1) % _completionMatches.Count;
            HighlightCompletion(_completionIndex);
            ApplyCompletion(_completionMatches[_completionIndex]);
            return;
        }

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

        switch (matches.Count) {
            case 0:
                return;
            case 1:
                ApplyCompletion(matches[0]);
                return;
        }

        // Multiple matches: fill in as much as is unambiguous, then offer the list.
        var common = LongestCommonPrefix(matches);
        if (common.Length > prefix.Length)
            ApplyCompletion(common);

        _completionMatches = matches;
        _completionIndex = -1;
        ShowCompletionPopup(matches);
    }

    private void ApplyCompletion(string completion) {
        _applyingCompletion = true;
        _textBox.Text = completion;
        _textBox.CursorPosition = completion.Length;
        _applyingCompletion = false;
    }

    private void ShowCompletionPopup(List<string> matches) {
        _uiManager ??= IoCManager.Resolve<IUserInterfaceManager>();

        if (_completionPopup == null) {
            _completionList = new ItemList();
            _completionList.OnItemSelected += eventArgs => {
                if (_applyingCompletion || _completionMatches == null)
                    return;

                _completionIndex = eventArgs.ItemIndex;
                ApplyCompletion(_completionMatches[eventArgs.ItemIndex]);
                _completionPopup?.Close();
                _textBox.GrabKeyboardFocus();
            };

            _completionPopup = new Popup();
            _completionPopup.AddChild(_completionList);
            _uiManager.ModalRoot.AddChild(_completionPopup);
        }

        _completionList!.Clear();
        foreach (var match in matches) {
            _completionList.AddItem(match);
        }

        var uiScale = _uiManager.ModalRoot.UIScale;
        var inputTopLeft = _textBox.GlobalPixelPosition / uiScale;
        var inputSize = _textBox.PixelSize / uiScale;

        var height = Math.Min(matches.Count, CompletionMaxVisibleRows) * CompletionRowHeight + 4;
        var width = Math.Max(inputSize.X, 250);

        // Above the input; below it if there is no room.
        var y = inputTopLeft.Y >= height
            ? inputTopLeft.Y - height
            : inputTopLeft.Y + inputSize.Y;

        _completionPopup.Open(UIBox2.FromDimensions(new Vector2(inputTopLeft.X, y), new Vector2(width, height)));
        _textBox.GrabKeyboardFocus();
    }

    private void HighlightCompletion(int index) {
        if (_completionList == null)
            return;

        _applyingCompletion = true;
        _completionList.ClearSelected();
        _completionList[index].Selected = true;
        _applyingCompletion = false;
    }

    private static string LongestCommonPrefix(List<string> values) {
        var prefix = values[0];

        foreach (var value in values) {
            var length = Math.Min(prefix.Length, value.Length);
            var i = 0;
            while (i < length && char.ToLowerInvariant(prefix[i]) == char.ToLowerInvariant(value[i]))
                i++;

            prefix = prefix[..i];
        }

        return prefix;
    }

    private void TextBox_OnSubmit(LineEdit.LineEditEventArgs lineEditEventArgs) {
        _completionMatches = null;
        _completionIndex = -1;
        _completionPopup?.Close();

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
