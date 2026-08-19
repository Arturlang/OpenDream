using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Numerics;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.GameObjects;
using Robust.Shared.Input;
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
    private string _completionPrefix = "";
    private int _completionIndex = -1;
    private bool _applyingCompletion;

    private const int CompletionMaxVisibleRows = 8;
    private const float CompletionRowHeight = 24;

    private ControlDescriptorInput InputDescriptor => (ControlDescriptorInput)ControlDescriptor;

    protected override Control CreateUIElement() {
        _textBox = new CompletionLineEdit { KeyBindInterceptor = InterceptKeyBind, TextInterceptor = InterceptTextEntry };
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
    /// Handles list navigation keys while the completion popup is open: arrows move the
    /// selection, Enter confirms. Returns true when the key was consumed.
    /// </summary>
    private bool InterceptKeyBind(GUIBoundKeyEventArgs args) {
        if (_completionPopup is not {Visible: true} || _completionMatches == null)
            return false;

        if (args.Function == EngineKeyFunctions.TextHistoryPrev) {
            MoveCompletionSelection(-1);
            return true;
        }

        if (args.Function == EngineKeyFunctions.TextHistoryNext) {
            MoveCompletionSelection(1);
            return true;
        }

        if (args.Function == EngineKeyFunctions.TextSubmit) {
            ConfirmCompletion();
            return true;
        }

        return false;
    }

    /// <summary>
    /// Handles typed characters while the completion popup is open: space confirms the
    /// selection (leaving the verb ready to take arguments), and a letter jumps to the
    /// option continuing the typed prefix with that letter - or, when the selection
    /// already matches, cycles through the options for that letter.
    /// </summary>
    private bool InterceptTextEntry(GUITextEnteredEventArgs args) {
        if (_completionPopup is not {Visible: true} || _completionMatches == null) {
            // BYOND completes a partially-typed verb when space is pressed; only the
            // first word qualifies, and the space falls through when nothing matches.
            if (args.Text == " " && string.IsNullOrEmpty(InputDescriptor.Command.Value) &&
                !string.IsNullOrWhiteSpace(_textBox.Text) && !_textBox.Text.Contains(' '))
                return TryStartCompletion(fromSpace: true);

            return false;
        }

        if (args.Text == " ") {
            if (_completionIndex >= 0)
                ConfirmCompletion(appendSpace: true);

            return true;
        }

        if (args.Text.Length == 1 && char.IsLetterOrDigit(args.Text[0])) {
            JumpCompletionToLetter(char.ToLowerInvariant(args.Text[0]));
            return true;
        }

        return false;
    }

    private void JumpCompletionToLetter(char letter) {
        if (_completionMatches == null || _completionMatches.Count == 0)
            return;

        // The options usually all share the typed prefix, so jump by the first letter
        // after it; fall back to the literal first letter of the option. Compared
        // per-character: building prefix+letter strings trips the content sandbox
        // (the compiler lowers char concatenation through ReadOnlySpan).
        var prefixLength = _completionPrefix.Length;
        var candidates = new List<int>();
        for (int i = 0; i < _completionMatches.Count; i++) {
            var option = _completionMatches[i];
            if (option.Length > prefixLength && char.ToLowerInvariant(option[prefixLength]) == letter)
                candidates.Add(i);
        }

        if (candidates.Count == 0) {
            for (int i = 0; i < _completionMatches.Count; i++) {
                if (char.ToLowerInvariant(_completionMatches[i][0]) == letter)
                    candidates.Add(i);
            }
        }

        if (candidates.Count == 0)
            return;

        // Same letter again cycles through its options
        var position = candidates.IndexOf(_completionIndex);
        _completionIndex = candidates[position == -1 ? 0 : (position + 1) % candidates.Count];
        HighlightCompletion(_completionIndex);
    }

    private void MoveCompletionSelection(int delta) {
        if (_completionMatches == null || _completionMatches.Count == 0)
            return;

        _completionIndex = ((_completionIndex < 0 ? 0 : _completionIndex) + delta + _completionMatches.Count) % _completionMatches.Count;
        HighlightCompletion(_completionIndex);
    }

    private void ConfirmCompletion(bool appendSpace = false) {
        if (_completionMatches == null || _completionIndex < 0)
            return;

        ApplyCompletion(_completionMatches[_completionIndex] + (appendSpace ? " " : ""));
        _completionMatches = null;
        _completionIndex = -1;
        _completionPopup?.Close();
        _textBox.GrabKeyboardFocus();
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

        TryStartCompletion(fromSpace: false);
    }

    /// <summary>
    /// Completes the typed verb prefix: a single match completes immediately, multiple
    /// matches extend to their longest common prefix and open the list. Returns false
    /// when there is nothing to complete (no prefix or no matches).
    /// </summary>
    private bool TryStartCompletion(bool fromSpace) {
        var prefix = _textBox.Text;
        if (string.IsNullOrWhiteSpace(prefix))
            return false;

        _entitySystems ??= IoCManager.Resolve<IEntitySystemManager>();
        if (!_entitySystems.TryGetEntitySystem<ClientVerbSystem>(out var verbSystem))
            return false;

        var matches = verbSystem.GetExecutableVerbs()
            .Select(verb => verb.VerbInfo.GetCommandName())
            .Where(name => name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            .Distinct()
            .Order(StringComparer.OrdinalIgnoreCase)
            .ToList();

        switch (matches.Count) {
            case 0:
                return false;
            case 1:
                // Completing via space leaves the verb ready for arguments
                ApplyCompletion(matches[0] + (fromSpace ? " " : ""));
                return true;
        }

        // Multiple matches: fill in as much as is unambiguous, then offer the list.
        var common = LongestCommonPrefix(matches);
        if (common.Length > prefix.Length)
            ApplyCompletion(common);

        _completionMatches = matches;
        _completionPrefix = common.Length > prefix.Length ? common : prefix;
        _completionIndex = 0; // The first entry starts selected
        ShowCompletionPopup(matches);
        return true;
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
                ConfirmCompletion();
            };

            _completionPopup = new Popup();
            _completionPopup.AddChild(_completionList);
            _uiManager.ModalRoot.AddChild(_completionPopup);
        }

        _completionList!.Clear();
        foreach (var match in matches) {
            _completionList.AddItem(match);
        }

        HighlightCompletion(0);

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

    /// <summary>
    /// A LineEdit that lets its owner intercept key functions (completion list navigation)
    /// before the text field acts on them.
    /// </summary>
    private sealed class CompletionLineEdit : LineEdit {
        public Func<GUIBoundKeyEventArgs, bool>? KeyBindInterceptor;
        public Func<GUITextEnteredEventArgs, bool>? TextInterceptor;

        protected override void KeyBindDown(GUIBoundKeyEventArgs args) {
            if (KeyBindInterceptor?.Invoke(args) == true) {
                args.Handle();
                return;
            }

            base.KeyBindDown(args);
        }

        protected override void TextEntered(GUITextEnteredEventArgs args) {
            if (TextInterceptor?.Invoke(args) == true)
                return;

            base.TextEntered(args);
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
