using Robust.Client.Graphics;
using Robust.Shared.Graphics;
using Robust.Shared.Utility;

namespace OpenDreamClient.Rendering;

public sealed class RenderTargetPool(IClyde clyde) {
    private readonly Dictionary<Vector2i, List<IRenderTexture>> _renderTargets = new();
    private readonly Dictionary<Vector2i, List<IRenderTexture>> _filteredRenderTargets = new();
    private readonly HashSet<IRenderTexture> _filteredSet = new();
    private readonly Stack<IRenderTexture> _renderTargetsToReturn = new();

    public IRenderTexture Rent(Vector2i size) {
        IRenderTexture result;

        if (!_renderTargets.TryGetValue(size, out var listResult)) {
            result = clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8));
        } else {
            result = listResult.Count > 0
                ? listResult.Pop()
                : clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8));
        }

        return result;
    }

    /// <summary>
    /// Rents a render target whose texture samples with bilinear filtering, for draws
    /// that scale or rotate the result. DMI atlas textures must stay nearest-sampled
    /// (filtering would bleed neighboring states), so smoothing goes through these.
    /// </summary>
    public IRenderTexture RentFiltered(Vector2i size) {
        IRenderTexture result;

        if (_filteredRenderTargets.TryGetValue(size, out var listResult) && listResult.Count > 0) {
            result = listResult.Pop();
        } else {
            result = clyde.CreateRenderTarget(size, new(RenderTargetColorFormat.Rgba8),
                new TextureSampleParameters { Filter = true });
            _filteredSet.Add(result);
        }

        return result;
    }

    public void ReturnAtEndOfFrame(IRenderTexture rental) {
        _renderTargetsToReturn.Push(rental);
    }

    public void Return(IRenderTexture rental) {
        var store = _filteredSet.Contains(rental) ? _filteredRenderTargets : _renderTargets;
        if (!store.TryGetValue(rental.Size, out var storeList)) {
            storeList = new List<IRenderTexture>(4);
            store.Add(rental.Size, storeList);
        }

        storeList.Add(rental);
    }

    [Access(typeof(DreamViewOverlay))]
    public void HandleEndOfFrame() {
        //some render targets need to be kept until the end of the render cycle, so return them here.
        while (_renderTargetsToReturn.TryPop(out var toReturn))
            Return(toReturn);
    }
}
