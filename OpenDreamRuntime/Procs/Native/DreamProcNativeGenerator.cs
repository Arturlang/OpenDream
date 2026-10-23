using OpenDreamRuntime.Objects;
using OpenDreamRuntime.Objects.Types;
using OpenDreamShared.Dream;

namespace OpenDreamRuntime.Procs.Native;

internal static class DreamProcNativeGenerator {
    [DreamProc("Rand")]
    public static DreamValue NativeProc_Rand(NativeProc.Bundle bundle, DreamObject? src, DreamObject? usr) {
        var genObj = (DreamObjectGenerator)src!;
        // The world's RNG, so rand_seed() makes Rand() repeatable like rand() and prob()
        var rand = bundle.DreamManager.Random;

        switch (genObj.Generator) {
            case IGeneratorNum numGen: {
                var result = numGen.Generate(rand);
                return new DreamValue(result);
            }
            case IGeneratorVector vecGen: {
                var resultObj = vecGen.PrefersVector3
                    ? DreamObjectVector.CreateFromValue(vecGen.GenerateVector3(rand), bundle.ObjectTree)
                    : DreamObjectVector.CreateFromValue(vecGen.GenerateVector2(rand), bundle.ObjectTree);

                return new DreamValue(resultObj);
            }
            default:
                throw new DMException($"Invalid generator for Rand: {genObj}");
        }
    }
}
