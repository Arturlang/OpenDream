// NOBYOND - implementation smoke test is not a BYOND parity test
/proc/RunTest()
	var/image/image = new
	var/obj/vis_target = new
	image.contents = list("inside")
	image.density = 1
	image.gender = FEMALE
	image.glide_size = 4
	image.infra_luminosity = 5
	image.invisibility = 6
	image.luminosity = 7
	image.opacity = 1
	image.pixel_step_size = 8
	image.suffix = "suffix"
	image.text = "text"
	image.verbs = list()
	image.vis_contents = list(vis_target)

	ASSERT(image.contents.len == 1)
	ASSERT(image.contents[1] == "inside")
	ASSERT(image.density == 1)
	ASSERT(image.gender == FEMALE)
	ASSERT(image.glide_size == 4)
	ASSERT(image.infra_luminosity == 5)
	ASSERT(image.invisibility == 6)
	ASSERT(image.luminosity == 7)
	ASSERT(image.opacity == 1)
	ASSERT(image.pixel_step_size == 8)
	ASSERT(image.suffix == "suffix")
	ASSERT(image.text == "text")
	ASSERT(image.verbs.len == 0)
	ASSERT(image.vis_contents.len == 1)

	var/mutable_appearance/appearance = new
	appearance.animate_movement = NO_STEPS
	appearance.screen_loc = "1,2"

	ASSERT(appearance.animate_movement == NO_STEPS)
	ASSERT(appearance.screen_loc == "1,2")
