using Lidgren.Network;
using Robust.Shared.Network;
using Robust.Shared.Serialization;

namespace OpenDreamShared.Network.Messages;

/// <summary>
/// Asks the client how large a piece of maptext would draw. Only the client knows:
/// the face, size and class styling all come from the map control's skin properties
/// and from font resources the server never rasterises.
/// </summary>
public sealed class MsgMeasureText : NetMessage {
    public override MsgGroups MsgGroup => MsgGroups.EntityEvent;

    public int PromptId;
    public string Text = string.Empty;
    public string Style = string.Empty;

    /// Width to wrap at, or 0 for no wrapping.
    public int Width;

    public override void ReadFromBuffer(NetIncomingMessage buffer, IRobustSerializer serializer) {
        PromptId = buffer.ReadVariableInt32();
        Text = buffer.ReadString();
        Style = buffer.ReadString();
        Width = buffer.ReadVariableInt32();
    }

    public override void WriteToBuffer(NetOutgoingMessage buffer, IRobustSerializer serializer) {
        buffer.WriteVariableInt32(PromptId);
        buffer.Write(Text);
        buffer.Write(Style);
        buffer.WriteVariableInt32(Width);
    }
}
