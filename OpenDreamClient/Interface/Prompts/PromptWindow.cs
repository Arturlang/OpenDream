using System.ComponentModel;
using System.Text;
using System.Web;
using OpenDreamShared.Dream;
using Robust.Client.Graphics;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;

namespace OpenDreamClient.Interface.Prompts;

public abstract class PromptWindow : OSWindow {
    protected readonly Control InputControl;
    protected string DefaultButton = string.Empty;

    private readonly BoxContainer _buttonPanel;
    private bool _promptFinished;

    private readonly Action<DreamValueType, object?>? _closeAction;

    /// <summary>Set by <see cref="PromptTestHook"/>.</summary>
    public int TestId;

    private readonly string? _message;
    private readonly List<string> _buttonLabels = new();

    protected PromptWindow(string? title, string? message, Action<DreamValueType, object?>? onClose) {
        _closeAction = onClose;
        _message = message;
        PromptTestHook.Register(this);

        Title = !string.IsNullOrEmpty(title) ? title : "OpenDream";

        Label messageLabel = new Label();
        messageLabel.Margin = new Thickness(5);
        messageLabel.Text = message;

        _buttonPanel = new BoxContainer();
        _buttonPanel.Margin = new Thickness(5);
        _buttonPanel.Orientation = BoxContainer.LayoutOrientation.Horizontal;
        _buttonPanel.HorizontalAlignment = HAlignment.Right;
        _buttonPanel.VerticalAlignment = VAlignment.Bottom;

        InputControl = new Control {
            VerticalExpand = true
        };

        var dockPanel = new BoxContainer();
        dockPanel.Orientation = BoxContainer.LayoutOrientation.Vertical;
        dockPanel.Margin = new Thickness(5);
        dockPanel.Children.Add(messageLabel);
        dockPanel.Children.Add(InputControl);
        dockPanel.Children.Add(_buttonPanel);

        SizeToContent = WindowSizeToContent.WidthAndHeight;
        MinWidth = 300;
        MinHeight = 150;
        StartupLocation = WindowStartupLocation.CenterOwner;
        Closing += PromptWindow_Closing;
        WindowStyles = OSWindowStyles.NoTitleOptions;

        AddChild(dockPanel);
    }

    protected void CreateButton(string text, bool isDefault) {
        Button button = new Button() {
            Margin = new Thickness(15, 0, 0, 0),
            Children = { new Label { Text = text, Margin = new Thickness(5, 2, 5, 2) } }
        };

        if (isDefault)
            DefaultButton = text;

        button.OnPressed += _ => ButtonClicked(text);
        _buttonPanel.Children.Add(button);
        _buttonLabels.Add(text);
    }

    public void TestDescribe(StringBuilder json) {
        json.Append("{\"id\":").Append(TestId);
        PromptTestHook.AppendString(json, "type", GetType().Name);
        PromptTestHook.AppendString(json, "title", Title);
        PromptTestHook.AppendString(json, "message", _message);
        PromptTestHook.AppendString(json, "default_button", DefaultButton);
        json.Append(",\"buttons\":[");
        for (var i = 0; i < _buttonLabels.Count; i++) {
            if (i > 0)
                json.Append(',');
            json.Append('"').Append(HttpUtility.JavaScriptStringEncode(_buttonLabels[i])).Append('"');
        }

        json.Append(']');
        TestDescribeInput(json);
        json.Append('}');
    }

    protected virtual void TestDescribeInput(StringBuilder json) { }

    protected virtual string TestSetInput(string action, string argument) => $"{action} not supported by {GetType().Name}";

    public string TestAnswer(string action, string argument) {
        switch (action) {
            case "press":
                if (!_buttonLabels.Contains(argument))
                    return $"no button '{argument}'";
                ButtonClicked(argument);
                return "pressed";
            case "submit":
                ButtonClicked(DefaultButton);
                return "submitted";
            default:
                return TestSetInput(action, argument);
        }
    }

    protected virtual void ButtonClicked(string button) {
        Close();
    }

    protected void FinishPrompt(DreamValueType responseType, object? value) {
        if (_promptFinished) return;
        _promptFinished = true;
        PromptTestHook.Unregister(this);

        _closeAction?.Invoke(responseType, value);
    }

    private void PromptWindow_Closing(CancelEventArgs e) {
        //Don't allow closing if there hasn't been a response to the prompt
        if (!_promptFinished) {
            e.Cancel = true;
        } else {
            Owner = null;
        }
    }
}
