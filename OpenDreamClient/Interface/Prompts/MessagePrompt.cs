using System.Text;
using OpenDreamShared.Dream;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.Utility;

namespace OpenDreamClient.Interface.Prompts;

internal sealed class MessagePrompt : InputWindow {
    private readonly TextEdit _textEdit;

    public MessagePrompt(string title, string message, string defaultValue, bool canCancel,
        Action<DreamValueType, object?>? onClose) : base(title, message, canCancel, onClose) {
        _textEdit = new TextEdit {
            TextRope = new Rope.Leaf(defaultValue),

            // Select all the text by default
            CursorPosition = new TextEdit.CursorPos(defaultValue.Length, TextEdit.LineBreakBias.Bottom),
            SelectionStart = new TextEdit.CursorPos(0, TextEdit.LineBreakBias.Bottom)
        };

        SetPromptControl(_textEdit);
    }

    protected override void OkButtonClicked() {
        FinishPrompt(DreamValueType.Message, Rope.Collapse(_textEdit.TextRope));
    }

    protected override void TestDescribeInput(StringBuilder json) {
        PromptTestHook.AppendString(json, "text", Rope.Collapse(_textEdit.TextRope));
    }

    protected override string TestSetInput(string action, string argument) {
        if (action != "text")
            return base.TestSetInput(action, argument);
        _textEdit.TextRope = new Rope.Leaf(argument);
        return "text set";
    }
}
