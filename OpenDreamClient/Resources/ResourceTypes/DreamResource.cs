using System.IO;
using JetBrains.Annotations;

namespace OpenDreamClient.Resources.ResourceTypes;

[Virtual]
public class DreamResource {
    public readonly int Id;
    public List<Action> OnUpdateCallbacks = new();

    protected byte[] Data;

    [UsedImplicitly]
    public DreamResource(int id, byte[] data) {
        Id = id;
        Data = data;
    }

    public void WriteTo(Stream stream) {
        stream.Write(Data);
    }

    /// <summary>
    /// A copy of the raw bytes, for handing a resource to something that wants a real
    /// file - fonts, for instance, which Robust loads through its own resource cache.
    /// </summary>
    public byte[] CopyData() => (byte[])Data.Clone();

    public virtual void UpdateData(byte[] data) {
        Data = data;
    }
}
