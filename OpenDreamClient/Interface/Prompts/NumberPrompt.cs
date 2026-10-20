using System.Text;
using OpenDreamShared.Dream;
using Robust.Client.UserInterface.Controls;

namespace OpenDreamClient.Interface.Prompts;

internal sealed class NumberPrompt : InputWindow {
    private readonly LineEdit _numberInput;

    public NumberPrompt(string title, string message, string defaultValue, bool canCancel,
        Action<DreamValueType, object?>? onClose) : base(title, message, canCancel, onClose) {
        _numberInput = new() {
            Text = defaultValue,
            VerticalAlignment = VAlignment.Top,
            IsValid = static str => float.TryParse(str, out float _),
        };

        _numberInput.OnTextEntered += NumberInput_TextEntered;
        SetPromptControl(_numberInput);
    }

    protected override void OkButtonClicked() {
        if (!float.TryParse(_numberInput.Text, out float num)) {
            Logger.GetSawmill("opendream.prompt").Error($"Error while trying to convert {_numberInput.Text} to a number.");
        }

        FinishPrompt(DreamValueType.Num, num);
    }

    private void NumberInput_TextEntered(LineEdit.LineEditEventArgs obj) {
        ButtonClicked(DefaultButton);
    }

    protected override void TestDescribeInput(StringBuilder json) {
        PromptTestHook.AppendString(json, "text", _numberInput.Text);
    }

    protected override string TestSetInput(string action, string argument) {
        if (action != "text")
            return base.TestSetInput(action, argument);
        // The IsValid filter can refuse the text.
        _numberInput.Text = argument;
        return _numberInput.Text == argument ? "text set" : $"text refused, now '{_numberInput.Text}'";
    }
}
