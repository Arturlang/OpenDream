"""External file IO: file(), file2text, text2file, fexists, fdel, fcopy, fcopy_rsc, flist, ftime, isfile,
length()/md5()/sha1() of files, and the << / >> operators on file objects. No savefiles.

Every case that touches the disk starts with files_reset() (fdel("fs_tmp/")) and records its result through
files_done(), which deletes fs_tmp/ again. Paths are written with tokens that expand to a folder unique to the
case ("fs_tmp/<hash of the case>"), so OD's process-wide resource cache can't carry a file's contents from one
case into another:  @ -> fs_tmp/<h>   @B -> the same with backslashes   @U -> upper-cased.

BYOND reference points targeted here:
- text2file appends Text with no line break added and creates the file (and, presumably, missing folders);
  returns 1 on success, 0 otherwise.
- file2text returns the file's contents (null for a missing file); file(Path) does not touch the disk.
- fdel: a path ending in "/" is a directory and is deleted with its contents; returns 1/0.
- fcopy(Src, Dst): Src may be a cache file, a savefile or an external file name; Dst folders are created;
  with both paths ending in "/" the directory contents (and sub-directories) are copied.
- fcopy_rsc returns a cache entry; a cache entry passed in is returned as is.
- flist("dir/prefix") lists names directly in dir that BEGIN with prefix; sub-directories get a trailing "/";
  flist("dir") (no slash) gives back "dir/".
- ftime(File, IsCreationTime) returns a time value (only its kind is recorded here).
- isfile is true for file() objects and cache files.
- length(file) is the file's length; md5/sha1 of a file() hash its contents (null if missing), of a text path
  hash the name.

OpenDream divergences these cases aim at (DreamProcNativeRoot.cs, DreamResourceManager.cs, DreamResource.cs):
- text2file goes through AppendLinesToFile: every call adds Environment.NewLine, and ReplaceLineEndings turns
  \\n, \\r, \\r\\n, form feed, NEL (U+0085), LS/PS (U+2028/9) into CRLF. A file() object as File returns 0.
  Non-text Text writes "" (not "[Text]").
- file2text replaces CRLF with LF; file2text/length/md5 of a file read earlier keep the cached bytes after
  fdel/fcopy (only text2file reloads), and the cache key differs for backslash paths given to file().
- fexists uses File.Exists, so directories are "missing"; non-text args give null.
- fdel of a missing file returns 1 (File.Delete doesn't throw); non-text non-file args throw.
- fcopy of a directory fails (LoadResource has no data); Dst must be text.
- flist uses the last path part as an exact search pattern (no prefix matching, wildcards honoured);
  a missing directory gives an empty list; a non-text Path lists "./".
- ftime: non-text File throws; a missing file gives a 1601-based negative time.
- F << X appends X + CRLF and throws for non-text; F >> V is not implemented for files.
"""
import hashlib
from pools import TEXT, TEXT_S, NUM_S, OTHER, ANY
from gen import dm_str

Q = dm_str


def build(s):
    s.dm(DM)

    def fc(proc, lines, expr):
        """A disk case: tokens expanded, reset first, fs_tmp/ deleted after the result is computed."""
        if isinstance(lines, str):
            lines = [lines]
        key = "\n".join(lines) + "\n" + expr
        h = hashlib.sha1(key.encode()).hexdigest()[:6]
        d = f"fs_tmp/{h}"

        def sub(t):
            return t.replace("@B", d.replace("/", "\\\\")).replace("@U", d.upper()).replace("@", d)
        body = ["files_reset()"] + [sub(l) for l in lines]
        return s.body(proc, body, f"files_done({sub(expr)})",
                      display="; ".join(lines) + " => " + expr)

    INFO = 'files_info("@/t.txt")'

    # =============================================================================== file() (no disk access)
    FILE_ARGS = ANY + [Q(t) for t in ["fs_tmp/a.txt", "fs_tmp/sub/x.txt", "fs_tmp\\x.txt", "./fs_tmp/x",
                                      "fs_tmp/", "fs_tmp", "FS_TMP/A.TXT", "fs_tmp//a", "fs_tmp/é日.txt",
                                      "fs_tmp/a b.txt", "test.dmi"]] + ["'test.dmi'", "'small.dmi'",
                                                                      'file("fs_tmp/a.txt")', "PINF", "NAN", "1.5"]
    for a in FILE_ARGS:
        s.case("file", f"file({a})")
        s.case("file", f'"[file({a})]"')
        s.case("file", f"isfile(file({a}))")
    for e in ['file()', 'file("fs_tmp/a.txt", "fs_tmp/b.txt")', 'file(Path = "fs_tmp/a.txt")',
              'file("fs_tmp/a.txt") == file("fs_tmp/a.txt")', 'file("fs_tmp/a.txt") == "fs_tmp/a.txt"',
              'file("fs_tmp/a.txt") == file("fs_tmp/b.txt")', "file('test.dmi') == 'test.dmi'",
              'file("test.dmi") == \'test.dmi\'', 'file(file("fs_tmp/a.txt")) == file("fs_tmp/a.txt")',
              'istext(file("fs_tmp/a.txt"))', 'ispath(file("fs_tmp/a.txt"))', 'isnull(file("fs_tmp/a.txt"))',
              'istype(file("fs_tmp/a.txt"), /datum)', 'isicon(file("fs_tmp/a.txt"))', "isicon(file('test.dmi'))",
              'isicon(file("test.dmi"))', 'length("[file("fs_tmp/a.txt")]")',
              'file("fs_tmp/a.txt") in list(file("fs_tmp/a.txt"))', 'list(file("fs_tmp/a.txt"))',
              'list(file("fs_tmp/a.txt") = 1)', 'file("fs_tmp/a.txt") + "x"', '"x" + file("fs_tmp/a.txt")',
              '!file("fs_tmp/a.txt")', 'file("fs_tmp/a.txt") ? 1 : 0', 'file("") ? 1 : 0',
              'fexists("fs_tmp/never.txt")']:
        s.case("file", e)
    fc("file", 'var/F = file("@/t.txt")', 'list(fexists("@/t.txt"), length(F), isfile(F))')

    # =============================================================================== isfile
    s.sweep("isfile", [ANY], min_args=1)
    for e in ["isfile('test.dmi')", "isfile('small.dmi')", 'isfile("test.dmi")', "isfile(icon('test.dmi'))",
              "isfile(new /icon('test.dmi'))", "isfile(image('test.dmi'))", 'isfile(fcopy_rsc("test.dmi"))',
              "isfile(fcopy_rsc('test.dmi'))", 'isfile(sound("fs_tmp/x.ogg"))', 'isfile(file("fs_tmp/x"))',
              'isfile(file("fs_tmp/x"), 1)', 'isfile()', 'isfile(list(file("fs_tmp/x")))',
              'isfile(world)', 'isfile(/icon)', 'isfile("[file("fs_tmp/x")]")']:
        s.case("isfile", e)
    fc("isfile", 'text2file("abc", "@/t.txt")', 'list(isfile(fcopy_rsc("@/t.txt")), isfile(fcopy_rsc(file("@/t.txt"))))')

    # =============================================================================== text2file
    # Every pool value as Text: return value and the exact bytes written
    for t in TEXT + NUM_S + OTHER + ["NAN", "NINF", "1e7", "0.1", "'test.dmi'", 'file("fs_tmp/zz.txt")',
                                     "/obj", "world", "matrix()"]:
        fc("text2file", f'var/r = text2file({t}, "@/t.txt")', f"list(r, {INFO})")
    # Line endings and characters .NET ReplaceLineEndings rewrites; raw bytes via length/md5
    LE = {
        "LF": "a\nb", "CRLF": "a[ascii2text(13)]\nb", "CR": "a[ascii2text(13)]b", "LFLF": "a\n\nb",
        "trail_LF": "a\n", "lead_LF": "\na", "only_LF": "\n", "only_CR": "[ascii2text(13)]",
        "CRCRLF": "a[ascii2text(13)][ascii2text(13)]\nb", "LFCR": "a\n[ascii2text(13)]b",
        "FF": "a[ascii2text(12)]b", "VT": "a[ascii2text(11)]b", "NEL": "a[ascii2text(133)]b",
        "LS": "a[ascii2text(8232)]b", "PS": "a[ascii2text(8233)]b", "TAB": "a\tb", "NUL": "a[ascii2text(0)]b",
        "BOM": "[ascii2text(65279)]abc", "DEL": "a[ascii2text(127)]b", "ESC": "a[ascii2text(27)]b",
        "U+FFFD": "a[ascii2text(65533)]b", "emoji": "🙂", "latin1": "[ascii2text(233)][ascii2text(255)]",
    }
    for name, src in LE.items():
        src = src.replace("\n", "\\n").replace("\t", "\\t")
        fc("text2file", [f'var/T = "{src}"', 'var/r = text2file(T, "@/t.txt")'],
           f'list(r, {INFO}, md5(file("@/t.txt")) == md5(T), file2text("@/t.txt") == T)')
    # Appending, creation of folders, odd paths
    for lines, expr in [
        (['text2file("a", "@/t.txt")', 'text2file("b", "@/t.txt")'], INFO),
        (['text2file("a\\n", "@/t.txt")', 'text2file("b\\n", "@/t.txt")'], INFO),
        (['text2file("", "@/t.txt")'], INFO),
        (['text2file("", "@/t.txt")', 'text2file("", "@/t.txt")'], INFO),
        (['text2file(null, "@/t.txt")'], INFO),
        (['text2file("a", "@/t.txt")', 'text2file(null, "@/t.txt")', 'text2file("b", "@/t.txt")'], INFO),
        (['var/r = text2file("x", "@/d1/d2/d3/t.txt")'], 'list(r, files_info("@/d1/d2/d3/t.txt"), files_sort(flist("@/d1/")))'),
        (['var/r = text2file("x", "@B\\\\t.txt")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@B\\\\sub\\\\t.txt")'], 'list(r, files_info("@/sub/t.txt"))'),
        (['var/r = text2file("x", "./@/t.txt")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@//t.txt")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@/./t.txt")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@/sub/../t.txt")'], f'list(r, {INFO}, fexists("@/sub/"))'),
        (['var/r = text2file("x", "@U/T.TXT")'], f'list(r, {INFO}, files_sort(flist("@/")))'),
        (['text2file("a", "@/t.txt")', 'var/r = text2file("b", "@U/T.TXT")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@/é日本.txt")'], 'list(r, files_info("@/é日本.txt"), files_sort(flist("@/")))'),
        (['var/r = text2file("x", "@/a b.txt")'], 'list(r, files_info("@/a b.txt"))'),
        (['var/r = text2file("x", "@/noext")'], 'list(r, files_info("@/noext"))'),
        (['var/r = text2file("x", "@/.hidden")'], 'list(r, files_info("@/.hidden"), files_sort(flist("@/")))'),
        (['var/r = text2file("x", "@/t.txt.")'], 'list(r, files_info("@/t.txt."), files_info("@/t.txt"))'),
        (['var/r = text2file("x", "@/d/")'], 'list(r, fexists("@/d/"), fexists("@/d"), files_sort(flist("@/")))'),
        (['text2file("x", "@/d/t.txt")', 'var/r = text2file("y", "@/d")'], 'list(r, fexists("@/d"), files_sort(flist("@/")))'),
        (['var/r = text2file("x", file("@/t.txt"))'], f'list(r, {INFO})'),
        (['var/F = file("@/t.txt")', 'var/r = text2file("x", F)', 'var/r2 = text2file("y", F)'], f'list(r, r2, {INFO}, length(F))'),
        (['var/r = text2file("x", null)'], 'r'),
        (['var/r = text2file("x", "")'], 'r'),
        (['var/r = text2file("x")'], 'r'),
        (['var/r = text2file()'], 'r'),
        (['var/r = text2file("x", "@/t.txt", "y")'], f'list(r, {INFO})'),
        (['var/r = text2file(Text = "x", File = "@/t.txt")'], f'list(r, {INFO})'),
        (['var/r = text2file(File = "@/t.txt", Text = "x")'], f'list(r, {INFO})'),
        (['var/r = text2file("x", "@/\'q\'.txt")'], 'list(r, files_info("@/\'q\'.txt"), files_sort(flist("@/")))'),
        # A long text
        (['var/T = ""', 'for(var/i in 1 to 200)', '\tT += "line [i]\\n"', 'var/r = text2file(T, "@/t.txt")'],
         'list(r, length(file("@/t.txt")), md5(file("@/t.txt")) == md5(T), length(file2text("@/t.txt")))'),
    ]:
        fc("text2file", lines, expr)

    # =============================================================================== file2text
    s.sweep("file2text", [ANY], min_args=1)
    for e in ["length(file2text('test.dmi'))", "md5(file2text('test.dmi'))", "text2ascii(file2text('test.dmi'), 1)",
              "text2ascii(file2text('test.dmi'), 2)", "copytext(file2text('test.dmi'), 2, 5)",
              'length(file2text("test.dmi"))', 'md5(file2text("test.dmi")) == md5(file2text(\'test.dmi\'))',
              "length(file2text('small.dmi'))", "length(file2text(icon('test.dmi')))",
              'file2text("fs_tmp/never.txt")', 'file2text(file("fs_tmp/never.txt"))', 'file2text()',
              'file2text("fs_tmp/never.txt", 1)', 'file2text(File = "fs_tmp/never.txt")',
              'isnull(file2text("fs_tmp/never.txt"))']:
        s.case("file2text", e)
    for lines, expr in [
        (['text2file("abc", "@/t.txt")'], 'file2text("@/t.txt")'),
        (['text2file("abc", "@/t.txt")'], 'file2text(file("@/t.txt"))'),
        (['text2file("abc", "@/t.txt")'], 'file2text("@B\\\\t.txt")'),
        (['text2file("abc", "@/t.txt")'], 'file2text(file("@B\\\\t.txt"))'),
        (['text2file("abc", "@/t.txt")'], 'file2text("./@/t.txt")'),
        (['text2file("abc", "@/t.txt")'], 'file2text("@U/T.TXT")'),
        (['text2file("abc", "@/t.txt")'], 'file2text("@/sub/../t.txt")'),
        (['text2file("abc", "@/t.txt")'], 'file2text(fcopy_rsc("@/t.txt"))'),
        (['text2file("", "@/t.txt")'], 'list(file2text("@/t.txt"), isnull(file2text("@/t.txt")), istext(file2text("@/t.txt")))'),
        (['text2file("abc", "@/d/t.txt")'], 'list(file2text("@/d/"), file2text("@/d"))'),
        (['text2file("a[ascii2text(13)]\\nb[ascii2text(13)]\\n", "@/t.txt")'], 'files_codes(file2text("@/t.txt"))'),
        (['text2file("a[ascii2text(13)]b", "@/t.txt")'], 'files_codes(file2text("@/t.txt"))'),
        (['text2file("[ascii2text(65279)]abc", "@/t.txt")'], 'files_codes(file2text("@/t.txt"))'),
        (['text2file("é🙂日", "@/t.txt")'], 'list(file2text("@/t.txt"), length(file2text("@/t.txt")), length_char(file2text("@/t.txt")))'),
        (['text2file("\\[b\\] <i> &amp; \\\\n", "@/t.txt")'], 'file2text("@/t.txt")'),
        (['fcopy(\'test.dmi\', "@/t.dmi")'], 'list(length(file2text("@/t.dmi")), md5(file2text("@/t.dmi")) == md5(file2text(\'test.dmi\')), text2ascii(file2text("@/t.dmi"), 1))'),
        (['fcopy(\'test.dmi\', "@/t.txt")'], 'length(file2text("@/t.txt"))'),
        # Reads after the file changed underneath (OD's resource cache)
        (['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', 'text2file("two", "@/t.txt")'], 'list(a, file2text("@/t.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', 'fdel("@/t.txt")'], 'list(a, file2text("@/t.txt"), fexists("@/t.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', 'fdel("@/t.txt")', 'text2file("two", "@/t.txt")'], 'list(a, file2text("@/t.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', 'fdel("@/")'], 'list(a, file2text("@/t.txt"))'),
        (['text2file("one", "@/t.txt")', 'text2file("other", "@/u.txt")', 'var/a = file2text("@/t.txt")', 'fcopy("@/u.txt", "@/t.txt")'], 'list(a, file2text("@/t.txt"), length(file("@/t.txt")))'),
        (['text2file("one", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/a = file2text(F)', 'text2file("two", "@/t.txt")'], 'list(a, file2text(F))'),
        (['text2file("one", "@/t.txt")', 'var/F = file("@B\\\\t.txt")', 'var/a = file2text(F)', 'text2file("two", "@/t.txt")'], 'list(a, file2text(F), length(F))'),
        (['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', 'var/F = file("@/t.txt")', 'F << "two"'], 'list(a, file2text("@/t.txt"))'),
        (['var/a = file2text("@/t.txt")', 'text2file("now", "@/t.txt")'], 'list(a, file2text("@/t.txt"))'),
        (['var/F = file("@/t.txt")', 'var/a = file2text(F)', 'text2file("now", "@/t.txt")'], 'list(a, file2text(F), length(F))'),
    ]:
        fc("file2text", lines, expr)

    # =============================================================================== fexists
    s.sweep("fexists", [ANY], min_args=1)
    for e in ["fexists('test.dmi')", 'fexists("test.dmi")', 'fexists("TEST.DMI")', 'fexists("./test.dmi")',
              'fexists(".\\\\test.dmi")', 'fexists(file("test.dmi"))', 'fexists(file("fs_tmp/never.txt"))',
              "fexists(icon('test.dmi'))", 'fexists("test")', 'fexists("test.dm")', 'fexists("*.dmi")',
              'fexists("test.dm?")', 'fexists("parity.dm")', 'fexists("fs_tmp/never/")', 'fexists()',
              'fexists("test.dmi", 1)', 'fexists(File = "test.dmi")', 'fexists("")', 'fexists(".")',
              'fexists("./")', 'fexists("test.dmi/")', 'fexists(" test.dmi")', 'fexists("test.dmi ")']:
        s.case("fexists", e)
    for lines, expr in [
        (['text2file("x", "@/t.txt")'], 'list(fexists("@/t.txt"), fexists("@/T.TXT"), fexists("@B\\\\t.txt"), fexists(file("@/t.txt")), fexists("@/t"), fexists("@/t.tx"), fexists("@/t.txt/"))'),
        (['text2file("x", "@/d/t.txt")'], 'list(fexists("@/d"), fexists("@/d/"), fexists("@B\\\\d\\\\"), fexists("@/d/."), fexists("@"), fexists("@/"), fexists("fs_tmp/"), fexists("fs_tmp"))'),
        (['text2file("x", "@/t.txt")', 'fdel("@/t.txt")'], 'list(fexists("@/t.txt"), fexists("@/"))'),
        (['text2file("x", "@/t.txt")', 'var/F = file("@/t.txt")', 'fdel("@/t.txt")'], 'list(fexists(F), fexists("@/t.txt"))'),
        (['text2file("", "@/t.txt")'], 'fexists("@/t.txt")'),
        (['text2file("x", "@/é日本.txt")'], 'list(fexists("@/é日本.txt"), fexists("@/É日本.TXT"))'),
        (['text2file("x", "@/t.txt")'], 'fexists(fcopy_rsc("@/t.txt"))'),
        (['text2file("x", "@/t.txt")'], 'fexists("@/sub/../t.txt")'),
    ]:
        fc("fexists", lines, expr)

    # =============================================================================== fdel
    # Only paths inside fs_tmp/ (and file objects for them); nothing that could name the world's folder
    for lines, expr in [
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/t.txt")'], 'list(r, fexists("@/t.txt"), files_sort(flist("@/")))'),
        (['var/r = fdel("@/missing.txt")'], 'r'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/missing.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['var/r = fdel("@/nodir/")'], 'r'),
        (['var/r = fdel("fs_tmp/never/never/")'], 'r'),
        (['text2file("x", "@/d/t.txt")', 'text2file("y", "@/d/e/u.txt")', 'var/r = fdel("@/d/")'], 'list(r, fexists("@/d/t.txt"), fexists("@/d/e/u.txt"), flist("@/"))'),
        (['text2file("x", "@/d/t.txt")', 'var/r = fdel("@/d")'], 'list(r, fexists("@/d/t.txt"), files_sort(flist("@/")))'),
        (['text2file("x", "@/d/t.txt")', 'fdel("@/d/t.txt")', 'var/r = fdel("@/d")'], 'list(r, files_sort(flist("@/")))'),
        (['text2file("x", "@/d/t.txt")', 'fdel("@/d/t.txt")', 'var/r = fdel("@/d/")'], 'list(r, files_sort(flist("@/")))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/t.txt/")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel(file("@/t.txt"))'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/a = length(F)', 'var/r = fdel(F)'], 'list(a, r, fexists("@/t.txt"), length(F), file2text(F))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@B\\\\t.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/d/t.txt")', 'var/r = fdel("@B\\\\d\\\\")'], 'list(r, fexists("@/d/t.txt"), files_sort(flist("@/")))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@U/T.TXT")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("./@/t.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/a.txt")', 'text2file("x", "@/b.txt")', 'text2file("x", "@/c.dat")', 'var/r = fdel("@/*.txt")'], 'list(r, files_sort(flist("@/")))'),
        (['text2file("x", "@/a1.txt")', 'text2file("x", "@/a2.txt")', 'var/r = fdel("@/a?.txt")'], 'list(r, files_sort(flist("@/")))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/t")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r1 = fdel("@/t.txt")', 'var/r2 = fdel("@/t.txt")'], 'list(r1, r2)'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel(File = "@/t.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/t.txt", 1)'], 'list(r, fexists("@/t.txt"))'),
        (['var/r = fdel()'], 'r'),
        (['text2file("x", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")', 'var/r = fdel(R)'], 'list(r, fexists("@/t.txt"), length(R))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/sub/../t.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@//t.txt")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/é日本.txt")', 'var/r = fdel("@/é日本.txt")'], 'list(r, fexists("@/é日本.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@")'], 'list(r, fexists("@/t.txt"))'),
        (['text2file("x", "@/t.txt")', 'var/r = fdel("@/")'], 'list(r, fexists("@/t.txt"), fexists("@/"), files_sort(flist("fs_tmp/")))'),
    ]:
        fc("fdel", lines, expr)
    s.case("fdel", 'fdel(123)')

    # =============================================================================== fcopy
    SRC_WRONG = ["null", "123", "list()", "/datum", "new /datum", "PINF", '""', "'test.dmi'", "icon('test.dmi')",
                 '"test.dmi"', 'file("test.dmi")', "image('test.dmi')", '"fs_tmp/never.txt"', 'file("fs_tmp/never.txt")']
    for src in SRC_WRONG:
        fc("fcopy", f'var/r = fcopy({src}, "@/c.dat")', 'list(r, fexists("@/c.dat"), length(file("@/c.dat")))')
    for dst in ["null", 'file("@/c.dat")', '"@/c.dat"', '"@/new/sub/c.dat"', '"@/d/"', '"@B\\\\c.dat"',
                '"@U/C.DAT"', '"./@/c.dat"', '"@/t.txt"', '"@/é.dat"']:
        fc("fcopy", ['text2file("data", "@/t.txt")', f'var/r = fcopy("@/t.txt", {dst})'],
           'list(r, files_sort(flist("@/")), file2text("@/t.txt"), files_info("@/c.dat"))')
    for lines, expr in [
        (['var/r = fcopy(\'test.dmi\', "@/t.dmi")'], 'list(r, length(file("@/t.dmi")) == length(\'test.dmi\'), md5(file("@/t.dmi")) == md5(\'test.dmi\'), sha1(file("@/t.dmi")) == sha1(\'test.dmi\'))'),
        (['var/r = fcopy(\'test.dmi\', "@/t.dmi")'], 'list(r, icon_states(icon(file("@/t.dmi"))))'),
        (['var/r = fcopy(icon(\'test.dmi\', "solid"), "@/t.dmi")'], 'list(r, fexists("@/t.dmi"), icon_states(icon(file("@/t.dmi"))))'),
        (['var/r = fcopy(\'small.dmi\', "@/t.png")'], 'list(r, md5(file("@/t.png")) == md5(\'small.dmi\'))'),
        (['text2file("one", "@/t.txt")', 'text2file("two", "@/u.txt")', 'var/r = fcopy("@/t.txt", "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/r = fcopy(file("@/t.txt"), "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/r = fcopy(fcopy_rsc("@/t.txt"), "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("one", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")', 'fdel("@/t.txt")', 'var/r = fcopy(R, "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/u.txt")'], 'list(r, files_info("@/u.txt"))'),
        (['text2file("a[ascii2text(13)]\\nb", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/u.txt")'], 'list(r, md5(file("@/u.txt")) == md5(file("@/t.txt")), length(file("@/u.txt")))'),
        # Directory copies
        (['text2file("1", "@/s/a.txt")', 'text2file("2", "@/s/sub/b.txt")', 'var/r = fcopy("@/s/", "@/d/")'],
         'list(r, files_sort(flist("@/d/")), files_sort(flist("@/d/sub/")), file2text("@/d/sub/b.txt"), files_sort(flist("@/s/")))'),
        (['text2file("1", "@/s/a.txt")', 'var/r = fcopy("@/s/", "@/d")'], 'list(r, files_sort(flist("@/")), files_sort(flist("@/d/")))'),
        (['text2file("1", "@/s/a.txt")', 'var/r = fcopy("@/s", "@/d/")'], 'list(r, files_sort(flist("@/")), files_sort(flist("@/d/")))'),
        (['text2file("1", "@/s/a.txt")', 'var/r = fcopy("@/s", "@/d")'], 'list(r, files_sort(flist("@/")))'),
        (['text2file("1", "@/s/a.txt")', 'text2file("old", "@/d/a.txt")', 'text2file("keep", "@/d/k.txt")', 'var/r = fcopy("@/s/", "@/d/")'],
         'list(r, files_sort(flist("@/d/")), file2text("@/d/a.txt"))'),
        (['var/r = fcopy("@/nosuch/", "@/d/")'], 'list(r, fexists("@/d/"), files_sort(flist("@/")))'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/t.txt")'], 'list(r, file2text("@/t.txt"))'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy("@B\\\\t.txt", "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy("@/t.txt")'], 'list(r, files_sort(flist("@/")))'),
        (['var/r = fcopy()'], 'r'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy(Src = "@/t.txt", Dst = "@/u.txt")'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/u.txt", 1)'], 'list(r, file2text("@/u.txt"))'),
        (['text2file("1", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/s/")', 'var/r2 = fcopy("@/s/", "@/d/")'], 'list(r, r2, files_sort(flist("@/")), files_sort(flist("@/s/")))'),
    ]:
        fc("fcopy", lines, expr)

    # =============================================================================== fcopy_rsc
    s.sweep("fcopy_rsc", [ANY], min_args=1)
    for e in ["fcopy_rsc('test.dmi')", "fcopy_rsc('test.dmi') == 'test.dmi'", "isfile(fcopy_rsc('test.dmi'))",
              'fcopy_rsc("test.dmi") == \'test.dmi\'', 'md5(fcopy_rsc("test.dmi")) == md5(\'test.dmi\')',
              'isfile(fcopy_rsc("test.dmi"))', 'isicon(fcopy_rsc("test.dmi"))', "isicon(fcopy_rsc(icon('test.dmi')))",
              "isfile(fcopy_rsc(icon('test.dmi')))", "icon_states(fcopy_rsc(icon('test.dmi', \"grad\")))",
              'fcopy_rsc("fs_tmp/never.txt")', 'fcopy_rsc(file("fs_tmp/never.txt"))', 'fcopy_rsc()',
              'fcopy_rsc("test.dmi", 1)', "length(fcopy_rsc('test.dmi')) == length('test.dmi')",
              'icon_states(fcopy_rsc("test.dmi"))', 'fcopy_rsc(File = \'test.dmi\') == \'test.dmi\'',
              "fcopy_rsc(fcopy_rsc('test.dmi')) == 'test.dmi'", 'load_resource(\'test.dmi\') == \'test.dmi\'']:
        s.case("fcopy_rsc", e)
    for lines, expr in [
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")'], 'list(isfile(R), length(R), file2text(R), md5(R) == md5(file("@/t.txt")), istext(R))'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc(file("@/t.txt"))'], 'list(isfile(R), length(R), file2text(R))'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")', 'text2file("def", "@/t.txt")'], 'list(file2text(R), length(R), file2text("@/t.txt"))'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")', 'fdel("@/t.txt")'], 'list(file2text(R), length(R), fexists(R))'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")', 'var/R2 = fcopy_rsc("@/t.txt")'], 'list(R == R2, fcopy_rsc(R) == R)'),
        (['text2file("abc", "@/t.txt")', 'text2file("abc", "@/u.txt")'], 'fcopy_rsc("@/t.txt") == fcopy_rsc("@/u.txt")'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")'], 'R == file("@/t.txt")'),
        (['text2file("abc", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")'], 'findtext("[R]", "t.txt") ? 1 : 0'),
        (['text2file("", "@/t.txt")', 'var/R = fcopy_rsc("@/t.txt")'], 'list(isnull(R), isfile(R), length(R))'),
        (['text2file("abc", "@/d/t.txt")', 'var/R = fcopy_rsc("@/d/")'], 'list(isnull(R), isfile(R))'),
        (['fcopy(\'test.dmi\', "@/t.dmi")', 'var/R = fcopy_rsc("@/t.dmi")'], 'list(isicon(R), isfile(R), icon_states(R), md5(R) == md5(\'test.dmi\'))'),
        (['fcopy(\'test.dmi\', "@/t.dmi")', 'var/R = fcopy_rsc("@/t.dmi")'], "R == 'test.dmi'"),
    ]:
        fc("fcopy_rsc", lines, expr)

    # =============================================================================== flist
    # A fixed tree: a.txt ab.txt b.txt A2.TXT adir/x.txt bdir/ (via an emptied folder) .hid c.dat
    TREE = ['text2file("1", "@/a.txt")', 'text2file("22", "@/ab.txt")', 'text2file("3", "@/b.txt")',
            'text2file("4", "@/A2.TXT")', 'text2file("5", "@/adir/x.txt")', 'text2file("6", "@/bdir/y.txt")',
            'fdel("@/bdir/y.txt")', 'text2file("7", "@/c.dat")', 'text2file("8", "@/.hid")']
    for arg in ['"@/"', '"@/a"', '"@/A"', '"@/ab"', '"@/a.txt"', '"@/adir"', '"@/adir/"', '"@/bdir/"', '"@/bdir"',
                '"@/z"', '"@/nodir/"', '"@/nodir/a"', '"@"', '"@B\\\\"', '"@B\\\\a"', '"@U/"', '"@/*.txt"',
                '"@/a*"', '"@/?.txt"', '"@/./"', '"./@/"', '"@//"', '"@/adir/../"', '"@/."', '"@/a.txt/"',
                'file("@/")', 'file("@/a")', '"@/ADIR/"', '"@/"+"a"', '"@/c"', '"@/."+"h"']:
        fc("flist", TREE + [f"var/L = flist({arg})"], "list(islist(L), files_sort(L))")
    fc("flist", TREE + ['var/L = flist("@/")'], "L")                 # raw order
    fc("flist", TREE + ['var/list/L = flist("@/")', 'L += "extra"', 'var/list/L2 = flist("@/")'], "list(L.len, L2.len)")
    fc("flist", TREE + ['var/L = flist("@/")', 'text2file("9", "@/new.txt")', 'var/L2 = flist("@/")'], "list(files_sort(L), files_sort(L2))")
    fc("flist", TREE + ['var/L = flist("@/")', 'fdel("@/a.txt")', 'var/L2 = flist("@/")'], "files_sort(L2)")
    fc("flist", TREE + ['var/L = flist("@/a")', 'fdel("@/ab.txt")', 'var/L2 = flist("@/a")'], "files_sort(L2)")
    fc("flist", ['text2file("x", "@/é日本.txt")', 'text2file("x", "@/a b.txt")', 'var/L = flist("@/")'], "files_sort(L)")
    fc("flist", ['text2file("x", "@/t.txt")', 'var/list/L = flist("fs_tmp/")'], "list(L.len, length(files_sort(L)))")
    fc("flist", ['var/list/L = flist("fs_tmp/")'], "list(islist(L), L ? L.len : null)")
    fc("flist", ['text2file("x", "@/t.txt")', 'var/L = flist()'], 'list(islist(L), (L && ("fs_tmp/" in L)) ? 1 : 0)')
    for a in ["null", "123", "list()", "new /datum", "/datum", '""', "PINF", "'test.dmi'"]:
        fc("flist", ['text2file("x", "@/t.txt")', f"var/L = flist({a})"], 'list(islist(L), (islist(L) && ("fs_tmp/" in L)) ? 1 : 0, (islist(L) && ("test.dmi" in L)) ? 1 : 0)')
    for e in ['flist("test.dmi")', 'flist("test.")', 'flist("small")', 'flist("TEST.DMI")', 'flist("fs_tmp/never/")',
              'flist("fs_tmp/never")', 'flist("test.dmi", 1)', 'flist(Path = "small.dmi")', 'flist("./small.dmi")']:
        s.case("flist", e)

    # =============================================================================== ftime (kind only, never the value)
    for a in ANY + ["'test.dmi'", '"test.dmi"', 'file("test.dmi")']:
        s.case("ftime", f"isnum(ftime({a}))")
    for lines, expr in [
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime("@/t.txt")), isnum(ftime("@/t.txt", 1)), ftime("@/t.txt") > 0, ftime("@/t.txt", 1) > 0)'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime(file("@/t.txt"))), isnum(ftime(file("@/t.txt"), 1)))'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime(fcopy_rsc("@/t.txt"))))'),
        (['text2file("x", "@/t.txt")'], 'list(ftime("@/t.txt") != 0, ftime("@/t.txt", 1) != 0)'),
        (['text2file("x", "@/t.txt")', 'var/F = file("@/t.txt")', 'F << "y"'], 'list(isnum(ftime(F)), ftime(F) > 0, isnum(ftime("@/t.txt", 1)))'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime("@/t.txt", "yes")), isnum(ftime("@/t.txt", null)), isnum(ftime("@/t.txt", -1)))'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime("@B\\\\t.txt")), isnum(ftime("@U/T.TXT")))'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime("@/t.txt")), ftime("@/t.txt") == ftime("@B\\\\t.txt"))'),
        (['text2file("x", "@/d/t.txt")'], 'list(isnum(ftime("@/d/")), isnum(ftime("@/d")), ftime("@/d/") > 0)'),
        ([], 'list(isnum(ftime("@/missing.txt")), ftime("@/missing.txt") == 0, ftime("@/missing.txt") > 0, isnull(ftime("@/missing.txt")))'),
        ([], 'list(isnum(ftime("@/missing.txt", 1)), ftime("@/missing.txt", 1) == 0)'),
        (['text2file("x", "@/t.txt")'], 'list(isnum(ftime(File = "@/t.txt", IsCreationTime = 1)))'),
        (['text2file("x", "@/t.txt")'], 'istext(time2text(ftime("@/t.txt"), "YYYY"))'),
        ([], 'isnum(ftime())'),
        (['text2file("x", "@/t.txt")'], 'isnum(ftime("@/t.txt", 0, 1))'),
    ]:
        fc("ftime", lines, expr)

    # =============================================================================== length / md5 / sha1 of files
    for e in ["length('test.dmi')", "length('small.dmi')", "length('test.dmi') > 100", 'length(file("test.dmi")) == length(\'test.dmi\')',
              'length(file("fs_tmp/never.txt"))', 'length("test.dmi")', 'length(file("test.dmi"))', "md5('test.dmi')",
              "md5('small.dmi')", 'md5(file("test.dmi")) == md5(\'test.dmi\')', 'md5(file("fs_tmp/never.txt"))',
              'md5("fs_tmp/never.txt")', "sha1('test.dmi')", 'sha1(file("fs_tmp/never.txt"))',
              'sha1(file("test.dmi")) == sha1(\'test.dmi\')', 'length_char(file("test.dmi")) == length(file("test.dmi"))',
              "length_char('test.dmi')", "md5(icon('test.dmi')) ? 1 : 0", "md5(file2text('test.dmi')) == md5('test.dmi')"]:
        s.case("length_file", e)
    for t in ["", "a", "abc", "é", "🙂x🙂", "line1\nline2", "a\tb"]:
        fc("length_file", f'text2file({Q(t)}, "@/t.txt")',
           f'list(length(file("@/t.txt")), length_char(file("@/t.txt")), md5(file("@/t.txt")) == md5({Q(t)}), sha1(file("@/t.txt")) == sha1({Q(t)}), md5("@/t.txt") == md5(file("@/t.txt")))')
    for lines, expr in [
        (['text2file("abc", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/a = length(F)', 'text2file("def", "@/t.txt")'], 'list(a, length(F), length(file("@/t.txt")))'),
        (['text2file("abc", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/a = length(F)', 'fdel("@/t.txt")'], 'list(a, length(F), md5(F))'),
        (['text2file("abc", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/a = md5(F)', 'fdel("@/t.txt")', 'text2file("xyz", "@/t.txt")'], 'list(a == md5(F), md5(F) == md5(file2text("@/t.txt")))'),
        (['text2file("abc", "@/d/t.txt")'], 'list(length(file("@/d/")), length(file("@/d")), md5(file("@/d/")))'),
        (['var/F = file("@/t.txt")'], 'list(length(F), md5(F), sha1(F))'),
        (['fcopy(\'test.dmi\', "@/t.dmi")'], 'list(length(file("@/t.dmi")) == length(\'test.dmi\'), length_char(file("@/t.dmi")) == length(\'test.dmi\'))'),
        (['text2file("abc", "@/t.txt")'], 'list(length(fcopy_rsc("@/t.txt")), md5(fcopy_rsc("@/t.txt")) == md5("abc"))'),
        (['text2file("abc", "@/t.txt")'], 'list(length(file("@B\\\\t.txt")), length(file("@U/T.TXT")))'),
    ]:
        fc("length_file", lines, expr)

    # =============================================================================== F << X / F >> V
    OUT_VALS = ['"x"', '""', '"a\\nb"', '"é🙂"', "5", "1.5", "null", "list()", "list(1, 2)", "new /datum", "/datum",
                "'test.dmi'", '"\\red x"', '"\\bold x"', '"<b>x</b>"', '"a[ascii2text(13)]\\nb"', "PINF"]
    for v in OUT_VALS:
        fc("file<<", ['var/F = file("@/t.txt")', f"F << {v}"], INFO)
    for lines, expr in [
        (['var/F = file("@/t.txt")', 'F << "a"', 'F << "b"'], INFO),
        (['var/F = file("@/t.txt")', 'F << "a"', 'var/a = length(F)', 'F << "b"'], f'list(a, length(F), {INFO})'),
        (['var/F = file("@/sub/dir/t.txt")', 'F << "a"'], 'files_info("@/sub/dir/t.txt")'),
        (['text2file("x", "@/t.txt")', 'var/F = file("@/t.txt")', 'F << "a"'], INFO),
        (['var/F = file("@/t.txt")', 'F << "a"', 'text2file("b", "@/t.txt")'], INFO),
        (['var/F = file("@B\\\\t.txt")', 'F << "a"'], INFO),
        (['file("@/t.txt") << "a"'], INFO),
        (['"@/t.txt" << "a"'], INFO),
        (['var/R = fcopy_rsc(\'test.dmi\')', 'R << "a"'], 'length(\'test.dmi\') == length(R)'),
        (['var/F = file("@/t.txt")', 'F << output("x", "foo")'], INFO),
    ]:
        fc("file<<", lines, expr)
    for content in ["42", "hello world", "line1\nline2", "", "1.5e2", "a,b"]:
        fc("file>>", [f'text2file({Q(content)}, "@/t.txt")', 'var/F = file("@/t.txt")', 'var/V = "unset"', "F >> V"], "V")
    fc("file>>", ['text2file("l1\\nl2\\nl3", "@/t.txt")', 'var/F = file("@/t.txt")', 'var/V1', 'var/V2', "F >> V1", "F >> V2"], "list(V1, V2)")
    fc("file>>", ['var/F = file("@/missing.txt")', 'var/V = "unset"', "F >> V"], "V")
    fc("file>>", ['text2file("x", "@/t.txt")', 'var/V = "unset"', '"@/t.txt" >> V'], "V")

    # =============================================================================== gaps: caches, odd names, dirs
    # Control for files_sort (sorttext order), so a sorttext divergence isn't read as a flist one
    s.case("files_misc", 'files_sort(list("b.txt", "A2.TXT", "a.txt", "adir/", ".hid", "ab.txt", "c.dat", "bdir/"))')
    # flist listing after a write through F << (OD's listing cache)
    for first in ['"@/"', '"@/n"']:
        fc("flist", TREE + [f"var/L = flist({first})", 'var/F = file("@/new.txt")', 'F << "x"', f"var/L2 = flist({first})"],
           "list(files_sort(L), files_sort(L2))")
    # flist prefixes inside a sub-directory
    for arg in ['"@/adir/x"', '"@/adir/z"', '"@/adir/x.txt"', '"@/adir/X"']:
        fc("flist", TREE + [f"var/L = flist({arg})"], "list(islist(L), files_sort(L))")
    # file2text cache after appending through a different spelling of the same path
    for w in ['text2file("two", "./@/t.txt")', 'text2file("two", "@U/T.TXT")', 'text2file("two", "@/sub/../t.txt")',
              'text2file("two", "@//t.txt")', 'file("./@/t.txt") << "two"', 'file("@B\\\\t.txt") << "two"']:
        fc("file2text", ['text2file("one", "@/t.txt")', 'var/a = file2text("@/t.txt")', w],
           'list(a, file2text("@/t.txt"), length(file("@/t.txt")))')
    # Non-image data under an icon extension; and a missing one
    for ext in ["dmi", "png"]:
        fc("fcopy_rsc", [f'text2file("abc", "@/bad.{ext}")'],
           f'list(isfile(fcopy_rsc("@/bad.{ext}")), isicon("@/bad.{ext}"), isicon(file("@/bad.{ext}")), '
           f'file2text("@/bad.{ext}"), length(file("@/bad.{ext}")), fcopy("@/bad.{ext}", "@/c.png"))')
    fc("fcopy_rsc", [], 'list(isfile(fcopy_rsc("@/missing.dmi")), isicon("@/missing.dmi"), isicon(file("@/missing.dmi")), '
                        'file2text("@/missing.dmi"), length(file("@/missing.dmi")), fcopy("@/missing.dmi", "@/c.png"))')
    # fcopy onto an existing directory named without a trailing slash
    fc("fcopy", ['text2file("x", "@/d/k.txt")', 'text2file("1", "@/t.txt")', 'var/r = fcopy("@/t.txt", "@/d")'],
       'list(r, files_sort(flist("@/")), files_sort(flist("@/d/")))')
    # Characters Windows doesn't allow in file names (':' makes an NTFS alternate data stream on "a")
    for name in ['"@/a?b.txt"', '"@/a*b.txt"', '"@/a<b>.txt"', '"@/a|b.txt"', '"@/a\\"b.txt"', '"@/a:b.txt"']:
        fc("text2file", [f'var/r = text2file("x", {name})'], f'list(r, fexists({name}), files_sort(flist("@/")))')
        fc("fcopy", ['text2file("1", "@/t.txt")', f'var/r = fcopy("@/t.txt", {name})'], f'list(r, fexists({name}), files_sort(flist("@/")))')
    # Paths over 260 characters: a long name, and deep nesting
    fc("text2file", ['var/n = ""', 'for(var/i in 1 to 30)', '\tn += "abcdefghij"', 'var/r = text2file("x", "@/[n].txt")'],
       'list(r, fexists("@/[n].txt"), length(file("@/[n].txt")), length(flist("@/")))')
    fc("text2file", ['var/p = "@/"', 'for(var/i in 1 to 30)', '\tp += "dddddddddd/"', 'var/r = text2file("x", "[p]t.txt")'],
       'list(r, fexists("[p]t.txt"), length(file("[p]t.txt")), files_sort(flist("@/")))')
    # fdel / fcopy / file2text / length given file() objects that name a directory
    fc("fdel", ['text2file("x", "@/d/t.txt")', 'var/r = fdel(file("@/d/"))'], 'list(r, fexists("@/d/t.txt"), files_sort(flist("@/")))')
    fc("fdel", ['text2file("x", "@/d/t.txt")', 'var/r = fdel(file("@/d"))'], 'list(r, fexists("@/d/t.txt"), files_sort(flist("@/")))')
    fc("fcopy", ['text2file("1", "@/s/a.txt")', 'var/r = fcopy(file("@/s/"), "@/d/")'], 'list(r, files_sort(flist("@/d/")))')
    fc("fcopy", ['text2file("1", "@/s/a.txt")', 'var/r = fcopy(file("@/s/"), file("@/d/"))'], 'list(r, files_sort(flist("@/")))')
    fc("file2text", ['text2file("x", "@/d/t.txt")'],
       'list(file2text(file("@/d/")), file2text(file("@/d")), isfile(file("@/d/")), fexists(file("@/d/")))')
    fc("length_file", ['text2file("x", "@/d/t.txt")'], 'list(length(file("@/d/")), md5(file("@/d")), fexists(file("@/d")))')

    # =============================================================================== mixed workflows
    for lines, expr in [
        # write, copy, list, delete a tree, in one go
        (['text2file("1", "@/w/a.txt")', 'fcopy("@/w/a.txt", "@/w/b.txt")', 'var/L1 = files_sort(flist("@/w/"))', 'fdel("@/w/a.txt")', 'var/L2 = files_sort(flist("@/w/"))', 'var/r = fdel("@/w/")'],
         'list(L1, L2, r, fexists("@/w/b.txt"), files_sort(flist("@/")))'),
        (['for(var/i in 1 to 5)', '\ttext2file("[i]", "@/n[i].txt")'], 'list(files_sort(flist("@/")), file2text("@/n3.txt"))'),
        (['for(var/i in 1 to 3)', '\ttext2file("[i]", "@/acc.txt")'], 'files_info("@/acc.txt")'),
        (['text2file("x", "@/t.txt")'], 'list(fexists("fs_tmp/"), fdel("fs_tmp/"), fexists("@/t.txt"), fexists("fs_tmp/"), files_sort(flist("fs_tmp/")))'),
    ]:
        fc("files_misc", lines, expr)
    # Last: make sure nothing of ours is left behind
    s.body("files_misc", ['fdel("fs_tmp/")'], 'list(fexists("fs_tmp/"), flist("fs_tmp/"))')


DM = r'''/proc/files_reset()
	fdel("fs_tmp/")

/proc/files_done(v)
	fdel("fs_tmp/")
	return v

// Exists / byte length / text of a path, read fresh each time
/proc/files_info(p)
	return list("exists" = fexists(p), "len" = length(file(p)), "text" = file2text(p))

// Code points of a text, so CR/BOM/etc. show up as numbers
/proc/files_codes(t)
	if(!istext(t))
		return t
	var/list/L = list()
	for(var/i in 1 to length_char(t))
		L += text2ascii_char(t, i)
	return L

// A sorted copy, so directory listing order doesn't matter
/proc/files_sort(list/L)
	if(!islist(L))
		return L
	var/list/R = L.Copy()
	for(var/i in 1 to R.len)
		for(var/j in 1 to R.len - i)
			if(sorttext("[R[j]]", "[R[j + 1]]") < 0)
				R.Swap(j, j + 1)
	return R
'''
