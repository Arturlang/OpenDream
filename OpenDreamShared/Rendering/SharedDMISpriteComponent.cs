using Robust.Shared.GameObjects;
using Robust.Shared.Serialization;
using System;
using Robust.Shared.GameStates;
using OpenDreamShared.Dream;
using Robust.Shared.Maths;

namespace OpenDreamShared.Rendering;

[NetworkedComponent]
public abstract partial class SharedDMISpriteComponent : Component {
    [Serializable, NetSerializable]
    public sealed class DMISpriteComponentState(uint? appearanceId, ScreenLocation? screenLocation, Vector2i boundOffset) : ComponentState {
        public readonly uint? AppearanceId = appearanceId;
        public readonly ScreenLocation? ScreenLocation = screenLocation;
        public readonly Vector2i BoundOffset = boundOffset;
    }
}
