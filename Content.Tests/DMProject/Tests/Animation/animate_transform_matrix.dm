// NOBYOND - exercises OpenDream's transform handling, not a BYOND parity dump.
//
// Note: BYOND leaves /atom/var/transform null until it is assigned, while OpenDream
// hands back the identity matrix. That difference is deliberately not asserted here.
//
// The test harness runs procs to completion without a real tick loop, so this covers
// the transform state around animate() rather than the interpolation over time.
/proc/AssertClose(A, B)
	ASSERT(abs(A - B) < 0.0001)

/proc/AssertMatrix(matrix/M, a, b, c, d, e, f)
	ASSERT(!isnull(M))
	AssertClose(M.a, a)
	AssertClose(M.b, b)
	AssertClose(M.c, c)
	AssertClose(M.d, d)
	AssertClose(M.e, e)
	AssertClose(M.f, f)

/proc/RunTest()
	// An untouched atom sits on the shared default appearance.
	var/obj/bystander = new()
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)

	// Regression: writing one atom's transform used to be able to mutate that shared
	// default in place, silently giving every other atom the same matrix.
	var/obj/scaled = new()
	scaled.transform = matrix().Scale(2, 3)
	AssertMatrix(scaled.transform, 2, 0, 0, 0, 3, 0)
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)

	// An atom created after that write must still get a clean default.
	var/obj/latecomer = new()
	AssertMatrix(latecomer.transform, 1, 0, 0, 0, 1, 0)

	// Rotation and translation compose onto the atom without leaking either.
	var/obj/turned = new()
	turned.transform = matrix().Turn(90)
	AssertMatrix(turned.transform, 0, 1, 0, -1, 0, 0)
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)

	var/obj/moved = new()
	moved.transform = matrix().Translate(5, -7)
	AssertMatrix(moved.transform, 1, 0, 5, 0, 1, -7)
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)

	// Queuing a transform animation must not disturb any other atom's matrix, and must
	// leave the animated atom's own transform readable.
	var/obj/animated = new()
	animated.transform = matrix().Scale(2, 2)
	animate(animated, transform = matrix().Scale(4, 4), time = 1)

	ASSERT(!isnull(animated.transform))
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)
	AssertMatrix(scaled.transform, 2, 0, 0, 0, 3, 0)
	AssertMatrix(latecomer.transform, 1, 0, 0, 0, 1, 0)

	// A chained animate() on the same atom is accepted and still leaves others alone.
	animate(animated, transform = matrix(), time = 1)
	AssertMatrix(bystander.transform, 1, 0, 0, 0, 1, 0)
