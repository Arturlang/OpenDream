using System;
using Robust.Shared.Configuration;

namespace OpenDreamShared;

[CVarDefs]
public abstract class OpenDreamCVars {
    public static readonly CVarDef<string> JsonPath =
        CVarDef.Create("opendream.json_path", string.Empty, CVar.SERVERONLY);

    public static readonly CVarDef<int> DownloadTimeout =
        CVarDef.Create("opendream.download_timeout", 30, CVar.CLIENTONLY);

    /// <summary>
    /// Skips the browser storage shim and leaves TGUI's own storage CDN reference intact.
    /// Diagnostic toggle: the shim replaces TGUI's storage backend, so it is the first thing
    /// to rule out when TGUI dies with a bare "Script error." that master does not produce.
    /// </summary>
    public static readonly CVarDef<bool> DisableBrowserStorageShim =
        CVarDef.Create("opendream.disable_browser_storage_shim", false, CVar.CLIENTONLY);

    /// <summary>
    /// When set to a file path, the client writes a JSON dump of every skin element's
    /// computed properties there shortly after the interface loads, then keeps going.
    /// Used to diff skin geometry against DreamSeeker without needing a human to look at it.
    /// Empty (the default) disables the dump entirely.
    /// </summary>
    public static readonly CVarDef<string> SkinDumpPath =
        CVarDef.Create("opendream.skin_dump_path", string.Empty, CVar.CLIENTONLY);

    /// <summary>
    /// Seconds to wait after the interface loads before writing <see cref="SkinDumpPath"/>,
    /// so that anchoring and splitter layout have settled.
    /// </summary>
    public static readonly CVarDef<float> SkinDumpDelay =
        CVarDef.Create("opendream.skin_dump_delay", 10f, CVar.CLIENTONLY);

    public static readonly CVarDef<bool> AlwaysShowExceptions =
        CVarDef.Create("opendream.always_show_exceptions", false, CVar.SERVERONLY);

    public static readonly CVarDef<int> DebugAdapterLaunched =
        CVarDef.Create("opendream.debug_adapter_launched", 0, CVar.SERVERONLY);

    /// <summary>
    /// Older versions of BYOND used Internet Explorer. Set this if you need to spoof the old user agent.
    /// </summary>
    public static readonly CVarDef<bool> SpoofIEUserAgent =
        CVarDef.Create("opendream.spoof_ie_user_agent", false, CVar.CLIENTONLY);

    public static readonly CVarDef<string> WorldParams =
        CVarDef.Create("opendream.world_params", string.Empty, CVar.SERVERONLY);

    public static readonly CVarDef<ushort> TopicPort =
        CVarDef.Create<ushort>("opendream.topic_port", 25567, CVar.SERVERONLY);

    /// <summary>
    /// How large a /list's capacity has to be before it will be held in the list pool
    /// </summary>
    public static readonly CVarDef<int> ListPoolThreshold =
        CVarDef.Create("opendream.list_pool_threshold", 2048, CVar.SERVERONLY);

    /// <summary>
    /// The maximum amount of lists kept in the list pool
    /// </summary>
    public static readonly CVarDef<int> ListPoolSize =
        CVarDef.Create("opendream.list_pool_size", 256, CVar.SERVERONLY);

    /// <summary>
    /// If Tracy should be enabled. ONLY FUNCTIONS IN TOOLS BUILD.
    /// </summary>
    public static readonly CVarDef<bool> TracyEnable =
        CVarDef.Create("opendream.enable_tracy", false, CVar.SERVERONLY);

    /*
    * INFOLINKS
    */

    /// <summary>
    /// Link to Discord server to show in the launcher.
    /// </summary>
    public static readonly CVarDef<string> InfoLinksDiscord =
        CVarDef.Create("infolinks.discord", "", CVar.SERVER | CVar.REPLICATED);

    /// <summary>
    /// Link to forum to show in the launcher.
    /// </summary>
    public static readonly CVarDef<string> InfoLinksForum =
        CVarDef.Create("infolinks.forum", "", CVar.SERVER | CVar.REPLICATED);

    /// <summary>
    /// Link to GitHub page to show in the launcher.
    /// </summary>
    public static readonly CVarDef<string> InfoLinksGithub =
        CVarDef.Create("infolinks.github", "", CVar.SERVER | CVar.REPLICATED);

    /// <summary>
    /// Link to website to show in the launcher.
    /// </summary>
    public static readonly CVarDef<string> InfoLinksWebsite =
        CVarDef.Create("infolinks.website", "", CVar.SERVER | CVar.REPLICATED);

    /// <summary>
    /// Link to wiki to show in the launcher.
    /// </summary>
    public static readonly CVarDef<string> InfoLinksWiki =
        CVarDef.Create("infolinks.wiki", "", CVar.SERVER | CVar.REPLICATED);
}
