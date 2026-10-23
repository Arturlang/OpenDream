"""BYOND prompt dialogs through Win32 calls in this process (ctypes). Same results as win32.ps1 dlg/dlgdo,
without a PowerShell start for each call."""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.GetWindowLongW.restype = ctypes.c_long
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.IsWindow.argtypes = [wintypes.HWND]


def is_open(dlg):
    return bool(dlg) and bool(user32.IsWindow(dlg))

WM_SETTEXT, WM_GETTEXT, WM_GETTEXTLENGTH, WM_COMMAND, WM_CLOSE = 0x0C, 0x0D, 0x0E, 0x111, 0x10
LB = dict(count=0x18B, cur=0x188, setcur=0x186, text=0x189, len=0x18A)
CB = dict(count=0x146, cur=0x147, setcur=0x14E, text=0x148, len=0x149)


def _class(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def _text(h):
    n = user32.SendMessageW(h, WM_GETTEXTLENGTH, 0, 0)
    b = ctypes.create_unicode_buffer(n + 1)
    user32.SendMessageW(h, WM_GETTEXT, n + 1, ctypes.addressof(b))
    return b.value


def _windows(pid):
    out = []

    def cb(h, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            out.append(h)
        return True
    user32.EnumWindows(EnumProc(cb), 0)
    return out


def _children(h):
    out = []
    user32.EnumChildWindows(h, EnumProc(lambda c, _: out.append(c) or True), 0)
    return [c for c in out if user32.IsWindowVisible(c)]


def dialogs(pid):
    """Window handles of the open prompt dialogs of process pid: standard dialog class with at least one button.
    DreamSeeker keeps one more dialog-class window open (the world name, a Static only), which is not a prompt."""
    return [int(h) for h in _windows(pid) if _class(h) == "#32770" and any(_class(c) == "Button" for c in _children(h))]


def find(pid, exclude=()):
    """The first open prompt dialog of process pid that is not in exclude, or None."""
    return next((h for h in dialogs(pid) if h not in exclude), None)


def _controls(dlg):
    cs = [(c, _class(c)) for c in _children(dlg)]
    buttons = [c for c, k in cs if k == "Button"]
    edit = next((c for c, k in cs if "Edit" in k), None)
    lst = next(((c, "ComboBox" in k) for c, k in cs if "ListBox" in k or "ComboBox" in k), None)
    return cs, buttons, edit, lst


def _is_default(b):
    return (user32.GetWindowLongW(b, -16) & 0xF) == 1


def describe(dlg):
    """Dialog dlg in the shape of win32.ps1 dlg: hwnd, title, message, buttons, default_button, text, items, selected."""
    if not dlg or not user32.IsWindow(dlg):
        return None
    cs, buttons, edit, lst = _controls(dlg)
    d = {
        "hwnd": int(dlg),
        "title": _text(dlg),
        "message": "\n".join(t for t in (_text(c) for c, k in cs if k == "Static") if t),
        "buttons": [_text(b) for b in buttons],
        "default_button": next((_text(b) for b in buttons if _is_default(b)), None),
        "text": _text(edit) if edit else None,
        "items": None,
        "selected": None,
        "classes": [k for _, k in cs],
    }
    if lst:
        h, combo = lst
        m = CB if combo else LB
        items = []
        for i in range(user32.SendMessageW(h, m["count"], 0, 0)):
            n = user32.SendMessageW(h, m["len"], i, 0)
            b = ctypes.create_unicode_buffer(max(n, 0) + 1)
            user32.SendMessageW(h, m["text"], i, ctypes.addressof(b))
            items.append(b.value)
        d["items"] = items
        d["selected"] = user32.SendMessageW(h, m["cur"], 0, 0)
    return d


def act(dlg, action, arg=""):
    """Applies one action to dialog dlg, as win32.ps1 dlgdo: text, select, press, submit, close. Returns a status."""
    if not dlg or not user32.IsWindow(dlg):
        return "no dialog"
    _, buttons, edit, lst = _controls(dlg)
    # Post, not send: a handler that blocks must not block the harness
    click = lambda b: user32.PostMessageW(dlg, WM_COMMAND, user32.GetDlgCtrlID(b) & 0xFFFF, b)
    if action == "text":
        if not edit:
            return "failed: no edit control"
        buf = ctypes.create_unicode_buffer(str(arg))
        user32.SendMessageW(edit, WM_SETTEXT, 0, ctypes.addressof(buf))
        return "text set"
    if action == "select":
        if not lst:
            return "failed: no list"
        h, combo = lst
        user32.SendMessageW(h, (CB if combo else LB)["setcur"], int(arg), 0)
        user32.SendMessageW(dlg, WM_COMMAND, (1 << 16) | (user32.GetDlgCtrlID(h) & 0xFFFF), h)
        return "selected"
    if action == "press":
        b = next((b for b in buttons if _text(b).replace("&", "") == str(arg)), None)
        if not b:
            return f"failed: no button '{arg}'"
        click(b)
        return "pressed"
    if action == "submit":
        b = next((b for b in buttons if _is_default(b)), None)
        if b:
            click(b)
        else:
            user32.PostMessageW(dlg, WM_COMMAND, 1, 0)
        return "submitted"
    if action == "close":
        user32.PostMessageW(dlg, WM_CLOSE, 0, 0)
        return "closed"
    return f"failed: unknown action '{action}'"
