using System.Diagnostics.CodeAnalysis;
using OpenDreamClient.Interface.Controls;
using OpenDreamShared.Interface.Descriptors;
using OpenDreamShared.Interface.DMF;
using Robust.Shared.Serialization.Manager;
using Robust.Shared.Serialization.Markdown.Mapping;

namespace OpenDreamClient.Interface;

[Virtual]
public partial class InterfaceElement {
    public DMFPropertyString Type => ElementDescriptor.Type;
    public DMFPropertyString Id => ElementDescriptor.Id;

    public ElementDescriptor ElementDescriptor;

    [Dependency] protected IDreamInterfaceManager InterfaceManager = default!;
    [Dependency] private ISerializationManager _serializationManager = default!;

    protected InterfaceElement(ElementDescriptor elementDescriptor) {
        ElementDescriptor = elementDescriptor;
        IoCManager.InjectDependencies(this);
    }

    public void PopulateElementDescriptor(MappingDataNode node, ISerializationManager serializationManager) {
        if (GetType() == typeof(ControlChild)) {
            // CHILD's top/bottom attributes alias to left/right
            // Code is duplicated in WindowDescriptor.CreateChildDescriptor()
            // TODO: A bit hacky. Remove this (may be worth abandoning RT's serialization manager)
            if (node.TryGet("top", out var topValue))
                node["left"] = topValue;
            if (node.TryGet("bottom", out var bottomValue))
                node["right"] = bottomValue;
        }

        try {
            MappingDataNode original =
                (MappingDataNode)serializationManager.WriteValue(ElementDescriptor.GetType(), ElementDescriptor);
            foreach (var key in node.Keys) {
                original.Remove(key);
            }

            MappingDataNode newNode = original.Merge(node);

            var descriptor = serializationManager.Read(ElementDescriptor.GetType(), newNode);
            if(descriptor is null) throw new NullReferenceException(); // We're in a try/catch anyway, just play it safe
            ElementDescriptor = (ElementDescriptor)descriptor;
            UpdateElementDescriptor();
        } catch (Exception e) {
            Logger.GetSawmill("opendream.interface").Error($"Error while populating values of \"{Id}\": {e}");
        }
    }

    /// <summary>
    /// Attempt to get a DMF property
    /// You only need to create an override for this if the property can't be straight read from the ElementDescriptor
    /// </summary>
    public virtual bool TryGetProperty(string property, [NotNullWhen(true)] out IDMFProperty? value) {
        MappingDataNode original =
                (MappingDataNode)_serializationManager.WriteValue(ElementDescriptor.GetType(), ElementDescriptor, alwaysWrite: true); //alwayswrite because we want to access all properties, even defaults
        if (original.TryGet(property, out var node) && _serializationManager.TryGetVariableType(ElementDescriptor.GetType(), property, out var propertyDef)) {
            var propertyValue = _serializationManager.Read(propertyDef, node);

            if (propertyValue is IDMFProperty dmfProperty) {
                value = dmfProperty;
                return true;
            }

            if (propertyValue is string stringProperty) {
                value = new DMFPropertyString(stringProperty);
                return true;
            }
        }

        value = null;
        return false;
    }

    public virtual IEnumerable<(string Name, IDMFProperty Value)> EnumerateProperties() {
        MappingDataNode original =
            (MappingDataNode)_serializationManager.WriteValue(ElementDescriptor.GetType(), ElementDescriptor, alwaysWrite: true);

        foreach (var property in original.Keys) {
            // Prefer whatever the element reports live. The descriptor only holds the values
            // declared in the DMF, so geometry like size/pos would otherwise come back as it
            // was written rather than as it was laid out - and TGUI reads its size from a
            // wildcard winget, so a stale value there mislays the whole interface.
            if (TryGetProperty(property, out var liveValue)) {
                yield return (property, liveValue);
                continue;
            }

            if (!original.TryGet(property, out var node) ||
                !_serializationManager.TryGetVariableType(ElementDescriptor.GetType(), property, out var propertyDef)) {
                continue;
            }

            object? propertyValue;
            try {
                propertyValue = _serializationManager.Read(propertyDef, node);
            } catch (Exception) {
                continue;
            }

            if (propertyValue is IDMFProperty dmfProperty) {
                yield return (property, dmfProperty);
            } else if (propertyValue is string stringProperty) {
                yield return (property, new DMFPropertyString(stringProperty));
            }
        }
    }

    // TODO: Replace PopulateElementDescriptor with this
    public virtual void SetProperty(string property, string value, bool manualWinset = false) {
        MappingDataNode node = new() {
            {property, value}
        };

        PopulateElementDescriptor(node, _serializationManager);
    }

    protected virtual void UpdateElementDescriptor() {
    }

    public virtual void AddChild(ElementDescriptor descriptor) {
        throw new InvalidOperationException($"{this} cannot add a child");
    }

    public virtual void Shutdown() {
    }
}
