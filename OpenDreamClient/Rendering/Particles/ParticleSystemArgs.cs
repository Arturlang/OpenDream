using Robust.Client.Graphics;
using Color = Robust.Shared.Maths.Color;

namespace OpenDreamClient.Rendering.Particles;

/// <summary>
///     Arguments for creating a particle system
/// </summary>
public sealed class ParticleSystemArgs(Func<Texture?> icon, Vector2i particleSystemSize, uint particleCount, float particlesPerSecond) {
    /// <summary>
    ///  Size of drawing surface
    /// </summary>
    public Vector2i ParticleSystemSize = particleSystemSize;

    /// <summary>
    ///  Maximum number of particles in this system. New particles will not be created while at this maximum.
    /// </summary>
    public uint ParticleCount = particleCount;

    /// <summary>
    ///  The number of new particles to create each second. No new particles will be created if we are at the maximum already.
    /// </summary>
    public float ParticlesPerSecond = particlesPerSecond;

    /// <summary>
    ///  The lower left hand back corner of the cuboid outside of which particles will be deactivated
    /// </summary>
    public Vector3?  LowerDrawBound;

    /// <summary>
    ///  The upper right hand front corner of the cuboid outside of which particles will be deactivated
    /// </summary>
    public Vector3? UpperDrawBound;

    /// <summary>
    /// The base transform to apply to all particles in this system
    /// </summary>
    public Matrix3x2? BaseTransform;

    //queried on each particle spawn

    /// <summary>
    /// A function which returns a float which is this particles lifespan in seconds. Defaults to infinity.
    /// </summary>
    public Func<float>? Lifespan;

    /// <summary>
    /// A function which returns a float which is this particles fade-out time in seconds
    /// </summary>
    public Func<float>? Fadeout;

    /// <summary>
    /// A function which returns a float which is this particles fade-in time in seconds
    /// </summary>
    public Func<float>? Fadein;

    /// <summary>
    /// A function which returns a Texture which is this particles texture at spawning
    /// </summary>
    public Func<Texture?> Icon = icon;

    /// <summary>
    /// A function which returns a Vector3 which is this particles position at spawning
    /// </summary>
    public Func<Vector3>? SpawnPosition;

    /// <summary>
    /// A function which returns a Vector3 which is this particles velocity at spawning
    /// </summary>
    public Func<Vector3>? SpawnVelocity;

    //queried every tick - arg is seconds particle has been alive. 0 for just spawned.

    /// <summary>
    /// A function which takes the life time of this particles and returns the Color of this particle
    /// </summary>
    public Func<float,Color>? Color;

    //queried on each particle spawn, in BYOND units: pixels, degrees clockwise, and rates per tick (0.1s)

    /// <summary>
    /// A function which returns this particle's scale at spawning
    /// </summary>
    public Func<Vector2>? Scale;

    /// <summary>
    /// A function which returns this particle's rotation at spawning, in degrees
    /// </summary>
    public Func<float>? Rotation;

    /// <summary>
    /// A function which returns how many degrees this particle turns each tick
    /// </summary>
    public Func<float>? Spin;

    /// <summary>
    /// A function which returns how much this particle's scale changes each tick
    /// </summary>
    public Func<Vector2>? Growth;

    /// <summary>
    /// A function which returns the proportion of velocity this particle loses each tick
    /// </summary>
    public Func<Vector3>? Friction;

    /// <summary>
    /// A function which returns a random change in velocity, queried for each particle every tick
    /// </summary>
    public Func<Vector3>? Drift;

    /// <summary>
    /// The change in velocity applied to every particle each tick
    /// </summary>
    public Vector3 Gravity;
}
