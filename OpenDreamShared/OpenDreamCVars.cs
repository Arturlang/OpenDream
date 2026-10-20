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
    /// Skips the geometry shim, which redefines Element.prototype.getBoundingClientRect,
    /// MouseEvent.prototype.screenX/screenY and window.screenLeft/screenTop.
    /// Diagnostic toggle: patching DOM prototypes underneath a framework is invasive enough
    /// to be worth ruling out on its own.
    /// </summary>
    public static readonly CVarDef<bool> DisableBrowserGeometryShim =
        CVarDef.Create("opendream.disable_browser_geometry_shim", false, CVar.CLIENTONLY);

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

    /// <summary>
    /// User data directory for the prompt test hook (prompts.json, answer.txt). Empty disables the hook.
    /// </summary>
    public static readonly CVarDef<string> TestPromptDir =
        CVarDef.Create("opendream.test_prompt_dir", string.Empty, CVar.CLIENTONLY);

    /// <summary>
    /// Enables the periodic entity/sprite census logging on both client and server.
    /// Each census walks EVERY entity to build its histogram - a quarter of a million
    /// of them on a full station - so it is a real periodic stall, not just log noise.
    /// Off by default; turn it on when diagnosing "objects exist but nothing renders".
    /// </summary>
    public static readonly CVarDef<bool> DebugCensus =
        CVarDef.Create("opendream.debug_census", false, CVar.ARCHIVE);

    /// <summary>
    /// Logs world-render frame time and sprite counts periodically. Off by default:
    /// it is for answering "is the client or the server behind?" with numbers.
    /// </summary>
    public static readonly CVarDef<bool> DebugRenderPerf =
        CVarDef.Create("opendream.debug_renderperf", false, CVar.CLIENTONLY);

    /// <summary>
    /// Logs what the mouse map actually registers each second: which planes were
    /// skipped and why, and how many sprites made it in. Clicks resolve against that
    /// map, so "the atom is drawn but not clickable" is only answerable from here.
    /// </summary>
    public static readonly CVarDef<bool> DebugMouseMap =
        CVarDef.Create("opendream.debug_mousemap", false, CVar.CLIENTONLY);

    /// <summary>
    /// Renders one plane's render target straight to the viewport instead of the
    /// composited world, so a screenshot shows exactly what that plane contains.
    /// Set to the plane number (SS13's lighting plate is 22, turf lighting 10).
    /// int.MinValue (the default) renders normally.
    /// </summary>
    public static readonly CVarDef<int> DebugPlane =
        CVarDef.Create("opendream.debug_plane", int.MinValue, CVar.CLIENTONLY);

    /// <summary>
    /// With <see cref="DebugPlane"/>, render that plane's ALPHA channel as
    /// greyscale instead of its colour. Screenshots are always opaque, and alpha
    /// is what alpha_mask_filter actually gates on.
    /// </summary>
    public static readonly CVarDef<bool> DebugPlaneAlpha =
        CVarDef.Create("opendream.debug_plane_alpha", false, CVar.CLIENTONLY);

    /// <summary>
    /// Seconds after startup at which to run one compacting gen2 collection, or 0 to never.
    /// Round init churns the large object heap hard and leaves it fragmented; compacting
    /// once before players arrive reclaims that. It is a blocking collection - every
    /// managed thread stops, including the game loop - so this is deliberately a one shot
    /// on a timer rather than something that can fire mid-round. The log line reports how
    /// long the freeze lasted and what it bought.
    /// </summary>
    public static readonly CVarDef<int> CompactHeapAfter =
        CVarDef.Create("opendream.compact_heap_after", 0, CVar.SERVERONLY);

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

    /// <summary>
    /// Seconds to wait before Tracy starts recording, so a capture can cover steady state without world init.
    /// The Tracy client only accepts one connection per process, so this is the way to profile a running round.
    /// </summary>
    public static readonly CVarDef<float> TracyDelay =
        CVarDef.Create("opendream.tracy_delay", 0f, CVar.SERVERONLY);

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
