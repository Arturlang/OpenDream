using DMCompiler.Bytecode;

namespace OpenDreamRuntime.Objects.Types;

/// <summary>
/// What initial() returns for a var whose initial value is set at runtime, e.g. <c>var/list/L = list()</c>.
/// BYOND has no compile-time value to give, so it returns an opaque value that is truthy but prints as an
/// empty string and is neither text, a list, nor a datum.
/// </summary>
internal sealed class DreamObjectInitialPlaceholder(DreamObjectDefinition objectDefinition) : DreamObject(objectDefinition) {
    public override string GetDisplayName(StringFormatEncoder.FormatSuffix? suffix = null) => string.Empty;

    protected override bool TryGetVar(string varName, out DreamValue value) {
        value = DreamValue.Null;
        return false;
    }

    protected override void SetVar(string varName, DreamValue value) {
        throw new Exception($"Cannot set var \"{varName}\"");
    }
}
