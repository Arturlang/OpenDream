using System.Diagnostics.CodeAnalysis;
using JetBrains.Annotations;
using Robust.Client.Graphics;
using Robust.Shared.Timing;

namespace OpenDreamClient.Rendering.Particles;

/// <summary>
///     System for creating and managing particle effects.
/// </summary>
[PublicAPI]
public sealed class ParticlesManager {
    private readonly Dictionary<EntityUid, ParticleSystem> _particleSystems = new();

    public void FrameUpdate(FrameEventArgs args) {
        // can't use parallel foreach here because IoC doesn't have context in parallel tasks
        foreach (var particleSys in _particleSystems.Values) {
            particleSys.FrameUpdate(args);
        }
    }

    public ParticleSystem CreateParticleSystem(EntityUid entity, ParticleSystemArgs args) {
        var newSystem = new ParticleSystem(args);
        _particleSystems.Add(entity, newSystem);
        return newSystem;
    }

    public void DestroyParticleSystem(EntityUid entity) {
        _particleSystems.Remove(entity);
    }

    public bool TryGetParticleSystem(EntityUid entity, [NotNullWhen(true)] out ParticleSystem? system) {
        return _particleSystems.TryGetValue(entity, out system);
    }
}

public sealed class ParticleSystem {
    //unchanging
    public Vector2i RenderSize => _particleSystemSize;

    /// <summary>
    ///  Size of drawing surface
    /// </summary>
    private Vector2i _particleSystemSize;

    /// <summary>
    ///  Length of a BYOND tick, the unit of particle velocities and other rates
    /// </summary>
    private const float TickSeconds = 0.1f;

    /// <summary>
    ///  Maximum number of particles in this system. New particles will not be created while at this maximum.
    /// </summary>
    private uint _particleCount;

    /// <summary>
    ///  The number of new particles to create each second. No new particles will be created if we are at the maximum already.
    /// </summary>
    private float _particlesPerSecond;

    /// <summary>
    ///  The lower left hand back corner of the cuboid outside of which particles will be deactivated
    /// </summary>
    private Vector3 _lowerBound;

    /// <summary>
    ///  The upper right hand front corner of the cuboid outside of which particles will be deactivated
    /// </summary>
    private Vector3 _upperBound;

    /// <summary>
    /// The base transform to apply to all particles in this system
    /// </summary>
    private Matrix3x2 _baseTransform;

    //queried on each particle spawn

    /// <summary>
    /// A function which returns a float which is this particles lifespan in seconds
    /// </summary>
    private Func<float> _lifespan;

    /// <summary>
    /// A function which returns a float which is this particles fade-out time in seconds
    /// </summary>
    private Func<float> _fadeout;

    /// <summary>
    /// A function which returns a float which is this particles fade-in time in seconds
    /// </summary>
    private Func<float> _fadein;

    /// <summary>
    /// A function which returns a Texture which is this particles texture at spawning. Null textures will be re-evaluated each frame until not null
    /// </summary>
    private Func<Texture?> _icon;

    /// <summary>
    /// A function which returns a Vector3 which is this particles position at spawning
    /// </summary>
    private Func<Vector3> _spawnPosition;

    /// <summary>
    /// A function which returns a Vector3 which is this particles velocity at spawning
    /// </summary>
    private Func<Vector3> _spawnVelocity;

    //queried every tick - arg is seconds particle has been alive. 0 for just spawned.

    /// <summary>
    /// A function which takes the life time of this particles and returns the Color of this particle
    /// </summary>
    private Func<float, Color> _color;

    // Rolled once per particle at spawning. Rates are per BYOND tick, angles in degrees clockwise
    private Func<Vector2> _scale;
    private Func<float> _rotation;
    private Func<float> _spin;
    private Func<Vector2> _growth;
    private Func<Vector3> _friction;

    /// <summary>
    /// A function which returns the random change in velocity applied to a particle each tick
    /// </summary>
    private Func<Vector3> _drift;

    /// <summary>
    /// The constant change in velocity applied to every particle each tick
    /// </summary>
    private Vector3 _gravity;

    /// <summary>
    /// Fractional particles carried over to the next frame, so spawning doesn't depend on the frame rate
    /// </summary>
    private float _spawnAccumulator;

    /// <summary>
    /// Internal store for particles for this system
    /// </summary>
    private Particle[] _particles;

    public ParticleSystem(ParticleSystemArgs args) {
        _particleSystemSize = args.ParticleSystemSize;
        _particleCount = args.ParticleCount;
        _particlesPerSecond = args.ParticlesPerSecond;
        _lowerBound = args.LowerDrawBound ?? new Vector3(-_particleSystemSize.X, -_particleSystemSize.Y, float.MinValue);
        _upperBound = args.UpperDrawBound ?? new Vector3(_particleSystemSize.X, _particleSystemSize.Y, float.MaxValue);
        _icon = args.Icon;
        _baseTransform = args.BaseTransform ?? Matrix3x2.Identity;
        _lifespan = args.Lifespan ?? (() => int.MaxValue);
        _fadeout = args.Fadeout ?? (() => 0);
        _fadein = args.Fadein ?? (() => 0);
        _spawnPosition = args.SpawnPosition ?? (() => Vector3.Zero);
        _spawnVelocity = args.SpawnVelocity ?? (() => Vector3.Zero);
        _color = args.Color ?? (_ => Color.White);
        _scale = args.Scale ?? (() => Vector2.One);
        _rotation = args.Rotation ?? (() => 0f);
        _spin = args.Spin ?? (() => 0f);
        _growth = args.Growth ?? (() => Vector2.Zero);
        _friction = args.Friction ?? (() => Vector3.Zero);
        _drift = args.Drift ?? (() => Vector3.Zero);
        _gravity = args.Gravity;

        _particles = new Particle[_particleCount];
        for (int i = 0; i < _particleCount; i++)
            _particles[i] = new();
    }

    public void UpdateSystem(ParticleSystemArgs args) {
        _particleSystemSize = args.ParticleSystemSize;
        if (_particleCount != args.ParticleCount) {
            _particleCount = args.ParticleCount;
            Particle[] newParticles = new Particle[_particleCount];
            for (int i = 0; i < _particleCount; i++)
                if (i < _particles.Length)
                    newParticles[i] = _particles[i];
                else
                    newParticles[i] = new();
            _particles = newParticles;
        }

        _particlesPerSecond = args.ParticlesPerSecond;
        _lowerBound = args.LowerDrawBound ?? new Vector3(-_particleSystemSize.X, -_particleSystemSize.Y, float.MinValue);
        _upperBound = args.UpperDrawBound ?? new Vector3(_particleSystemSize.X, _particleSystemSize.Y, float.MaxValue);
        _icon = args.Icon;
        _baseTransform = args.BaseTransform ?? Matrix3x2.Identity;
        _lifespan = args.Lifespan ?? (() => int.MaxValue);
        _fadeout = args.Fadeout ?? (() => 0);
        _fadein = args.Fadein ?? (() => 0);
        _spawnPosition = args.SpawnPosition ?? (() => Vector3.Zero);
        _spawnVelocity = args.SpawnVelocity ?? (() => Vector3.Zero);
        _color = args.Color ?? (_ => Color.White);
        _scale = args.Scale ?? (() => Vector2.One);
        _rotation = args.Rotation ?? (() => 0f);
        _spin = args.Spin ?? (() => 0f);
        _growth = args.Growth ?? (() => Vector2.Zero);
        _friction = args.Friction ?? (() => Vector3.Zero);
        _drift = args.Drift ?? (() => Vector3.Zero);
        _gravity = args.Gravity;
    }

    public void FrameUpdate(FrameEventArgs args) {
        // Velocity, spin and growth are per BYOND tick (0.1s), not per frame
        var ticks = args.DeltaSeconds / TickSeconds;

        _spawnAccumulator = Math.Min(_spawnAccumulator + _particlesPerSecond * args.DeltaSeconds, _particleCount);
        int particlesToSpawn = (int)_spawnAccumulator;
        _spawnAccumulator -= particlesToSpawn;

        int particlesSpawned = 0;
        for (int i = 0; i < _particleCount; i++) {
            if (_particles[i].Active) {
                _particles[i].Lifetime += args.DeltaSeconds;
                _particles[i].Color = _color(_particles[i].Lifetime);

                // Gravity, drift and friction change the velocity once per whole tick
                _particles[i].TickProgress += ticks;
                while (_particles[i].TickProgress >= 1f) {
                    _particles[i].TickProgress -= 1f;
                    _particles[i].Velocity += _gravity + _drift();
                    _particles[i].Velocity *= Vector3.One - _particles[i].Friction;
                }

                _particles[i].Position += _particles[i].Velocity * ticks;
                _particles[i].Rotation += _particles[i].Spin * ticks;
                _particles[i].Scale += _particles[i].Growth * ticks;
                if(_particles[i].Fadein > _particles[i].Lifetime)
                    _particles[i].Color.A = Math.Clamp(_particles[i].Lifetime/_particles[i].Fadein, 0, 1);
                if(_particles[i].Fadeout > _particles[i].Lifespan-_particles[i].Lifetime)
                    _particles[i].Color.A = Math.Clamp((_particles[i].Lifespan-_particles[i].Lifetime)/_particles[i].Fadeout, 0, 1);

                if (_particles[i].Lifetime > _particles[i].Lifespan || _particles[i].Position.X > _upperBound.X ||
                    _particles[i].Position.Y > _upperBound.Y || _particles[i].Position.Z > _upperBound.Z ||
                    _particles[i].Position.X < _lowerBound.X || _particles[i].Position.Y < _lowerBound.Y ||
                    _particles[i].Position.Z < _lowerBound.Z)
                    _particles[i].Active = false;

                _particles[i].Texture ??= _icon();
            }

            if (!_particles[i].Active && particlesSpawned < particlesToSpawn) {
                _particles[i].Lifetime = 0;
                _particles[i].TickProgress = 0;
                _particles[i].Texture = _icon();
                _particles[i].Position = _spawnPosition();
                _particles[i].Velocity = _spawnVelocity();
                _particles[i].Scale = _scale();
                _particles[i].Rotation = _rotation();
                _particles[i].Spin = _spin();
                _particles[i].Growth = _growth();
                _particles[i].Friction = _friction();
                _particles[i].Color = _color(_particles[i].Lifetime);
                _particles[i].Lifespan = _lifespan();
                _particles[i].Fadein = _fadein();
                _particles[i].Fadeout = _fadeout();
                _particles[i].Active = true;
                particlesSpawned++;
            }
        }
    }

    public void Draw(DrawingHandleWorld handle, Matrix3x2 transform) {
        Array.Sort(_particles, (p1, p2) => p1.Position.Z.CompareTo(p2.Position.Z));
        foreach (var particle in _particles) {
            if (particle is { Active: true, Texture: not null }) {
                // Scale and rotate each particle about its own centre; BYOND angles are clockwise
                var centre = new Vector2(particle.Position.X, particle.Position.Y) + particle.Texture.Size / 2f;
                var particleTransform = Matrix3x2.CreateTranslation(-centre) *
                                        Matrix3x2.CreateScale(particle.Scale) *
                                        Matrix3x2.CreateRotation(-particle.Rotation * MathF.PI / 180f) *
                                        Matrix3x2.CreateTranslation(centre);

                handle.SetTransform(_baseTransform * particleTransform * transform);
                handle.DrawTextureRect(particle.Texture!,
                    new Box2(new Vector2(particle.Position.X, particle.Position.Y),
                        new Vector2(particle.Position.X, particle.Position.Y) + particle.Texture!.Size),
                    particle.Color);
            }
        }
    }
}

internal struct Particle {
    public Texture? Texture;
    public Vector3 Position;
    public Vector3 Velocity;
    public Vector2 Scale;
    public float Rotation;
    public float Spin;
    public Vector2 Growth;
    public Vector3 Friction;
    public float TickProgress;
    public Color Color;
    public float Lifetime;
    public float Lifespan;
    public float Fadein;
    public float Fadeout;
    public bool Active;
}
