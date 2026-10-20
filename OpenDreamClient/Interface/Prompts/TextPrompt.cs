using System.Text;
using OpenDreamShared.Dream;
using Robust.Client.UserInterface.Controls;

namespace OpenDreamClient.Interface.Prompts;

internal sealed class TextPrompt : InputWindow {
    private readonly LineEdit _textEdit;

    public TextPrompt(string title, string message, string defaultValue, bool canCancel,
        Action<DreamValueType, object?>? onClose) : base(title, message, canCancel, onClose) {
        MinHeight = 100;

        _textEdit = new LineEdit {
            Text = defaultValue,
            VerticalAlignment = VAlignment.Top
        };

        _textEdit.OnTextEntered += TextEdit_TextEntered;
        SetPromptControl(_textEdit);
    }

    protected override void OkButtonClicked() {
        FinishPrompt(DreamValueType.Text, _textEdit.Text);
    }

    private void TextEdit_TextEntered(LineEdit.LineEditEventArgs e) {
        ButtonClicked(DefaultButton);
    }

    protected override void TestDescribeInput(StringBuilder json) {
        PromptTestHook.AppendString(json, "text", _textEdit.Text);
    }

    protected override string TestSetInput(string action, string argument) {
        if (action != "text")
            return base.TestSetInput(action, argument);
        _textEdit.Text = argument;
        return "text set";
    }
}
