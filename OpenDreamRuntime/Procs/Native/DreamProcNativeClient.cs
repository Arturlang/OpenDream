using System.Threading.Tasks;
using OpenDreamRuntime.Objects;
using OpenDreamRuntime.Objects.Types;
using DreamValueTypeFlag = OpenDreamRuntime.DreamValue.DreamValueTypeFlag;

namespace OpenDreamRuntime.Procs.Native;

internal static class DreamProcNativeClient {
    [DreamProc("SoundQuery")]
    public static async Task<DreamValue> NativeProc_SoundQuery(AsyncNativeProc.AsyncNativeProcState state) {
        var client = (DreamObjectClient)state.Instance!;
        return await client.Connection.SoundQuery();
    }

    [DreamProc("Export")]
    [DreamProcParameter("file")]
    public static DreamValue NativeProc_Export(NativeProc.Bundle bundle, DreamObject? src, DreamObject? usr) {
        return DreamValue.Null;
    }

    [DreamProc("MeasureText")]
    [DreamProcParameter("text", Type = DreamValueTypeFlag.String)]
    [DreamProcParameter("style", Type = DreamValueTypeFlag.String)]
    [DreamProcParameter("width", Type = DreamValueTypeFlag.Float, DefaultValue = 0)]
    public static async Task<DreamValue> NativeProc_MeasureText(AsyncNativeProc.AsyncNativeProcState state) {
        var text = state.GetArgument(0, "text").Stringify();
        state.GetArgument(1, "style").TryGetValueAsString(out var style);
        state.GetArgument(2, "width").TryGetValueAsInteger(out var width);

        // Only the client can answer this: the face, size and class styling all come from
        // the map control's skin properties. Guessing here is what left every runechat box
        // a fixed 16 pixels tall no matter how many lines it actually held.
        if (state.Instance is not DreamObjectClient {Connection: not null} client)
            return new DreamValue($"{text.Length * 8}x16");

        return await client.Connection.MeasureText(text, style, width);
    }
}
