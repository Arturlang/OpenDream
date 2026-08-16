using System.IO;
using System.Text;
using System.Globalization;
using System.Threading.Tasks;
using OpenDreamClient.Audio;
using OpenDreamShared.Network.Messages;
using OpenDreamClient.Interface.Controls;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using OpenDreamClient.Interface.Prompts;
using OpenDreamClient.Resources;
using OpenDreamClient.Resources.ResourceTypes;
using OpenDreamShared.Dream;
using Robust.Client;
using Robust.Client.Graphics;
using Robust.Client.Input;
using Robust.Client.UserInterface;
using Robust.Client.UserInterface.Controls;
using Robust.Shared.ContentPack;
using Robust.Shared.Network;
using Robust.Shared.Random;
using Robust.Shared.Asynchronous;
using Robust.Shared.Serialization.Manager;
using Robust.Shared.Timing;
using Robust.Shared.Utility;
using SixLabors.ImageSharp;
using System.Linq;
using System.Web;
using OpenDreamShared;
using Robust.Shared.Configuration;
using Robust.Shared.Map;

namespace OpenDreamClient.Interface;

internal sealed partial class DreamInterfaceManager : IDreamInterfaceManager {
    private static readonly ResPath DefaultInterfaceFile = new("/OpenDream/DefaultInterface.dmf");

    [Dependency] private IClyde _clyde = default!;
    [Dependency] private IBaseClient _client = default!;
    [Dependency] private IEyeManager _eyeManager = default!;
    [Dependency] private IClientNetManager _netManager = default!;
    [Dependency] private IDreamResourceManager _dreamResource = default!;
    [Dependency] private IResourceManager _resourceManager = default!;
    [Dependency] private IFileDialogManager _fileDialogManager = default!;
    [Dependency] private ISerializationManager _serializationManager = default!;
    [Dependency] private IEntitySystemManager _entitySystemManager = default!;
    [Dependency] private IInputManager _inputManager = default!;
    [Dependency] private IUserInterfaceManager _uiManager = default!;
    [Dependency] private IRobustRandom _random = default!;
    [Dependency] private ITimerManager _timerManager = default!;
    [Dependency] private IUriOpener _uriOpener = default!;
    [Dependency] private IConfigurationManager _cfg = default!;
    [Dependency] private IGameController _gameController = default!;
    [Dependency] private ITaskManager _taskManager = default!;
    [Dependency] private IDreamSoundEngine _soundEngine = default!;

    private readonly ISawmill _sawmill = Logger.GetSawmill("opendream.interface");

    public InterfaceDescriptor InterfaceDescriptor { get; private set; } = default!;

    public ControlWindow? DefaultWindow { get; private set; }
    public ControlOutput? DefaultOutput { get; private set; }
    public ControlInfo? DefaultInfo { get; private set; }
    public ControlMap? DefaultMap { get; private set; }

    public Dictionary<string, ControlWindow> Windows { get; } = new();
    public Dictionary<string, InterfaceMenu> Menus { get; } = new();
    public Dictionary<string, InterfaceMacroSet> MacroSets { get; } = new();
    private readonly HashSet<string> _pendingBrowseWindows = new();
    private readonly HashSet<string> _knownBrowseWindows = new();
    private readonly Dictionary<string, BrowsePopup> _browsePopups = new();
    private Dictionary<WindowId, ControlWindow> ClydeWindowIdToControl { get; } = new();
    public CursorHolder Cursors { get; private set; } = default!;

    public ViewRange View {
        get => _view;
        private set {
            // Cap to a view range of 45x45
            // Any larger causes crashes with RobustToolbox's GetPixel()
            if (value.Width > 45 || value.Height > 45)
                value = new(Math.Min(value.Width, 45), Math.Min(value.Height, 45));

            _view = value;
            DefaultMap?.UpdateViewRange(_view);
        }
    }

    public bool ShowPopupMenus { get; private set; } = true;
    public int IconSize { get; private set; }
    public MapFormat MapFormat { get; private set; }

    private ViewRange _view = new(5);

    public void LoadInterfaceFromSource(string source) {
        Reset();

        DMFLexer dmfLexer = new DMFLexer(source);
        DMFParser dmfParser = new DMFParser(dmfLexer, _serializationManager);
        InterfaceDescriptor interfaceDescriptor = dmfParser.Interface();

        if (dmfParser.Errors.Count > 0) {
            foreach (string error in dmfParser.Errors) {
                _sawmill.Error(error);
            }

            // Open an error message that disconnects from the server once closed
            OpenAlert(
                "Error",
                "Encountered error(s) while parsing interface source.\nCheck the console for details.",
                "Ok", null, null,
                (_, _) => _client.DisconnectFromServer("Errors while parsing interface"));

            return;
        }

        LoadInterface(interfaceDescriptor);
    }

    private void SetupBaseDreamBinds() {
        // Set up mouse buttons not covered by Robust's default use/right-click bindings
        var commonContext = _inputManager.Contexts.GetContext("common");
        commonContext.AddFunction(OpenDreamKeyFunctions.MouseMiddle);
        commonContext.AddFunction(OpenDreamKeyFunctions.MouseButton4);
        commonContext.AddFunction(OpenDreamKeyFunctions.MouseButton5);

        _inputManager.RegisterBinding(new KeyBindingRegistration {
            Function = OpenDreamKeyFunctions.MouseMiddle,
            BaseKey = Keyboard.Key.MouseMiddle
        });
        _inputManager.RegisterBinding(new KeyBindingRegistration {
            Function = OpenDreamKeyFunctions.MouseButton4,
            BaseKey = Keyboard.Key.MouseButton4
        });
        _inputManager.RegisterBinding(new KeyBindingRegistration {
            Function = OpenDreamKeyFunctions.MouseButton5,
            BaseKey = Keyboard.Key.MouseButton5
        });
    }

    public void Initialize() {
        SetupBaseDreamBinds();

        Cursors = new(_clyde);

        _netManager.RegisterNetMessage<MsgUpdateStatPanels>(RxUpdateStatPanels);
        _netManager.RegisterNetMessage<MsgSelectStatPanel>(RxSelectStatPanel);
        _netManager.RegisterNetMessage<MsgOutput>(RxOutput);
        _netManager.RegisterNetMessage<MsgAlert>(RxAlert);
        _netManager.RegisterNetMessage<MsgPrompt>(RxPrompt);
        _netManager.RegisterNetMessage<MsgPromptList>(RxPromptList);
        _netManager.RegisterNetMessage<MsgPromptResponse>();
        _netManager.RegisterNetMessage<MsgBrowse>(RxBrowse);
        _netManager.RegisterNetMessage<MsgTopic>();
        _netManager.RegisterNetMessage<MsgWinSet>(RxWinSet);
        _netManager.RegisterNetMessage<MsgWinClone>(RxWinClone);
        _netManager.RegisterNetMessage<MsgWinExists>(RxWinExists);
        _netManager.RegisterNetMessage<MsgWinGet>(RxWinGet);
        _netManager.RegisterNetMessage<MsgLink>(RxLink);
        _netManager.RegisterNetMessage<MsgFtp>(RxFtp);
        _netManager.RegisterNetMessage<MsgLoadInterface>(RxLoadInterface);
        _netManager.RegisterNetMessage<MsgAckLoadInterface>();
        _netManager.RegisterNetMessage<MsgUpdateClientInfo>(RxUpdateClientInfo);
        _clyde.OnWindowFocused += OnWindowFocused;
    }

    private void RunOnMainThread(Action callback) {
        _taskManager.RunOnMainThread(() => {
            try {
                callback();
            } catch (Exception e) {
                _sawmill.Error($"Exception while handling interface network message on the main thread: {e}");
            }
        });
    }

    private void RunOnMainThread(Func<Task> callback) {
        _taskManager.RunOnMainThread(() => {
            _ = RunAsyncCallback(callback);
        });
    }

    private async Task RunAsyncCallback(Func<Task> callback) {
        try {
            await callback();
        } catch (Exception e) {
            _sawmill.Error($"Exception while handling interface network message on the main thread: {e}");
        }
    }

    private void RxUpdateStatPanels(MsgUpdateStatPanels message) {
        RunOnMainThread(() => DefaultInfo?.UpdateStatPanels(message));
    }

    private void RxSelectStatPanel(MsgSelectStatPanel message) {
        var statPanel = message.StatPanel;
        RunOnMainThread(() => DefaultInfo?.SelectStatPanel(statPanel));
    }

    private void RxOutput(MsgOutput pOutput) {
        var control = pOutput.Control;
        var value = pOutput.Value;
        RunOnMainThread(() => Output(control, value));
    }

    private void RxAlert(MsgAlert message) {
        var title = message.Title;
        var body = message.Message;
        var button1 = message.Button1;
        var button2 = message.Button2;
        var button3 = message.Button3;
        var promptId = message.PromptId;

        RunOnMainThread(() => OpenAlert(
            title,
            body,
            button1, button2, button3,
            (responseType, response) => OnPromptFinished(promptId, responseType, response)));
    }

    public void OpenAlert(string title, string message, string button1, string? button2, string? button3, Action<DreamValueType, object?>? onClose) {
        var alert = new AlertWindow(
            title,
            message,
            button1, button2, button3,
            onClose);

        alert.Owner = _clyde.MainWindow;
        alert.Show();
    }

    private void RxPrompt(MsgPrompt pPrompt) {
        var types = pPrompt.Types;
        var title = pPrompt.Title;
        var message = pPrompt.Message;
        var defaultValue = pPrompt.DefaultValue;
        var promptId = pPrompt.PromptId;

        void OnPromptClose(DreamValueType responseType, object? response) {
            OnPromptFinished(promptId, responseType, response);
        }

        RunOnMainThread(() => Prompt(types, title, message, defaultValue, OnPromptClose));
    }

    private void RxPromptList(MsgPromptList pPromptList) {
        var title = pPromptList.Title;
        var message = pPromptList.Message;
        var defaultValue = pPromptList.DefaultValue;
        var canCancel = pPromptList.CanCancel;
        var values = pPromptList.Values;
        var promptId = pPromptList.PromptId;

        RunOnMainThread(() => {
            var prompt = new ListPrompt(
                title,
                message,
                defaultValue,
                canCancel,
                values,
                (responseType, response) => OnPromptFinished(promptId, responseType, response)
            );

            ShowPrompt(prompt);
        });
    }

    private void RxBrowse(MsgBrowse pBrowse) {
        var window = pBrowse.Window;
        var htmlSource = pBrowse.HtmlSource;
        var bodyData = pBrowse.BodyData;
        var size = pBrowse.Size;
        var file = pBrowse.File;
        var display = pBrowse.Display;

        if (display && window != null && (htmlSource != null || bodyData != null))
            _pendingBrowseWindows.Add(window);

        RunOnMainThread(() => Browse(window, htmlSource, bodyData, size, file, display));
    }

    private void Browse(string? windowId, string? htmlSource, byte[]? bodyData, Vector2i size, string? fileName = null, bool display = true) {
        BrowseInternal(windowId, htmlSource, bodyData, size, fileName, display);
    }

    private void BrowseInternal(string? windowId, string? htmlSource, byte[]? bodyData, Vector2i size, string? fileName = null, bool display = true) {
        var referencedElement = (windowId != null) ? FindElementWithId(windowId) : DefaultWindow;

        if (htmlSource == null && bodyData == null && referencedElement != null) {
            // Closing the referenced window or browser
            if (referencedElement is ControlWindow window) {
                if (windowId != null && _browsePopups.TryGetValue(windowId, out var popup)) {
                    popup.Close();
                } else {
                    window.CloseChildWindow();
                }
            } else if (referencedElement is ControlBrowser browser) {
                // TODO: What does "closing" the browser mean? Redirect to a blank page or remove the control entirely?
                browser.SetFileSource(null);
            }

            if (windowId != null)
                _pendingBrowseWindows.Remove(windowId);
            if (windowId != null)
                _knownBrowseWindows.Remove(windowId);
            if (windowId != null)
                _browsePopups.Remove(windowId);
        } else if (htmlSource != null || bodyData != null) {
            var htmlFileName = fileName ?? $"browse_{windowId}_{_random.Next()}.html"; // TODO: Possible collisions
            var cacheFile = bodyData != null
                ? _dreamResource.CreateCacheFile(htmlFileName, bodyData)
                : _dreamResource.CreateCacheFile(htmlFileName, htmlSource!);
            if (!display) {
                if (windowId != null) {
                    _pendingBrowseWindows.Remove(windowId);
                    _knownBrowseWindows.Remove(windowId);
                    _browsePopups.Remove(windowId);
                }

                return;
            }

            ControlBrowser? outputBrowser = referencedElement as ControlBrowser;

            if (outputBrowser == null) {
                if (referencedElement is ControlWindow window) {
                    outputBrowser = null;

                    // Find a browser within this window
                    foreach (var childControl in window.ChildControls) {
                        if (childControl is not ControlBrowser browser)
                            continue;

                        outputBrowser = browser;
                        break;
                    }
                } else if (windowId != null) {
                    // Creating a new popup
                    var popup = new BrowsePopup(windowId, size);
                    popup.Closed += () => {
                        Windows.Remove(windowId);
                        _pendingBrowseWindows.Remove(windowId);
                        _knownBrowseWindows.Remove(windowId);
                        _browsePopups.Remove(windowId);
                    };

                    outputBrowser = popup.Browser;
                    _knownBrowseWindows.Add(windowId);
                    _browsePopups[windowId] = popup;
                    Windows.Add(windowId, popup.WindowElement);
                    popup.Open();
                }
            }

            if (outputBrowser == null) {
                if (windowId != null) {
                    _pendingBrowseWindows.Remove(windowId);
                    _knownBrowseWindows.Remove(windowId);
                    _browsePopups.Remove(windowId);
                }

                _sawmill.Error($"Failed to find a browser element in window \"{windowId}\" to browse()");
                return;
            }

            outputBrowser.SetFileSource(cacheFile);
        }
    }

    private void RxWinSet(MsgWinSet message) {
        var controlId = message.ControlId;
        var winsetParams = message.Params;
        RunOnMainThread(() => WinSet(controlId, winsetParams));
    }

    private void RxWinClone(MsgWinClone message) {
        var controlId = message.ControlId;
        var cloneId = message.CloneId;
        RunOnMainThread(() => WinClone(controlId, cloneId));
    }

    private void RxWinExists(MsgWinExists message) {
        var controlId = message.ControlId;
        var promptId = message.PromptId;

        RunOnMainThread(() => {
            InterfaceElement? element = FindElementWithId(controlId);
            bool browseWindow = _pendingBrowseWindows.Contains(controlId) || _knownBrowseWindows.Contains(controlId);
            bool pendingBrowseWindow = element == null && browseWindow;
            MsgPromptResponse response = new() {
                PromptId = promptId,
                Type = DreamValueType.Text,
                Value = element?.Type.Value ?? (pendingBrowseWindow ? "MAIN" : string.Empty)
            };

            _netManager.ClientSendMessage(response);
        });
    }

    private void RxWinGet(MsgWinGet message) {
        var controlId = message.ControlId;
        var queryValue = message.QueryValue;
        var promptId = message.PromptId;

        // Run this later to ensure any pending UI measurements have occured
        RunOnMainThread(() => _timerManager.AddTimer(new Timer(100, false, () => {
            MsgPromptResponse response = new() {
                PromptId = promptId,
                Type = DreamValueType.Text,
                Value = WinGet(controlId, queryValue, forceSnowflake:true)
            };

            _netManager.ClientSendMessage(response);
        })));
    }

    private void RxLink(MsgLink message) {
        var url = message.Url;
        RunOnMainThread(() => Link(url));
    }

    private void Link(string url) {
        Uri uri;
        try {
            uri = new Uri(url);
        } catch (Exception e) {
            _sawmill.Error($"Received link \"{url}\" which failed to parse as a valid URI: {e.Message}");
            return;
        }

        // TODO: This can be a topic call

        if (uri.Scheme is "http" or "https") {
            _uriOpener.OpenUri(url);
        } else if (uri.Scheme is "ss14" or "ss14s") {
            if (_gameController.LaunchState.FromLauncher)
                _gameController.Redial(url, "link() used to connect to another server.");
            else
                _sawmill.Warning("link() only supports connecting to other servers when utilizing the launcher. Ignoring.");
        } else {
            _sawmill.Warning($"Received link \"{url}\" which is not supported. Ignoring.");
        }
    }

    private void RxFtp(MsgFtp message) {
        var resourceId = message.ResourceId;
        _dreamResource.LoadResourceAsync<DreamResource>(resourceId, resource => {
            RunOnMainThread(async () => {
                // TODO: Default the filename to message.SuggestedName
                // RT doesn't seem to support this currently
                var tuple = await _fileDialogManager.SaveFile();
                if (tuple == null) // User cancelled
                    return;

                await using var file = tuple.Value.fileStream;
                resource.WriteTo(file);
            });
        });
    }

    private void RxLoadInterface(MsgLoadInterface message) {
        var interfaceText = message.InterfaceText;
        RunOnMainThread(() => LoadInterface(interfaceText));
    }

    private void LoadInterface(string? interfaceText) {
        if (interfaceText == null) {
            if (!_resourceManager.TryContentFileRead(DefaultInterfaceFile.CanonPath, out var defaultInterface)) {
                // Open an error message that disconnects from the server once closed
                OpenAlert(
                    "Error",
                    "The server did not provide an interface and there is no default interface in the resources folder.",
                    "Ok", null, null,
                    (_, _) => _client.DisconnectFromServer("No interface to use"));

                return;
            }

            using var defaultInterfaceReader = new StreamReader(defaultInterface);
            interfaceText = defaultInterfaceReader.ReadToEnd();
        }

        LoadInterfaceFromSource(interfaceText);
        _netManager.ClientSendMessage(new MsgAckLoadInterface());
    }

    private void RxUpdateClientInfo(MsgUpdateClientInfo msg) {
        var iconSize = msg.IconSize;
        var view = msg.View;
        var mapFormat = msg.MapFormat;
        var showPopupMenus = msg.ShowPopupMenus;
        var cursorResource = msg.CursorResource;

        RunOnMainThread(() => UpdateClientInfo(iconSize, view, mapFormat, showPopupMenus, cursorResource));
    }

    private void UpdateClientInfo(int iconSize, ViewRange view, MapFormat mapFormat, bool showPopupMenus, int cursorResource) {
        IconSize = iconSize;
        View = view;
        MapFormat = mapFormat;
        ShowPopupMenus = showPopupMenus;
        if (cursorResource != 0)
            _dreamResource.LoadResourceAsync<DMIResource>(cursorResource, resource => {
                RunOnMainThread(() => {
                    //TODO should trigger a cursor update immediately
                    Cursors = new(_clyde, resource);
                });
            });
        else {
            Cursors = new(_clyde); //reset to default
        }
    }

    private void ShowPrompt(PromptWindow prompt) {
        prompt.Owner = _clyde.MainWindow;
        prompt.Show();
    }

    public void FrameUpdate(FrameEventArgs frameEventArgs) {
        var currentEye = _eyeManager.CurrentEye;

        foreach (ControlWindow window in Windows.Values) {
            foreach (InterfaceControl control in window.ChildControls) {
                if (control is ControlMap { Viewport.Visible: true } controlMap)
                    controlMap.Viewport.Eye = currentEye;
            }
        }

        foreach (var popup in _browsePopups.Values) {
            popup.ProcessNativeDrag();
        }
    }

    public InterfaceElement? FindElementWithId(string id) {
        string[] split = id.Split(".");

        if (split.Length == 2) {
            string windowId = split[0];
            string elementId = split[1];
            ControlWindow? window = null;

            if (Windows.ContainsKey(windowId)) {
                window = Windows[windowId];
            } else if (Menus.TryGetValue(windowId, out var menu)) {
                if (menu.MenuElementsById.TryGetValue(elementId, out var menuElement))
                    return menuElement;
            } else if(MacroSets.TryGetValue(windowId, out var macroSet)) {
                if (macroSet.Macros.TryGetValue(elementId, out var macroElement))
                    return macroElement;
            }

            if (window != null) {
                foreach (InterfaceControl element in window.ChildControls) {
                    if (element.Id.Value == elementId) return element;
                }
            }
        } else {
            string elementId = split[0];

            // ":[element]" returns the default element of that type
            switch (elementId) {
                case ":map":
                    return DefaultMap;
                case ":info":
                    return DefaultInfo;
                case ":window":
                    return DefaultWindow;
                case ":output":
                    return DefaultOutput;
            }

            foreach (ControlWindow window in Windows.Values) {
                if (window.Id.Value == elementId)
                    return window;

                foreach (InterfaceControl element in window.ChildControls) {
                    if (element.Id.Value == elementId) return element;
                }
            }

            foreach (InterfaceMenu menu in Menus.Values) {
                if (menu.Id.Value == elementId)
                    return menu;

                if (menu.MenuElementsById.TryGetValue(elementId, out var menuElement))
                    return menuElement;
            }

            foreach (var macroSet in MacroSets.Values) {
                if (macroSet.Id.Value == elementId)
                    return macroSet;

                if (macroSet.Macros.TryGetValue(elementId, out var macroElement))
                    return macroElement;
            }
        }

        return null;
    }

    public void SaveScreenshot(bool openDialog) {
        // ReSharper disable once AsyncVoidLambda
        DefaultMap?.Viewport.Screenshot(async img => {
            //TODO: Support automatically choosing a location if openDialog == false
            var filters = new FileDialogFilters(new FileDialogFilters.Group("png"));
            var tuple = await _fileDialogManager.SaveFile(filters);
            if (tuple == null)
                return;

            await using var file = tuple.Value.fileStream;
            await img.SaveAsPngAsync(file);
        });
    }

    public void Prompt(DreamValueType types, string title, string message, string defaultValue, Action<DreamValueType, object?>? onClose) {
        PromptWindow? prompt = null;
        bool canCancel = (types & DreamValueType.Null) == DreamValueType.Null;

        if ((types & DreamValueType.Text) == DreamValueType.Text) {
            prompt = new TextPrompt(title, message, defaultValue, canCancel, onClose);
        } else if ((types & DreamValueType.Num) == DreamValueType.Num) {
            prompt = new NumberPrompt(title, message, defaultValue, canCancel, onClose);
        } else if ((types & DreamValueType.Message) == DreamValueType.Message) {
            prompt = new MessagePrompt(title, message, defaultValue, canCancel, onClose);
        } else if ((types & DreamValueType.Color) == DreamValueType.Color) {
            prompt = new ColorPrompt(title, message, defaultValue, canCancel, onClose);
        }

        if (prompt != null) {
            ShowPrompt(prompt);
        }
    }

    private void HandleBrowserOptions(string options) {
        foreach (string rawOption in DecodeBrowserOptions(options).Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)) {
            string option = rawOption.TrimStart('+', '-');

            switch (option) {
                // CEF already has page storage for the local browser origin, and OpenDream renders browser
                // chrome through its own controls instead of BYOND's browser toolbar.
                case "byondstorage":
                case "find":
                case "refresh":
                    break;
                default:
                    _sawmill.Error($"Unsupported browser-options winset \"{options}\"");
                    return;
            }
        }
    }

    private static string DecodeBrowserOptions(string options) {
        return options
            .Replace("%2c", ",", StringComparison.OrdinalIgnoreCase)
            .Replace("%2b", "+", StringComparison.OrdinalIgnoreCase)
            .Replace("%2d", "-", StringComparison.OrdinalIgnoreCase);
    }

    public void RunCommand(string fullCommand, bool repeating = false, NetEntity? atomContext = null, string? atomRefContext = null) {
        switch (fullCommand) {
            case not null when fullCommand.StartsWith(".quit"):
                _gameController.Shutdown(".quit used");
                break;

            case not null when fullCommand.StartsWith(".screenshot"):
                string[] split = fullCommand.Split(" ");
                SaveScreenshot(split.Length == 1 || split[1] != "auto");
                break;

            case not null when fullCommand.StartsWith(".configure"):
                _sawmill.Warning(".configure command is not implemented");
                break;

            case not null when fullCommand.StartsWith(".winset"):
                // Everything after .winset, excluding the space and quotes
                string winsetParams = fullCommand.Substring(7); //clip .winset
                winsetParams = winsetParams.Trim(); //clip space
                if (winsetParams.StartsWith('"') && winsetParams.EndsWith('"'))
                    winsetParams = winsetParams.Substring(1, winsetParams.Length - 2); //clip quotes

                WinSet(null, winsetParams);
                break;

            case not null when fullCommand.StartsWith(".output"): {
                string[] args = fullCommand.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                if (args.Length != 3) {
                    _sawmill.Error($".output command was executed with {args.Length - 1} args instead of 2");
                    break;
                }

                Output(args[1], args[2]);
                break;
            }

            case not null when fullCommand.StartsWith(".sound"): {
                var soundCommandText = fullCommand[6..].Trim();
                if (!SoundCommandParser.TryParse(soundCommandText, out var soundCommand, out var error, atomContext, atomRefContext)) {
                    _sawmill.Error($".sound command failed: {error}");
                    break;
                }

                if (soundCommand.Stop) {
                    if (soundCommand.SoundData.Channel == 0)
                        _soundEngine.StopAllChannels();
                    else
                        _soundEngine.StopChannel(soundCommand.SoundData.Channel);
                } else if (soundCommand is { ResourcePath: not null, Format: not null }) {
                    _soundEngine.PlaySound(soundCommand.SoundData, soundCommand.Format.Value, soundCommand.ResourcePath);
                }

                break;
            }

            default: {
                string[] argsRaw = fullCommand!.Split(' ', 2, StringSplitOptions.TrimEntries);
                string command = argsRaw[0].ToLowerInvariant(); // Case-insensitive

                if (!_entitySystemManager.TryGetEntitySystem(out ClientVerbSystem? verbSystem))
                    return;
                var ret = verbSystem.FindVerbWithCommandName(command);
                if (ret is not var (verbId, verbSrc, verbInfo))
                    return;

                if (argsRaw.Length == 1) { // No args given; Let the verb system handle the possible prompting
                    if (repeating) {
                        verbSystem.StartRepeatingVerb(verbSrc, verbId);
                    } else {
                        verbSystem.ExecuteVerb(verbSrc, verbId);
                    }
                } else { // Attempt to parse the given arguments
                    List<string> args = new List<string>();
                    StringBuilder currentArg = new();
                    bool stringCapture = false;
                    for (int i = 0; i < argsRaw[1].Length; i++) {
                        if (argsRaw[1][i] == '"') {
                            currentArg.Append('"');
                            if (stringCapture) {
                                var result = HandleEmbeddedWinget(null, currentArg.ToString(), out var hadWinget);

                                // 64x64 or 64,64 gets split into two "64 64" args
                                if (hadWinget && result.Split(['x', ',']) is {Length: 2} wingetSplit &&
                                    float.TryParse(wingetSplit[0], out _) && float.TryParse(wingetSplit[1], out _)) {
                                    args.Add(wingetSplit[0]);
                                    args.Add(wingetSplit[1]);
                                } else {
                                    args.Add(result);
                                }

                                currentArg.Clear();
                            }

                            stringCapture = !stringCapture;
                            continue;
                        }

                        if (argsRaw[1][i] == ' ' && !stringCapture) {
                            var result = HandleEmbeddedWinget(null, currentArg.ToString(), out var hadWinget);

                            // 64x64 or 64,64 gets split into two "64 64" args
                            if (hadWinget && result.Split(['x', ',']) is {Length: 2} wingetSplit &&
                                float.TryParse(wingetSplit[0], out _) && float.TryParse(wingetSplit[1], out _)) {
                                args.Add(wingetSplit[0]);
                                args.Add(wingetSplit[1]);
                            } else {
                                args.Add(result);
                            }

                            currentArg.Clear();
                            continue;
                        }

                        currentArg.Append(argsRaw[1][i]);
                    }

                    if (currentArg.ToString() is { } arg && !string.IsNullOrEmpty(arg)) {
                        var result = HandleEmbeddedWinget(null, arg, out var hadWinget);

                        // 64x64 or 64,64 gets split into two "64 64" args
                        if (hadWinget && result.Split(['x', ',']) is {Length: 2} wingetSplit &&
                            float.TryParse(wingetSplit[0], out _) && float.TryParse(wingetSplit[1], out _)) {
                            args.Add(wingetSplit[0]);
                            args.Add(wingetSplit[1]);
                        } else {
                            args.Add(result);
                        }
                    }

                    if (args.Count != verbInfo.Arguments.Length) {
                        _sawmill.Error(
                            $"Attempted to call a verb with {verbInfo.Arguments.Length} argument(s) with only {args.Count}: {fullCommand}");
                        return;
                    }

                    var arguments = new object?[verbInfo.Arguments.Length];
                    for (int i = 0; i < verbInfo.Arguments.Length; i++) {
                        DreamValueType argumentType = verbInfo.Arguments[i].Types;

                        if (argumentType is DreamValueType.Text or DreamValueType.Message or DreamValueType.CommandText) {
                            arguments[i] = args[i];
                        } else if (argumentType == DreamValueType.Num) {
                            if (!float.TryParse(args[i], out var numArg)) {
                                _sawmill.Error(
                                    $"Invalid number argument \"{args[i]}\"; ignoring command ({fullCommand})");
                                return;
                            }

                            arguments[i] = numArg;
                        } else {
                            _sawmill.Error($"Parsing verb args of type {argumentType} is unimplemented; ignoring command ({fullCommand})");
                            return;
                        }
                    }

                    verbSystem.ExecuteVerb(verbSrc, verbId, arguments);
                }

                break;
            }
        }
    }

    public void StopRepeatingCommand(string command) {
        string[] argsRaw = command.Split(' ', 2, StringSplitOptions.TrimEntries);
        string parsedCommand = argsRaw[0].ToLowerInvariant(); // Case-insensitive

        if (!_entitySystemManager.TryGetEntitySystem(out ClientVerbSystem? verbSystem))
            return;
        var ret = verbSystem.FindVerbWithCommandName(parsedCommand);
        if (ret is not var (verbId, verbSrc, _))
            return;
        verbSystem.StopRepeatingVerb(verbSrc, verbId);
    }

    public string HandleEmbeddedWinget(string? controlId, string value, out bool hadWinget) {
        hadWinget = false;

        string result = value;
        int startPos = result.IndexOf("[[", StringComparison.Ordinal);
        while(startPos > -1){
            int endPos = result.IndexOf("]]", startPos, StringComparison.Ordinal);
            if(endPos == -1)
                break;
            string inner = result.Substring(startPos+2, endPos-startPos-2);
            string[] elementSplit = inner.Split('.');
            string innerControlId = controlId ?? "";
            if(elementSplit.Length > 1){
                innerControlId = (string.IsNullOrEmpty(innerControlId) ? "" : innerControlId+".")+string.Join(".", elementSplit[..^1]);
                inner = elementSplit[^1];
            }

            string innerResult = WinGet(innerControlId, inner);
            hadWinget = true;
            result = result.Substring(0, startPos) + innerResult + result.Substring(endPos+2);
            startPos = result.IndexOf("[[", StringComparison.Ordinal);
        }

        return result;
    }

    public void WinSet(string? controlId, string winsetParams) {
        DMFParser parser;
        try{
            var lexer = new DMFLexer(winsetParams);
            parser = new DMFParser(lexer, _serializationManager);
        } catch (Exception e) {
            _sawmill.Error($"Error parsing winset: {e}");
            return;
        }

        bool CheckParserErrors() {
            if (parser.Errors.Count <= 0)
                return false;

            foreach (string error in parser.Errors) {
                _sawmill.Error(error);
            }

            return true;
        }

        if (string.IsNullOrEmpty(controlId)) {
            List<DMFWinSet> winSets = parser.GlobalWinSet();

            if (CheckParserErrors())
                return;

            // id=abc overrides the elements of other winsets without an element
            string? elementOverride = winSets.FirstOrDefault(winSet => winSet.Element == null && winSet.Attribute == "id")?.Value;

            foreach (DMFWinSet winSet in winSets) {
                if (winSet.Attribute == "id") // This is used to set the target, not an actual winset
                    continue;

                string? elementId = winSet.Element ?? elementOverride;
                if (string.IsNullOrEmpty(elementId))
                    elementId = null;

                if (elementId == null) {
                    if (winSet.Attribute == "command") {
                        RunCommand(HandleEmbeddedWinget(controlId, winSet.Value, out _));
                    } else if (winSet.Attribute == "browser-options") {
                        HandleBrowserOptions(winSet.Value);
                    } else {
                        _sawmill.Error($"Invalid global winset \"{winsetParams}\"");
                    }
                } else {
                    if(winSet.TrueStatements is not null) {
                        InterfaceElement? conditionalElement = FindElementWithId(elementId);
                        if(conditionalElement is null)
                            _sawmill.Error($"Invalid element on ternary condition \"{elementId}\"");
                        else
                            if(conditionalElement.TryGetProperty(winSet.Attribute, out var conditionalCheckValue) && conditionalCheckValue.Equals(winSet.Value)) {
                                foreach(DMFWinSet statement in winSet.TrueStatements) {
                                    string statementElementId = statement.Element ?? elementId;
                                    InterfaceElement? statementElement = FindElementWithId(statementElementId);
                                    if (_browsePopups.TryGetValue(statementElementId, out var statementPopup)) {
                                        statementPopup.SetProperty(statement.Attribute, HandleEmbeddedWinget(statementElementId, statement.Value, out _));
                                    } else if(statementElement is not null) {
                                        statementElement.SetProperty(statement.Attribute, HandleEmbeddedWinget(statementElementId, statement.Value, out _), manualWinset: true);
                                    } else {
                                        _sawmill.Error($"Invalid element on ternary \"{statementElementId}\"");
                                    }
                                }
                            } else if (winSet.FalseStatements is not null){
                                foreach(DMFWinSet statement in winSet.FalseStatements) {
                                    string statementElementId = statement.Element ?? elementId;
                                    InterfaceElement? statementElement = FindElementWithId(statementElementId);
                                    if (_browsePopups.TryGetValue(statementElementId, out var statementPopup)) {
                                        statementPopup.SetProperty(statement.Attribute, HandleEmbeddedWinget(statementElementId, statement.Value, out _));
                                    } else if(statementElement is not null) {
                                        statementElement.SetProperty(statement.Attribute, HandleEmbeddedWinget(statementElementId, statement.Value, out _), manualWinset: true);
                                    } else {
                                        _sawmill.Error($"Invalid element on ternary \"{statementElementId}\"");
                                    }
                                }
                            }
                    } else {
                        InterfaceElement? element = FindElementWithId(elementId);

                        if (_browsePopups.TryGetValue(elementId, out var popup)) {
                            popup.SetProperty(winSet.Attribute, HandleEmbeddedWinget(elementId, winSet.Value, out _));
                        } else if (element != null) {
                            element.SetProperty(winSet.Attribute, HandleEmbeddedWinget(elementId, winSet.Value, out _), manualWinset: true);
                        } else {
                            _sawmill.Error($"Invalid element \"{elementId}\"");
                        }
                    }
                }
            }
        } else {
            InterfaceElement? element = FindElementWithId(controlId);
            var attributes = parser.AttributesValues();

            if (CheckParserErrors())
                return;

            if (attributes.TryGetValue("parent", out var parentId) && string.IsNullOrEmpty(parentId)) {
                // BYOND uses parent="" to detach/remove an element. If the element was already
                // gone, there is nothing left to do.
                if (element == null)
                    return;

                RemoveElement(element);
            } else if (element == null && attributes.TryGetValue("parent", out parentId)) {
                var parent = FindElementWithId(parentId);
                if (parent == null) {
                    _sawmill.Error($"Attempted to create an element with nonexistent parent \"{parentId}\" ({winsetParams})");
                    return;
                }

                attributes["id"] = controlId;
                var childDescriptor = parent.ElementDescriptor.CreateChildDescriptor(_serializationManager, attributes);
                if (childDescriptor == null)
                    return;

                parent.AddChild(childDescriptor);
            } else if (element != null) {
                foreach (var attribute in attributes) {
                    if (_browsePopups.TryGetValue(controlId, out var popup))
                        popup.SetProperty(attribute.Key, attribute.Value);
                    else
                        element.SetProperty(attribute.Key, attribute.Value, manualWinset: true);
                }
            } else {
                if (string.IsNullOrEmpty(controlId))
                    _sawmill.Error($"Invalid element \"{controlId}\"");
                else
                    _sawmill.Error($"Invalid element \"{controlId}\"");
            }
        }
    }

    private bool RemoveElement(InterfaceElement element) {
        if (element is not InterfaceControl control)
            return false;

        foreach (var window in Windows.Values) {
            if (window.RemoveChild(control))
                return true;
        }

        return false;
    }

    public string WinGet(string controlId, string queryValue, bool forceJson = false, bool forceSnowflake = false) {
        bool ParseAndTryGet(InterfaceElement element, string query, out string result) {
            //parse "as blah" from query if it's there
            string[] querySplit = query.Split(" as ");
            IDMFProperty propResult;
            if(querySplit.Length != 2) //must be "thing as blah" or "thing". Anything else is invalid.
                if(element.TryGetProperty(query, out propResult!)){
                    result = forceJson ? propResult.AsJson() : forceSnowflake ? propResult.AsSnowflake() : propResult.AsRaw();
                    return true;
                } else {
                    result = "";
                    return false;
                }
            else{
                if(!element.TryGetProperty(querySplit[0], out propResult!)) {
                    result = "";
                    return false;
                }

                if (forceJson) {
                    result = propResult.AsJson();
                    return true;
                } else if (forceSnowflake) {
                    result = propResult.AsSnowflake();
                    return true;
                }

                switch(querySplit[1]){
                    case "arg":
                        result = propResult.AsArg();
                        break;
                    case "escaped":
                        result = propResult.AsEscaped();
                        break;
                    case "string":
                        result = propResult.AsString();
                        break;
                    case "params":
                        result = propResult.AsParams();
                        break;
                    case "json":
                        result = propResult.AsJson();
                        break;
                    case "json-dm":
                        result = propResult.AsJsonDM();
                        break;
                    case "raw":
                        result = propResult.AsRaw();
                        break;
                    default:
                        _sawmill.Error($"Invalid winget query function \"{querySplit[1]}\" in \"{query}\"");
                        result = "";
                        return false;
                }

                return true;
            }
        }

        string GetProperty(string elementId) {
            if (_browsePopups.TryGetValue(elementId, out var popup)) {
                string FormatPopupProperty(IDMFProperty? property) {
                    if (property == null)
                        return string.Empty;

                    // forceJson must be honoured here like everywhere else in WinGet.
                    // TGUI windows are browse popups, and TGUI boots with winget(id, "pos")
                    // expecting JSON - returning AsRaw() here handed "400,120" to a caller
                    // that splices the result into a JS object literal, which is a syntax
                    // error the page can only see as a masked "Script error." at :0.
                    if (forceJson)
                        return property.AsJson();

                    return forceSnowflake ? property.AsSnowflake() : property.AsRaw();
                }

                var popupMultiQuery = queryValue.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
                if (popupMultiQuery.Length > 1) {
                    var result = "";
                    foreach (var query in popupMultiQuery) {
                        if (!popup.TryGetProperty(query, out var queryResult))
                            _sawmill.Error($"Could not winget property {query} on browse popup {elementId}");

                        result += query + "=" + FormatPopupProperty(queryResult) + ";";
                    }

                    return result.TrimEnd(';');
                }

                if (popup.TryGetProperty(queryValue, out var value))
                    return FormatPopupProperty(value);

                _sawmill.Error($"Could not winget property {queryValue} on browse popup {elementId}");
                return string.Empty;
            }

            var element = FindElementWithId(elementId);
            if (element == null) {
                _sawmill.Error($"Could not winget element {elementId} because it does not exist");
                return string.Empty;
            }

            var multiQuery = queryValue.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if(multiQuery.Length > 1) {
                var result = "";
                foreach(var query in multiQuery) {
                    if (!ParseAndTryGet(element, query, out var queryResult))
                        _sawmill.Error($"Could not winget property {query} on {element.Id}");
                    result += query+"="+queryResult + ";";
                }

                return result.TrimEnd(';');
            } else if (ParseAndTryGet(element, queryValue, out var value))
                return value;

            _sawmill.Error($"Could not winget property {queryValue} on {element.Id}");
            return string.Empty;
        }

        string GetAllProperties(string elementId, bool includeElementPrefix, bool jsonValuesAsRawStrings = false) {
            var element = FindElementWithId(elementId);
            if (element == null) {
                _sawmill.Error($"Could not winget element {elementId} because it does not exist");
                return forceJson ? "{}" : string.Empty;
            }

            if (forceJson) {
                var properties = element
                    .EnumerateProperties()
                    .Select(pair => (includeElementPrefix ? $"{elementId}.{pair.Name}" : pair.Name, pair.Value));

                return BrowserBridgeJson.EncodePropertyMap(properties, jsonValuesAsRawStrings);
            }

            var result = new StringBuilder();
            foreach (var (name, value) in element.EnumerateProperties()) {
                if (result.Length > 0)
                    result.Append(';');

                result.Append(includeElementPrefix ? $"{elementId}.{name}" : name);
                result.Append('=');
                result.Append(forceSnowflake ? value.AsSnowflake() : value.AsRaw());
            }

            return result.ToString();
        }

        IEnumerable<string> ExpandElementId(string elementId) {
            if (!elementId.EndsWith(".*", StringComparison.Ordinal))
                return [elementId];

            var parentId = elementId[..^2];
            if (Windows.TryGetValue(parentId, out var window))
                return window.ChildControls.Select(control => $"{parentId}.{control.Id.Value}");

            if (Menus.TryGetValue(parentId, out var menu))
                return menu.MenuElementsById.Keys.Select(menuElementId => $"{parentId}.{menuElementId}");

            if (MacroSets.TryGetValue(parentId, out var macroSet))
                return macroSet.Macros.Keys.Select(macroId => $"{parentId}.{macroId}");

            _sawmill.Error($"Could not winget wildcard element {elementId} because {parentId} does not exist");
            return [];
        }

        var elementIds = controlId
            .Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .SelectMany(ExpandElementId)
            .ToArray();

        if (queryValue == "*") {
            if (elementIds.Length == 0)
                return forceJson ? "{}" : string.Empty;
            if (elementIds.Length == 1)
                return GetAllProperties(elementIds[0], includeElementPrefix: false, jsonValuesAsRawStrings: forceJson);

            if (forceJson) {
                var json = new StringBuilder();
                json.Append('{');

                foreach (var elementId in elementIds) {
                    var elementJson = GetAllProperties(elementId, includeElementPrefix: true, jsonValuesAsRawStrings: true);
                    if (elementJson.Length <= 2)
                        continue;

                    if (json.Length > 1)
                        json.Append(',');

                    json.Append(elementJson.Substring(1, elementJson.Length - 2));
                }

                json.Append('}');
                return json.ToString();
            }

            var allProperties = new StringBuilder();
            foreach (var elementId in elementIds) {
                var elementResult = GetAllProperties(elementId, includeElementPrefix: true);
                if (string.IsNullOrEmpty(elementResult))
                    continue;

                if (allProperties.Length > 0)
                    allProperties.Append(';');

                allProperties.Append(elementResult);
            }

            return allProperties.ToString();
        }

        if (elementIds.Length == 0) {
            var queryResult = queryValue switch {
                // The server will actually never query this because it can predict the answer to be "true"
                // But also have it here in case a local winget ever wants it
                "hwmode" => "true",
                "windows" => string.Join(';',
                        Windows.Where(pair => !pair.Value.WindowDescriptor.IsPane.Value).Select(pair => pair.Key)),
                "panes" => string.Join(';',
                        Windows.Where(pair => pair.Value.WindowDescriptor.IsPane.Value).Select(pair => pair.Key)),
                "menus" => string.Join(';', Menus.Keys),
                "macros" => string.Join(';', MacroSets.Keys),
                "url" => _netManager.ServerChannel?.RemoteEndPoint.ToString() ?? string.Empty, // TODO: Port should be 0 "if connected to a local .dmb file"
                "dpi" => (_clyde.DefaultWindowScale.X.ToString(CultureInfo.InvariantCulture)),
                _ => null
            };

            if (queryResult is null) {
                _sawmill.Error($"Special winget \"{queryValue}\" is not implemented");
                return string.Empty;
            } else {
                return forceJson ? $"\"{HttpUtility.JavaScriptStringEncode(queryResult)}\"" : queryResult;
            }
        } else if (elementIds.Length == 1) {
            return GetProperty(elementIds[0]);
        }

        var result = new StringBuilder(elementIds.Length * 6 - 1);

        for (int i = 0; i < elementIds.Length; i++) {
            var elementId = elementIds[i];

            result.Append(elementId);
            result.Append('.');
            result.Append(queryValue);
            result.Append('=');
            result.Append(GetProperty(elementId));

            if (i != elementIds.Length - 1)
                result.Append(';');
        }

        return result.ToString();
    }

    public void Output(string? control, string value) {
        InterfaceControl? interfaceElement;
        string? data = null;

        if (control != null) {
            string[] split = control.Split(":");

            interfaceElement = (InterfaceControl?)FindElementWithId(split[0]);
            if (interfaceElement == null &&
                split[0].EndsWith(".browser", StringComparison.Ordinal)) {
                string browserControlId = split[0][..^".browser".Length];
                if (FindElementWithId(browserControlId) is ControlBrowser browser) {
                    interfaceElement = browser;
                }
            }

            if (split.Length > 1) data = split[1];
        } else {
            interfaceElement = DefaultOutput;
        }

        if (interfaceElement == null) {
            // Silently dropping these hides real failures: TGUI delivers its entire payload
            // through output() to "<id>.browser:update", so one unresolved id leaves the
            // interface with no data at all.
            _sawmill.Error($"Could not output to \"{control}\" because no such element exists");
            return;
        }

        interfaceElement.Output(value, data);
    }

    public void WinClone(string controlId, string cloneId) {
        ElementDescriptor? elementDescriptor = InterfaceDescriptor.GetElementDescriptor(controlId);

        elementDescriptor = elementDescriptor?.CreateCopy(_serializationManager, cloneId);

        // If window_name is "window", "pane", "menu", or "macro", and the skin file does not have a control of
        // that name already, we will create a new control of that type from scratch.
        if (elementDescriptor == null) {
            switch (controlId) {
                case "window":
                    elementDescriptor = new WindowDescriptor(cloneId);
                    break;
                case "menu":
                    elementDescriptor = new MenuDescriptor(cloneId);
                    break;
                case "macro":
                    elementDescriptor = new MacroSetDescriptor(cloneId);
                    break;
                default:
                    _sawmill.Error($"Invalid element to winclone \"{controlId}\"");
                    return;
            }
        }

        if (elementDescriptor is WindowDescriptor windowDescriptor) {
            // Cloned windows start off non-visible
            elementDescriptor = windowDescriptor.WithVisible(_serializationManager, false);
        }

        LoadDescriptor(elementDescriptor);
        if (elementDescriptor is WindowDescriptor && Windows.TryGetValue(cloneId, out var window)) {
            window.CreateChildControls();
        }
    }

    private void Reset() {
        _uiManager.MainViewport.Visible = false;
        //close windows if they're open, and clear all child ui elements
        foreach (var window in Windows.Values){
            window.CloseChildWindow();
            window.UIElement.RemoveAllChildren();
        }

        Windows.Clear();
        Menus.Clear();
        MacroSets.Clear();

        _inputManager.ResetAllBindings();
        SetupBaseDreamBinds();
    }

    private void LoadInterface(InterfaceDescriptor descriptor) {
        InterfaceDescriptor = descriptor;

        foreach (MacroSetDescriptor macroSet in descriptor.MacroSetDescriptors) {
            LoadDescriptor(macroSet);
        }

        foreach (MenuDescriptor menuDescriptor in InterfaceDescriptor.MenuDescriptors) {
            LoadDescriptor(menuDescriptor);
        }

        foreach (WindowDescriptor windowDescriptor in InterfaceDescriptor.WindowDescriptors) {
            LoadDescriptor(windowDescriptor);
        }

        foreach (ControlWindow window in Windows.Values) {
            window.CreateChildControls();

            foreach (InterfaceControl control in window.ChildControls) {
                if (control.IsDefault) {
                    switch (control) {
                        case ControlOutput controlOutput: DefaultOutput = controlOutput; break;
                        case ControlInfo controlInfo: DefaultInfo = controlInfo; break;
                        case ControlMap controlMap: DefaultMap = controlMap; break;
                    }
                }
            }
        }

        if (DefaultWindow == null)
            throw new Exception("Given DMF did not have a default window");

        DefaultWindow.RegisterOnClydeWindow(_clyde.MainWindow);
        DefaultWindow.UIElement.Name = "MainWindow";
        LayoutContainer.SetAnchorRight(DefaultWindow.UIElement, 1);
        LayoutContainer.SetAnchorBottom(DefaultWindow.UIElement, 1);

        _uiManager.StateRoot.AddChild(DefaultWindow.UIElement);

        if (DefaultWindow.GetClydeWindow() is { } clydeWindow) {
            ClydeWindowIdToControl.Add(clydeWindow.Id, DefaultWindow);
        }

        ScheduleSkinDump();
    }

    /// <summary>
    /// Writes every skin element's computed properties to the path in
    /// <see cref="OpenDreamCVars.SkinDumpPath"/>, if one is configured.
    ///
    /// This is the client-side half of the skin parity harness: it produces the same
    /// information as the "Dump Skin State" verb without needing anyone to click anything,
    /// so a headless run can be diffed against a DreamSeeker capture.
    /// </summary>
    private void ScheduleSkinDump() {
        var dumpPath = _cfg.GetCVar(OpenDreamCVars.SkinDumpPath);
        if (string.IsNullOrWhiteSpace(dumpPath))
            return;

        var delay = _cfg.GetCVar(OpenDreamCVars.SkinDumpDelay);

        // Delayed so anchoring and splitter layout have settled by the time we read them.
        Timer.Spawn(TimeSpan.FromSeconds(delay), () => {
            try {
                WriteSkinDump(dumpPath);
                _sawmill.Info($"Skin dump written to {dumpPath}");
            } catch (Exception e) {
                _sawmill.Error($"Failed to write skin dump to {dumpPath}: {e}");
            }
        });
    }

    /// <remarks>
    /// Content assemblies are sandboxed and cannot touch System.IO, so the dump goes through
    /// Robust's UserData. The path is relative to the client's user data directory.
    /// </remarks>
    private void WriteSkinDump(string dumpPath) {
        var json = new StringBuilder();
        json.Append("{\"engine\":\"opendream\",\"reference_window_size\":");

        var mainWindowSize = WinGet("mainwindow", "size", forceJson: true);
        json.Append(string.IsNullOrEmpty(mainWindowSize) ? "\"\"" : mainWindowSize);

        json.Append(",\"containers\":[");
        var containerIds = Windows.Keys.OrderBy(id => id, StringComparer.Ordinal).ToArray();
        for (var i = 0; i < containerIds.Length; i++) {
            if (i > 0)
                json.Append(',');
            json.Append('"').Append(HttpUtility.JavaScriptStringEncode(containerIds[i])).Append('"');
        }

        json.Append("],\"elements\":{");

        var first = true;
        foreach (var containerId in containerIds) {
            // The window/pane itself, then each of its child controls.
            AppendElement(json, containerId, containerId, ref first);

            foreach (var control in Windows[containerId].ChildControls) {
                var childId = control.Id.Value;
                AppendElement(json, $"{containerId}.{childId}", childId, ref first);
            }
        }

        json.Append("}}");

        var path = new ResPath(dumpPath).ToRootedPath();
        _resourceManager.UserData.CreateDir(path.Directory);

        using var writer = _resourceManager.UserData.OpenWriteText(path);
        writer.Write(json.ToString());
    }

    private void AppendElement(StringBuilder json, string queryId, string outputId, ref bool first) {
        var properties = WinGet(queryId, "*", forceJson: true);
        if (string.IsNullOrEmpty(properties) || properties == "{}")
            return;

        if (!first)
            json.Append(',');
        first = false;

        json.Append('"').Append(HttpUtility.JavaScriptStringEncode(outputId)).Append("\":");
        json.Append(properties);
    }

    private void OnWindowFocused(WindowFocusedEventArgs args) {
        if (ClydeWindowIdToControl.TryGetValue(args.Window.Id, out var controlWindow)) {
            _sawmill.Verbose($"window id {controlWindow.Id} was {(args.Focused ? "focused" : "defocused")}");
            WindowDescriptor descriptor = (WindowDescriptor)controlWindow.ElementDescriptor;
            descriptor.Focus = new DMFPropertyBool(args.Focused);
            if (args.Focused && MacroSets.TryGetValue(descriptor.Macro.AsRaw(), out var windowMacroSet)) {
                _sawmill.Verbose($"Activating macroset {descriptor.Macro}");
                windowMacroSet.SetActive();
            }
        } else {
            _sawmill.Verbose($"window id was not found (probably a modal) but was {(args.Focused ? "focused" : "defocused")}");
        }
    }

    private void LoadDescriptor(ElementDescriptor descriptor) {
        switch (descriptor) {
            case MacroSetDescriptor macroSetDescriptor:
                InterfaceMacroSet macroSet = new(macroSetDescriptor, _entitySystemManager, _inputManager, _uiManager);

                MacroSets[macroSet.Id.Value] = macroSet;
                break;
            case MenuDescriptor menuDescriptor:
                InterfaceMenu menu = new(menuDescriptor);

                Menus.Add(menu.Id.Value, menu);
                break;
            case WindowDescriptor windowDescriptor:
                ControlWindow window = new ControlWindow(windowDescriptor);

                Windows.Add(windowDescriptor.Id.Value, window);
                if (window.IsDefault) {
                    DefaultWindow = window;
                }

                if (window.GetClydeWindow() is { } clydeWindow) {
                    ClydeWindowIdToControl.Add(clydeWindow.Id, window);
                }

                break;
        }
    }

    private void OnPromptFinished(int promptId, DreamValueType responseType, object? response) {
        var msg = new MsgPromptResponse {
            PromptId = promptId,
            Type = responseType,
            Value = response
        };

        _netManager.ClientSendMessage(msg);
    }
}

public sealed class CursorHolder(IClyde clyde) {
    public readonly ICursor? BaseCursor;
    public readonly ICursor? DragCursor = clyde.GetStandardCursor(StandardCursorShape.Crosshair);
    public readonly ICursor? OverCursor;
    public readonly ICursor? DropCursor = clyde.GetStandardCursor(StandardCursorShape.Hand);
    public readonly bool AllStateSet;

    public CursorHolder(IClyde clyde, DMIResource resource) : this(clyde) {
        var allCursor = resource.GetStateAsImage(clyde, "all");

        if (allCursor is not null) { //all overrides all possible states
            BaseCursor = allCursor;
            DragCursor = BaseCursor;
            DropCursor = BaseCursor;
            OverCursor = BaseCursor;
            AllStateSet = true;
        } else {
            BaseCursor = resource.GetStateAsImage(clyde, "");
            OverCursor = resource.GetStateAsImage(clyde, "over");
            DragCursor = resource.GetStateAsImage(clyde, "drag");
            DropCursor = resource.GetStateAsImage(clyde, "drop");
        }
    }
}

public interface IDreamInterfaceManager {
    Dictionary<string, ControlWindow> Windows { get; }
    Dictionary<string, InterfaceMenu> Menus { get; }
    Dictionary<string, InterfaceMacroSet> MacroSets { get; }
    public ControlWindow? DefaultWindow { get; }
    public ControlOutput? DefaultOutput { get; }
    public ControlInfo? DefaultInfo { get; }
    public ControlMap? DefaultMap { get; }
    public ViewRange View { get; }
    public bool ShowPopupMenus { get; }
    public int IconSize { get; }
    public MapFormat MapFormat { get; }
    public CursorHolder Cursors { get; }

    void Initialize();
    void FrameUpdate(FrameEventArgs frameEventArgs);
    InterfaceElement? FindElementWithId(string id);
    void SaveScreenshot(bool openDialog);
    void LoadInterfaceFromSource(string source);

    public void OpenAlert(string title, string message, string button1, string? button2, string? button3, Action<DreamValueType, object?>? onClose);
    public void Prompt(DreamValueType types, string title, string message, string defaultValue, Action<DreamValueType, object?>? onClose);
    public void RunCommand(string fullCommand, bool isRepeating = false, NetEntity? atomContext = null, string? atomRefContext = null);
    public void StopRepeatingCommand(string command);
    public void WinSet(string? controlId, string winsetParams);
    public string WinGet(string controlId, string queryValue, bool forceJson = false, bool forceSnowflake = false);
}
