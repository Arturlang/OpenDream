using Lidgren.Network;
using OpenDreamShared.Dream;
using Robust.Shared.Network;
using Robust.Shared.Serialization;

namespace OpenDreamShared.Network.Messages;

/// <summary>
/// A NetMessage intended for information the client needs, is small, and infrequently changes
/// </summary>
public sealed class MsgUpdateClientInfo : NetMessage {
    public override MsgGroups MsgGroup => MsgGroups.EntityEvent;

    public int IconSize;
    public ViewRange View;
    public MapFormat MapFormat;
    public int CursorResource;

    public bool ShowPopupMenus;
    /// <summary>client.fps: the frame rate the client renders at, 0 for its own default</summary>
    public int Fps;

    public override void ReadFromBuffer(NetIncomingMessage buffer, IRobustSerializer serializer) {
        IconSize = buffer.ReadInt32();
        View = new(buffer.ReadInt32(), buffer.ReadInt32());
        MapFormat = (MapFormat)buffer.ReadInt32();
        ShowPopupMenus = buffer.ReadBoolean();
        CursorResource = buffer.ReadInt32();
        Fps = buffer.ReadInt32();
    }

    public override void WriteToBuffer(NetOutgoingMessage buffer, IRobustSerializer serializer) {
        buffer.Write(IconSize);
        buffer.Write(View.Width);
        buffer.Write(View.Height);
        buffer.Write((int)MapFormat);
        buffer.Write(ShowPopupMenus);
        buffer.Write(CursorResource);
        buffer.Write(Fps);
    }
}
