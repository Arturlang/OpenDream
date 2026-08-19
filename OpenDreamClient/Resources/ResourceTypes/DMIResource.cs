using System.IO;
using System.Linq;
using System.Threading.Tasks;
using OpenDreamShared.Dream;
using OpenDreamShared.Resources;
using Robust.Client.Graphics;
using Robust.Shared.Graphics;
using Robust.Shared.Asynchronous;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;

namespace OpenDreamClient.Resources.ResourceTypes;

public sealed class DMIResource : DreamResource {
    public Texture Texture;
    public Vector2i IconSize;
    public DMIParser.ParsedDMIDescription Description;

    private readonly IClyde _clyde;
    private readonly ITaskManager _taskManager;
    private readonly int _mainThreadId;
    private Dictionary<string, State> _states;

    public DMIResource(int id, byte[] data, IClyde clyde, ITaskManager taskManager, int mainThreadId) : base(id, data) {
        _clyde = clyde;
        _taskManager = taskManager;
        _mainThreadId = mainThreadId;
        var processedData = ProcessDMIData();
        Texture = processedData.Texture;
        IconSize = processedData.IconSize;
        Description = processedData.Description;
        _states = processedData.States;
    }

    public override void UpdateData(byte[] data) {
        base.UpdateData(data);
        ApplyDMIData(ProcessDMIData());
    }

    private ProcessedDMIData ProcessDMIData() {
        using Stream dmiStream = new MemoryStream(Data);
        DMIParser.ParsedDMIDescription description = DMIParser.ParseDMI(dmiStream);

        dmiStream.Seek(0, SeekOrigin.Begin);

        Image<Rgba32> image = Image.Load<Rgba32>(dmiStream);
        return LoadTextureOnMainThread(image, description);
    }

    private ProcessedDMIData FinalizeDMIData(Image<Rgba32> image, DMIParser.ParsedDMIDescription description) {
        // Non-sRGB: the world pipeline does all math and blending on raw sRGB bytes,
        // matching BYOND's byte-space arithmetic (see docs/byond-parity-notes.md).
        var texture = _clyde.LoadTextureFromImage(image, name: $"DMI Resource #{Id}",
            loadParams: new TextureLoadParameters { Srgb = false });
        var iconSize = new Vector2i(description.Width, description.Height);
        var states = new Dictionary<string, State>();
        foreach (DMIParser.ParsedDMIState parsedState in description.States.Values) {
            State state = new State(texture, parsedState, description.Width, description.Height);

            states.Add(parsedState.Name, state);
        }

        return new ProcessedDMIData(texture, iconSize, description, states);
    }

    private ProcessedDMIData LoadTextureOnMainThread(Image<Rgba32> image, DMIParser.ParsedDMIDescription description) {
        if (Environment.CurrentManagedThreadId == _mainThreadId) {
            return FinalizeDMIData(image, description);
        }

        TaskCompletionSource<ProcessedDMIData> finished = new();

        _taskManager.RunOnMainThread(() => {
            try {
                finished.SetResult(FinalizeDMIData(image, description));
            } catch (Exception e) {
                finished.SetException(e);
            }
        });

        return finished.Task.GetAwaiter().GetResult();
    }

    private void ApplyDMIData(ProcessedDMIData data) {
        Texture = data.Texture;
        IconSize = data.IconSize;
        Description = data.Description;
        _states = data.States;
    }

    private sealed record ProcessedDMIData(Texture Texture, Vector2i IconSize, DMIParser.ParsedDMIDescription Description, Dictionary<string, State> States);

    public State? GetState(string? stateName) {
        if (stateName == null || !_states.ContainsKey(stateName))
            return _states.TryGetValue(string.Empty, out var state) ? state : null; // Default state, if one exists

        return _states[stateName];
    }

    public ICursor? GetStateAsImage(IClyde clyde, string? stateName) {
        using var dmiStream = new MemoryStream(Data);
        var description = DMIParser.ParseDMI(dmiStream);

        dmiStream.Seek(0, SeekOrigin.Begin);

        Image<Rgba32> image = Image.Load<Rgba32>(dmiStream);
        var state = description.GetStateOrDefault(stateName);
        if (!(state?.Directions.TryGetValue(AtomDirection.South, out var frames) ?? false))
            return null;

        var stateImage = image.Clone(clone => {
            var frame = frames[0];

            clone.Crop(new Rectangle(frame.X, frame.Y, frame.X + description.Width, frame.Y + description.Height));
        });

        var hotspot = state.Hotspot ?? (0, stateImage.Height - 1); // Default to the top-left
        var cursor = clyde.CreateCursor(stateImage, hotspot);
        return cursor;
    }

    public byte[]? GetStateAsPng(string? stateName, AtomDirection direction = AtomDirection.South, int frame = 0) {
        using var dmiStream = new MemoryStream(Data);
        var description = DMIParser.ParseDMI(dmiStream);

        dmiStream.Seek(0, SeekOrigin.Begin);

        using var image = Image.Load<Rgba32>(dmiStream);
        var state = description.GetStateOrDefault(stateName);
        if (state == null)
            return null;

        var frames = state.GetFrames(direction);
        if (frames.Length == 0)
            return null;

        frame = Math.Clamp(frame, 0, frames.Length - 1);
        var dmiFrame = frames[frame];
        using var stateImage = image.Clone(clone => {
            clone.Crop(new Rectangle(dmiFrame.X, dmiFrame.Y, description.Width, description.Height));
        });

        using var output = new MemoryStream();
        stateImage.SaveAsPng(output);
        return output.ToArray();
    }

    public string DescribeStatesForLog(int maxStates = 12) {
        var stateNames = Description.States.Keys.Take(maxStates);
        var suffix = Description.States.Count > maxStates ? ", ..." : string.Empty;

        return string.Join(", ", stateNames) + suffix;
    }

    public struct State {
        public Dictionary<AtomDirection, AtlasTexture[]> Frames;

        public State(Texture texture, DMIParser.ParsedDMIState parsedState, int width, int height) {
            Frames = new Dictionary<AtomDirection, AtlasTexture[]>();

            foreach (KeyValuePair<AtomDirection, DMIParser.ParsedDMIFrame[]> pair in parsedState.Directions) {
                AtomDirection dir = pair.Key;
                DMIParser.ParsedDMIFrame[] parsedFrames = pair.Value;
                AtlasTexture[] frames = new AtlasTexture[parsedFrames.Length];

                for (int i = 0; i < parsedFrames.Length; i++) {
                    DMIParser.ParsedDMIFrame parsedFrame = parsedFrames[i];

                    frames[i] = new AtlasTexture(texture, new UIBox2(parsedFrame.X, parsedFrame.Y, parsedFrame.X + width, parsedFrame.Y + height));
                }

                Frames.Add(dir, frames);
            }
        }

        public AtlasTexture[] GetFrames(AtomDirection direction) {
            // Find another direction to use if this one doesn't exist
            if (!Frames.ContainsKey(direction)) {
                // The diagonal directions attempt to use east/west
                if (direction is AtomDirection.Northeast or AtomDirection.Southeast)
                    direction = AtomDirection.East;
                else if (direction is AtomDirection.Northwest or AtomDirection.Southwest)
                    direction = AtomDirection.West;

                // Use the south direction if the above still isn't valid
                if (!Frames.ContainsKey(direction))
                    direction = AtomDirection.South;
            }

            return Frames[direction];
        }
    }
}
