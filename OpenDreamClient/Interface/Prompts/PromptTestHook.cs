using System.Text;
using System.Web;
using OpenDreamShared;
using Robust.Shared.Configuration;
using Robust.Shared.ContentPack;
using Robust.Shared.Utility;

namespace OpenDreamClient.Interface.Prompts;

/// <summary>
/// Parity test hook. Writes the open prompts to prompts.json and applies the lines of answer.txt:
/// <c>id&lt;TAB&gt;action&lt;TAB&gt;argument</c>. The actions are text, select (0-based index), press (button label) and submit.
/// </summary>
internal static class PromptTestHook {
    private static readonly List<PromptWindow> OpenPrompts = new();
    private static int _nextId = 1;
    private static float _sinceCheck;
    private static string _lastWritten = string.Empty;
    private static string _lastStatus = string.Empty;

    public static void Register(PromptWindow prompt) {
        prompt.TestId = _nextId++;
        OpenPrompts.Add(prompt);
    }

    public static void Unregister(PromptWindow prompt) {
        OpenPrompts.Remove(prompt);
    }

    public static void FrameUpdate(float deltaSeconds, IConfigurationManager cfg, IResourceManager resources) {
        var dir = cfg.GetCVar(OpenDreamCVars.TestPromptDir);
        if (string.IsNullOrWhiteSpace(dir))
            return;

        _sinceCheck += deltaSeconds;
        if (_sinceCheck < 0.1f)
            return;
        _sinceCheck = 0f;

        var root = new ResPath(dir).ToRootedPath();
        var answerPath = root / "answer.txt";
        if (resources.UserData.Exists(answerPath)) {
            string answers;
            using (var reader = resources.UserData.OpenText(answerPath))
                answers = reader.ReadToEnd();
            resources.UserData.Delete(answerPath);
            _lastStatus = Apply(answers);
        }

        var json = Describe();
        if (json == _lastWritten)
            return;

        resources.UserData.CreateDir(root);
        using (var writer = resources.UserData.OpenWriteText(root / "prompts.json"))
            writer.Write(json);
        _lastWritten = json;
    }

    private static string Apply(string answers) {
        var status = new StringBuilder();
        foreach (var line in answers.Split('\n', StringSplitOptions.RemoveEmptyEntries)) {
            var parts = line.TrimEnd('\r').Split('\t');
            if (parts.Length < 2 || !int.TryParse(parts[0], out var id)) {
                status.Append("bad line;");
                continue;
            }

            var prompt = OpenPrompts.Find(p => p.TestId == id);
            if (prompt == null) {
                status.Append($"{id}: no such prompt;");
                continue;
            }

            status.Append($"{id}: {prompt.TestAnswer(parts[1], parts.Length > 2 ? parts[2] : string.Empty)};");
        }

        return status.ToString();
    }

    private static string Describe() {
        var json = new StringBuilder();
        json.Append("{\"last_answer\":\"").Append(HttpUtility.JavaScriptStringEncode(_lastStatus)).Append("\",\"prompts\":[");
        for (var i = 0; i < OpenPrompts.Count; i++) {
            if (i > 0)
                json.Append(',');
            OpenPrompts[i].TestDescribe(json);
        }

        json.Append("]}");
        return json.ToString();
    }

    public static void AppendString(StringBuilder json, string key, string? value) {
        json.Append(",\"").Append(key).Append("\":");
        if (value == null)
            json.Append("null");
        else
            json.Append('"').Append(HttpUtility.JavaScriptStringEncode(value)).Append('"');
    }
}
