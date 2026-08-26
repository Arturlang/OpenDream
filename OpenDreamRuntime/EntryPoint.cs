using OpenDreamRuntime.Objects.Types;
using OpenDreamRuntime.Procs.DebugAdapter;
using OpenDreamShared;
using Robust.Shared;
using Robust.Shared.Configuration;
using Robust.Shared.ContentPack;
using Robust.Shared.Timing;
using Robust.Shared.Prototypes;
using Robust.Shared.Utility;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using Robust.Shared.GameObjects;

[module: System.Runtime.CompilerServices.SkipLocalsInit]

namespace OpenDreamRuntime {
    public sealed partial class EntryPoint : GameServer {
        [Dependency] private IEntitySystemManager _entitySystemManager = default!;
        [Dependency] private DreamManager _dreamManager = default!;
        [Dependency] private IConfigurationManager _configManager = default!;
        [Dependency] private IPrototypeManager _prototypeManager = default!;
        [Dependency] private IDreamDebugManager _debugManager = default!;
        [Dependency] private ServerInfoManager _serverInfoManager = default!;

        private ServerVerbSystem? _serverVerbSystem;

        /// <summary>
        /// Says out loud whether this server was built with optimisations. A server built
        /// in the Debug configuration runs roughly four and a half times slower than one
        /// built in Tools - a full Bubberstation init went from 363 seconds to 81, which
        /// is BYOND's own time - and nothing else about it looks wrong, so it is worth
        /// one line at startup rather than an afternoon with a profiler.
        ///
        /// It reflects on the loaded assemblies rather than checking #if DEBUG, because
        /// the case that actually happens is a mismatch: a plain `dotnet build` defaults
        /// to Debug and overwrites part of an otherwise optimised bin.
        /// </summary>
        private static void LogBuildConfiguration() {
            var sawmill = Logger.GetSawmill("opendream");
            var unoptimised = new List<string>();

            foreach (var assembly in new[] {typeof(EntryPoint).Assembly, typeof(IEntityManager).Assembly}) {
                var debuggable = assembly.GetCustomAttribute<DebuggableAttribute>();
                if (debuggable?.IsJITOptimizerDisabled == true)
                    unoptimised.Add(assembly.GetName().Name ?? "<unknown>");
            }

            if (unoptimised.Count == 0) {
                sawmill.Info("Build: optimised.");
                return;
            }

            sawmill.Warning(
                $"Build: UNOPTIMISED ({string.Join(", ", unoptimised)}). This is a Debug build and " +
                "will run several times slower than a Tools or Release one. Rebuild with " +
                "\"dotnet build OpenDreamServer -c Tools\" or ./build.ps1 - a plain \"dotnet build\" " +
                "defaults to Debug.");
        }

        public override void Init() {
            LogBuildConfiguration();

            IComponentFactory componentFactory = IoCManager.Resolve<IComponentFactory>();
            componentFactory.DoAutoRegistrations();

            ServerContentIoC.Register();

            // This needs to happen after all IoC registrations, but before IoC.BuildGraph();
            foreach (var callback in TestingCallbacks) {
                var cast = (ServerModuleTestingCallbacks) callback;
                cast.ServerBeforeIoC?.Invoke();
            }

            IoCManager.BuildGraph();
            IoCManager.InjectDependencies(this);
            componentFactory.GenerateNetIds();

            _configManager.OverrideDefault(CVars.NetLogLateMsg, false); // Disable since disabling prediction causes timing errors otherwise.
            _configManager.OverrideDefault(CVars.GameAutoPauseEmpty, false); // DreamObjectWorld sets this appropriately but we need to keep it disabled til then or it won't be reached
            _configManager.OverrideDefault(CVars.DiscordRichPresenceSecondIconId, "opendream");
            _configManager.SetCVar(CVars.GridSplitting, false); // Grid splitting should never be used
            if(string.IsNullOrEmpty(_configManager.GetCVar(OpenDreamCVars.JsonPath))) //if you haven't set the jsonpath cvar, set it to the first valid file path passed as an arg
                foreach (string arg in Environment.GetCommandLineArgs().Skip(1)) //skip the first element, because it's just the server's exe path
                    if(File.Exists(arg)){
                        _configManager.SetCVar(OpenDreamCVars.JsonPath, arg);
                        break;
                    }

            if(_configManager.GetCVar(OpenDreamCVars.TracyEnable))
                Profiler.Activate();

            _prototypeManager.LoadDirectory(new ResPath("/Resources/Prototypes"));

            _serverInfoManager.Initialize();
        }

        public override void PostInit() {
            _serverVerbSystem = _entitySystemManager.GetEntitySystem<ServerVerbSystem>();

            int debugAdapterPort = _configManager.GetCVar(OpenDreamCVars.DebugAdapterLaunched);
            if (debugAdapterPort == 0) {
                _dreamManager.PreInitialize(_configManager.GetCVar(OpenDreamCVars.JsonPath));
                _dreamManager.StartWorld();
            } else {
                // The debug manager is responsible for running _dreamManager.PreInitialize() and .StartWorld()
                _debugManager.Initialize(debugAdapterPort);
            }
        }

        protected override void Dispose(bool disposing) {
            // Write every savefile to disk
            foreach (var savefile in DreamObjectSavefile.Savefiles.ToArray()) { //ToArray() to avoid modifying the collection while iterating over it
                try {
                    savefile.Close();
                } catch (Exception e) {
                    Logger.GetSawmill("opendream").Error($"Exception while flushing savefile '{savefile.Resource?.ResourcePath ?? "<unknown>"}', data has been lost. {e}");
                }
            }

            _dreamManager.Shutdown();
            _debugManager.Shutdown();
            ByondApi.ByondApi.Shutdown();
        }

        public override void Update(ModUpdateLevel level, FrameEventArgs frameEventArgs) {
            if (level == ModUpdateLevel.PostEngine) {
                _serverVerbSystem?.RunRepeatingVerbs();
                _dreamManager.Update();
                _debugManager.Update();
            }
        }
    }
}
