/proc/RunTest()
	var/icon/I = new('icons.dmi', "mob")

	I.DrawBox("#ff0000", 1, 1, 2, 1)
	ASSERT(I.GetPixel(1, 1) == "#ff0000")
	ASSERT(I.GetPixel(2, 1) == "#ff0000")

	I.SwapColor("#ff0000", "#00ff00")
	ASSERT(I.GetPixel(1, 1) == "#00ff00")

	// MapColors takes colour-matrix components, not from/to pairs. An identity
	// matrix has to leave the icon untouched.
	I.MapColors(1,0,0, 0,1,0, 0,0,1)
	ASSERT(I.GetPixel(1, 1) == "#00ff00")

	I.SwapColor("#00ff00", "#0000ff")
	ASSERT(I.GetPixel(1, 1) == "#0000ff")

	I.Shift(EAST, 1, FALSE)
	ASSERT(I.GetPixel(2, 1) == "#0000ff")
	ASSERT(isnull(I.GetPixel(1, 1)))

	I.Crop(2, 1, 2, 1)
	ASSERT(I.Width() == 1)
	ASSERT(I.Height() == 1)
	ASSERT(I.GetPixel(1, 1) == "#0000ff")

	I.DrawBox("#808080", 1, 1)
	I.SetIntensity(0.5, 1, 1)
	ASSERT(I.GetPixel(1, 1) == "#408080")
