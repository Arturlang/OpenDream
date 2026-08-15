using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using JetBrains.Annotations;
using OpenDreamShared.Dream;
using OpenDreamShared.Resources;
using OpenDreamRuntime.Objects.Types;
using OpenDreamRuntime.Resources;
using Api = OpenDreamRuntime.ByondApi.ByondApi;

namespace OpenDreamRuntime.Procs;

internal static partial class DMOpcodeHandlers {
    private static ProcStatus CallExt(
        DMProcState state,
        DreamValue source,
        DMProcState.DMStackArgumentInfo argumentsInfo) {
        if(!source.TryGetValueAsString(out var dllName))
            throw new DMException($"{source} is not a valid DLL");

        using var popProc = state.Pop();
        if(!popProc.TryGetValueAsString(out var procName)) {
            throw new DMException($"{popProc} is not a valid proc name");
        }

        DreamProcArguments arguments = state.PopProcArguments(null, argumentsInfo);

        dllName = NormalizeExternalLibraryName(dllName);

        if (procName.StartsWith("byond:")) {
            return CallExtByond(state, dllName, procName, arguments);
        } else {
            return CallExtString(state, dllName, procName, arguments);
        }
    }

    public static string NormalizeExternalLibraryName(string dllName) {
        // If we're on linux, we use a .so instead of a .dll
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux) && dllName.EndsWith(".dll")) {
            dllName = dllName[..^"dll".Length] + "so";
        }

        return dllName;
    }

    public static unsafe void ResolveExternalFunction(DreamResourceManager resourceManager, string dllName, string procName) {
        _ = procName.StartsWith("byond:")
            ? DllHelper.ResolveDllTarget(resourceManager, dllName, procName["byond:".Length..])
            : DllHelper.ResolveDllTarget(resourceManager, dllName, procName);
    }

    private static ProcStatus CallExtLoaded(
        DMProcState state,
        DreamObjectExternalProc externalProc,
        DreamProcArguments arguments) {
        return externalProc.Function.StartsWith("byond:")
            ? CallExtByond(state, externalProc.Library, externalProc.Function, arguments)
            : CallExtString(state, externalProc.Library, externalProc.Function, arguments);
    }

    private static unsafe ProcStatus CallExtByond(
        DMProcState state,
        string dllName,
        string procName,
        [HandlesResourceDisposal] DreamProcArguments arguments) {
        // TODO: Don't allocate string copy
        // TODO: Handle stdcall (do we care?)
        var entryPoint = (delegate* unmanaged[Cdecl]<uint, ByondApi.CByondValue*, ByondApi.CByondValue>)
            DllHelper.ResolveDllTarget(state.Proc.DreamResourceManager, dllName, procName["byond:".Length..]);

        Span<ByondApi.CByondValue> args = stackalloc ByondApi.CByondValue[arguments.Count];
        args.Clear();

        for (var i = 0; i < args.Length; i++) {
            var arg = arguments.GetArgument(i);
            args[i] = Api.ValueToByondApi(arg);
        }

        using var result = Api.ValueFromDreamApi(Api.DoCall(entryPoint, args));
        state.Push(result);
        arguments.Dispose();
        return ProcStatus.Continue;
    }

    private static unsafe ProcStatus CallExtString(
        DMProcState state,
        string dllName,
        string procName,
        [HandlesResourceDisposal] DreamProcArguments arguments) {
        if (procName == "file_read" && TryReadStaticSourceFile(state, arguments, out var fileReadResult)) {
            state.Push(fileReadResult);
            arguments.Dispose();
            return ProcStatus.Continue;
        }

        if (procName == "file_write" && TryWriteTextFile(state, arguments, out var fileWriteResult)) {
            state.Push(fileWriteResult);
            arguments.Dispose();
            return ProcStatus.Continue;
        }

        var entryPoint = DllHelper.ResolveDllTarget(state.Proc.DreamResourceManager, dllName, procName);

        Span<nint> argV = stackalloc nint[arguments.Count];
        argV.Fill(0);
        try {
            for (var i = 0; i < argV.Length; i++) {
                var arg = arguments.GetArgument(i).Stringify();

                argV[i] = Marshal.StringToCoTaskMemUTF8(arg);
            }

            byte* ret;
            if (arguments.Count > 0) {
                fixed (nint* ptr = &argV[0]) {
                    ret = entryPoint(arguments.Count, (byte**)ptr);
                }
            } else {
                ret = entryPoint(0, (byte**)0);
            }

            if (ret == null) {
                state.Push(DreamValue.Null);
                return ProcStatus.Continue;
            }

            var retString = Marshal.PtrToStringUTF8((nint)ret) ?? string.Empty;
            if (procName == "dmi_read_metadata") {
                retString = LooksLikeDmiMetadata(retString) || !TryCreateDmiMetadataFallback(state, arguments.GetArgument(0), out var fallback)
                    ? retString
                    : fallback;
            } else if (procName == "toml_file_to_json") {
                retString = NormalizeTomlFileToJsonStringArrays(retString);
            }

            state.Push(new DreamValue(retString));
            return ProcStatus.Continue;
        } finally {
            arguments.Dispose();
            foreach (var arg in argV) {
                if (arg != 0)
                    Marshal.ZeroFreeCoTaskMemUTF8(arg);
            }
        }
    }

    private static bool TryReadStaticSourceFile(DMProcState state, DreamProcArguments arguments, out DreamValue result) {
        result = DreamValue.Null;

        if (arguments.Count != 1)
            return false;

        var path = arguments.GetArgument(0).Stringify();
        if (!Path.GetExtension(path).Equals(".dm", StringComparison.OrdinalIgnoreCase))
            return false;

        result = state.Proc.DreamResourceManager.LoadResource(path).ReadAsString() is { } text
            ? new DreamValue(text)
            : DreamValue.Null;
        return true;
    }

    private static bool TryWriteTextFile(DMProcState state, DreamProcArguments arguments, out DreamValue result) {
        result = DreamValue.Null;

        if (arguments.Count != 2)
            return false;

        if (!arguments.GetArgument(1).TryGetValueAsString(out var path))
            return false;

        var text = arguments.GetArgument(0).Stringify();
        result = new DreamValue(state.Proc.DreamResourceManager.SaveTextToFile(path, text) ? "1" : "0");
        return true;
    }

    private static bool LooksLikeDmiMetadata(string metadata) {
        try {
            if (JsonNode.Parse(metadata) is JsonObject metadataObject && metadataObject["states"] is JsonArray)
                return true;
        } catch (JsonException) {
            return false;
        }

        return false;
    }

    private static string NormalizeTomlFileToJsonStringArrays(string tomlResultJson) {
        try {
            if (JsonNode.Parse(tomlResultJson) is not JsonObject result ||
                result["success"]?.GetValue<bool>() != true ||
                result["content"]?.GetValue<string>() is not { } content ||
                JsonNode.Parse(content) is not { } contentNode) {
                return tomlResultJson;
            }

            ConvertStringArraysToAssociativeObjects(contentNode);
            result["content"] = contentNode.ToJsonString();
            return result.ToJsonString();
        } catch (JsonException) {
            return tomlResultJson;
        } catch (InvalidOperationException) {
            return tomlResultJson;
        }
    }

    private static void ConvertStringArraysToAssociativeObjects(JsonNode node) {
        switch (node) {
            case JsonObject jsonObject:
                foreach (var property in jsonObject.ToArray()) {
                    if (property.Value == null)
                        continue;

                    var converted = ConvertStringArrayToAssociativeObject(property.Value);
                    if (!ReferenceEquals(converted, property.Value))
                        jsonObject[property.Key] = converted;
                }

                break;
            case JsonArray jsonArray:
                for (var i = 0; i < jsonArray.Count; i++) {
                    if (jsonArray[i] == null)
                        continue;

                    var converted = ConvertStringArrayToAssociativeObject(jsonArray[i]!);
                    if (!ReferenceEquals(converted, jsonArray[i]))
                        jsonArray[i] = converted;
                }

                break;
        }
    }

    private static JsonNode ConvertStringArrayToAssociativeObject(JsonNode node) {
        if (node is JsonArray jsonArray) {
            var allStrings = jsonArray.Count > 0 && jsonArray.All(element => element is JsonValue value && value.TryGetValue<string>(out _));
            if (allStrings) {
                JsonObject jsonObject = new();
                foreach (var element in jsonArray) {
                    var value = element!.GetValue<string>();
                    jsonObject[value] = value;
                }

                return jsonObject;
            }
        }

        ConvertStringArraysToAssociativeObjects(node);
        return node;
    }

    private static bool TryCreateDmiMetadataFallback(DMProcState state, DreamValue metadataArgument, out string metadata) {
        metadata = string.Empty;

        var resourcePath = metadataArgument.Stringify();
        switch (Path.GetExtension(resourcePath)) {
            case ".dmi":
            case ".png":
            case ".bmp":
                break;
            default:
                return false;
        }

        if (!state.Proc.DreamResourceManager.TryLoadIcon(metadataArgument, out var icon))
            return false;

        metadata = DmiMetadataToJson(icon.DMI);
        return true;
    }

    private static string DmiMetadataToJson(DMIParser.ParsedDMIDescription description) {
        var states = new JsonArray();

        foreach (var parsedState in description.States.Values) {
            var directions = DMIParser.GetExportedDirectionCount(parsedState.Directions);
            var frames = parsedState.GetFrames(AtomDirection.South).Length;

            states.Add(new JsonObject {
                ["name"] = parsedState.Name,
                ["dirs"] = directions,
                ["frames"] = frames
            });
        }

        return new JsonObject {
            ["width"] = description.Width,
            ["height"] = description.Height,
            ["states"] = states
        }.ToJsonString();
    }
}
