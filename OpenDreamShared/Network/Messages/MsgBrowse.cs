using Lidgren.Network;
using Robust.Shared.Maths;
using Robust.Shared.Network;
using Robust.Shared.Serialization;

namespace OpenDreamShared.Network.Messages {
    public sealed class MsgBrowse : NetMessage {
        public override MsgGroups MsgGroup => MsgGroups.EntityEvent;

        public string? Window;
        public string? HtmlSource;
        public byte[]? BodyData;
        public string? File;
        public bool Display = true;
        /// Popup chrome, from browse()'s titlebar and can_close options
        public bool Titlebar = true;
        public bool CanClose = true;
        public Vector2i Size;

        public override void ReadFromBuffer(NetIncomingMessage buffer, IRobustSerializer serializer) {
            var hasWindow = buffer.ReadBoolean();
            var hasHtml = buffer.ReadBoolean();
            var hasFile = buffer.ReadBoolean();
            var hasBodyData = buffer.ReadBoolean();
            Display = buffer.ReadBoolean();
            Titlebar = buffer.ReadBoolean();
            CanClose = buffer.ReadBoolean();
            buffer.ReadPadBits();

            if (hasWindow)
                Window = buffer.ReadString();
            if (hasHtml)
                HtmlSource = buffer.ReadString();
            if (hasFile)
                File = buffer.ReadString();
            if (hasBodyData) {
                var bytes = buffer.ReadVariableInt32();
                BodyData = buffer.ReadBytes(bytes);
            }

            Size = (buffer.ReadUInt16(), buffer.ReadUInt16());
        }

        public override void WriteToBuffer(NetOutgoingMessage buffer, IRobustSerializer serializer) {
            buffer.Write(Window != null);
            buffer.Write(HtmlSource != null);
            buffer.Write(File != null);
            buffer.Write(BodyData != null);
            buffer.Write(Display);
            buffer.Write(Titlebar);
            buffer.Write(CanClose);
            buffer.WritePadBits();

            if (Window != null)
                buffer.Write(Window);
            if (HtmlSource != null)
                buffer.Write(HtmlSource);
            if (File != null)
                buffer.Write(File);
            if (BodyData != null) {
                buffer.WriteVariableInt32(BodyData.Length);
                buffer.Write(BodyData);
            }

            buffer.Write((ushort) Size.X);
            buffer.Write((ushort) Size.Y);
        }
    }
}
