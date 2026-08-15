using NUnit.Framework;
using OpenDreamShared.Interface.DMF;
using OpenDreamShared.Interface.Descriptors;
using Robust.Shared.IoC;
using Robust.Shared.Serialization.Manager;

namespace Content.Tests;

/// <summary>
/// Parsing regressions for the CHILD/splitter geometry that decides how a skin's panes
/// are sized. These cover the tgstation-style nested right-hand panel (buttons over chat
/// over input), where a wrongly-sized splitter visibly breaks that whole side of the UI.
/// </summary>
/// <remarks>
/// These stop at the descriptor layer. Verifying the pane rectangles that Splitter
/// actually produces needs a live client, since instantiating a Robust Control requires
/// IUserInterfaceManager - that is what tools/winget_parity is for.
/// </remarks>
[TestFixture]
public sealed class SkinLayoutTests : ContentUnitTest {
    /// <summary>
    /// RobustUnitTest doesn't initialize the serialization manager, and reading DMF
    /// attributes into descriptors goes through it.
    /// </summary>
    [OneTimeSetUp]
    public void InitializeSerialization() {
        IoCManager.Resolve<ISerializationManager>().Initialize();
    }

    /// <summary>
    /// A cut-down version of tgstation's skin.dmf right-hand side. The two CHILD elements
    /// are the interesting part: both sit far outside a 10%-90% split and both hide the
    /// splitter handle.
    /// </summary>
    private const string RightPanelDmf = """
window "info_and_buttons"
	elem "info_and_buttons"
		type = MAIN
		pos = 0,0
		size = 640x480
		is-pane = true
	elem "info_button_child"
		type = CHILD
		pos = 0,0
		size = 640x477
		left = "infobuttons"
		right = "infowindow"
		is-vert = false
		splitter = 2
		show-splitter = false

window "infowindow"
	elem "infowindow"
		type = MAIN
		pos = 281,5
		size = 640x475
		is-pane = true
	elem "info_split"
		type = CHILD
		pos = 0,5
		size = 640x475
		left = "info"
		right = "input_buttons"
		is-vert = false
		splitter = 97.5
		show-splitter = false
""";

    private static InterfaceDescriptor ParseSkin(string dmf) {
        var serializationManager = IoCManager.Resolve<ISerializationManager>();
        var parser = new DMFParser(new DMFLexer(dmf), serializationManager);
        var descriptor = parser.Interface();

        Assert.That(parser.Errors, Is.Empty, "DMF parse produced errors");
        return descriptor;
    }

    private static WindowDescriptor GetWindow(InterfaceDescriptor skin, string windowId) {
        foreach (var window in skin.WindowDescriptors) {
            if (window.Id.Value == windowId)
                return window;
        }

        Assert.Fail($"No window \"{windowId}\" in the parsed skin");
        return null!;
    }

    private static ControlDescriptorChild GetChild(InterfaceDescriptor skin, string windowId, string childId) {
        foreach (var control in GetWindow(skin, windowId).ControlDescriptors) {
            if (control is ControlDescriptorChild child && child.Id.Value == childId)
                return child;
        }

        Assert.Fail($"No CHILD element \"{childId}\" in window \"{windowId}\"");
        return null!;
    }

    /// <summary>
    /// Regression: the splitter percentage has to survive verbatim. Values outside
    /// 10%-90% used to be clamped, turning tgstation's 2% button bar into a 10% one and
    /// its 97.5% chat area into 90% - the visible break on the right-hand side.
    /// </summary>
    [Test]
    public void ExtremeChildSplitterValuesSurviveParsing() {
        var skin = ParseSkin(RightPanelDmf);

        Assert.Multiple(() => {
            Assert.That(GetChild(skin, "info_and_buttons", "info_button_child").Splitter.Value,
                Is.EqualTo(2f).Within(0.001f), "A 2% split must not be widened towards a 10% minimum");
            Assert.That(GetChild(skin, "infowindow", "info_split").Splitter.Value,
                Is.EqualTo(97.5f).Within(0.001f), "A 97.5% split must not be narrowed towards a 90% maximum");
        });
    }

    /// <summary>
    /// Regression: show-splitter was parsed but never applied, so a hidden handle still
    /// reserved its width and shrank both panes.
    /// </summary>
    [Test]
    public void ShowSplitterIsParsedAndDefaultsToTrue() {
        var skin = ParseSkin(RightPanelDmf);

        Assert.Multiple(() => {
            Assert.That(GetChild(skin, "info_and_buttons", "info_button_child").ShowSplitter.Value, Is.False);
            Assert.That(GetChild(skin, "infowindow", "info_split").ShowSplitter.Value, Is.False);

            // A CHILD that says nothing about the splitter keeps BYOND's visible default.
            Assert.That(new ControlDescriptorChild().ShowSplitter.Value, Is.True);
            Assert.That(new ControlDescriptorChild().Splitter.Value, Is.EqualTo(50f).Within(0.001f));
        });
    }

    /// <summary>
    /// The split axis and pane wiring have to round-trip too - swapping these silently
    /// mirrors the layout.
    /// </summary>
    [Test]
    public void ChildPaneWiringRoundTripsFromDmf() {
        var buttonSplit = GetChild(ParseSkin(RightPanelDmf), "info_and_buttons", "info_button_child");

        Assert.Multiple(() => {
            Assert.That(buttonSplit.IsVert.Value, Is.False);
            Assert.That(buttonSplit.Left.Value, Is.EqualTo("infobuttons"));
            Assert.That(buttonSplit.Right.Value, Is.EqualTo("infowindow"));
        });
    }

    /// <summary>
    /// Regression: a MAIN element's own id used to overwrite the window's id, so panes
    /// declared as "window X / elem Y" could not be looked up by X.
    /// </summary>
    [Test]
    public void MainElementDoesNotOverrideWindowId() {
        var skin = ParseSkin(RightPanelDmf);

        Assert.Multiple(() => {
            Assert.That(GetWindow(skin, "info_and_buttons").Id.Value, Is.EqualTo("info_and_buttons"));
            Assert.That(skin.GetElementDescriptor("infowindow"), Is.Not.Null);
        });
    }
}
