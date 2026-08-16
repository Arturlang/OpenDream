using System.Text;
using System.Web;

namespace OpenDreamClient.Interface;

public static class BrowserBridgeScript {
    public static string FormatOutputCall(string jsFunction, string value) {
        return WrapInjectedCall(jsFunction, FormatOutputArguments(value));
    }

    /// <summary>
    /// Wraps a call we inject through ExecuteJavaScript in a try/catch that reports the real
    /// exception through byond://odlog.
    ///
    /// Injected scripts have no source URL, so Chromium masks anything they throw as
    /// "Script error." at :0 - even window.onerror sees nothing else. Catching in the same
    /// context sidesteps the masking entirely: we hold the exception object and its stack.
    /// </summary>
    public static string WrapInjectedCall(string jsFunction, string argumentsJs) {
        var label = HttpUtility.JavaScriptStringEncode(jsFunction);

        // The exception has stringified to "" in the wild (String(e) empty, no stack), so
        // report type forensics rather than a bare String(e).
        return "try{" + jsFunction + "(" + argumentsJs + ")}" +
               "catch(e){try{(new Image()).src=\"byond://odlog?text=\"+encodeURIComponent(" +
               "\"injected call " + label + " threw:\"" +
               "+\" tag=\"+Object.prototype.toString.call(e)" +
               "+\" name=\"+String(e&&e.name)" +
               "+\" msg=\"+String(e&&e.message)" +
               "+\" json=\"+(function(){try{return (JSON.stringify(e)||\"\").slice(0,300)}catch(e3){return \"?\"}})()" +
               "+\" stack=\"+String(e&&e.stack).slice(0,1000)" +
               ")}catch(e2){}}";
    }

    public static string FormatOutputArguments(string value) {
        var result = new StringBuilder();
        var parts = value.Split('&');

        for (var i = 0; i < parts.Length; i++) {
            if (i > 0)
                result.Append(',');

            result.Append('"');
            result.Append(HttpUtility.JavaScriptStringEncode(HttpUtility.UrlDecode(parts[i])));
            result.Append('"');
        }

        return result.ToString();
    }
}
