import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.config import COLOR_GREEN, COLOR_ORANGE, COLOR_RED

_FONT_CACHE = {}
RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS


def hex_to_rgba(hex_color, alpha=255):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def load_pil_font(bold=False, mono=True, size=18):
    key = (bold, mono, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    if mono:
        candidates = ["consolab.ttf", "lucon.ttf", "courbd.ttf"] if bold else ["consola.ttf", "cour.ttf"]
    else:
        candidates = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    windir = os.environ.get("WINDIR", "C:\\Windows")
    for name in candidates:
        for path in (os.path.join(windir, "Fonts", name), name):
            try:
                f = ImageFont.truetype(path, size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def smooth_catmull_rom(pts, samples_per_seg=4, y_min=0.0, y_max=9999.0):
    n = len(pts)
    if n < 3:
        return pts
    out = []
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for s in range(samples_per_seg):
            t = s / float(samples_per_seg)
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2.0 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2.0 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
            )
            y = max(y_min, min(y_max, y))
            out.append((x, y))
    out.append(pts[-1])
    return out


def build_pulse_icon(accent_rgb, size=256):
    base = 256
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r, g, b = accent_rgb
    solid_accent = (r, g, b, 255)

    draw.rounded_rectangle((14, 14, 242, 242), radius=54, fill=(10, 14, 24, 255), outline=(r, g, b, 90), width=10)
    draw.rounded_rectangle((20, 20, 236, 236), radius=48, fill=(14, 20, 34, 255), outline=solid_accent, width=5)

    pulse_pts = [
        (42, 134), (78, 134), (96, 102), (116, 174),
        (140, 74), (162, 152), (178, 134), (212, 134),
    ]

    glow_layer = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.line(pulse_pts, fill=(r, g, b, 190), width=18, joint="curve")
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=9))
    img = Image.alpha_composite(img, glow_layer)

    draw = ImageDraw.Draw(img)
    draw.line(pulse_pts, fill=solid_accent, width=10, joint="curve")
    draw.line(pulse_pts, fill=(245, 252, 255, 230), width=4, joint="curve")
    draw.ellipse((198, 120, 224, 146), fill=solid_accent)
    draw.ellipse((204, 126, 218, 140), fill=(255, 255, 255, 255))

    if size != base:
        img = img.resize((size, size), RESAMPLE_LANCZOS)
    return img


def render_aa_status_led(color_hex, glow_strength=0.6, size=22):
    scale = 4
    s = size * scale
    cx = cy = s // 2
    r, g, b, _ = hex_to_rgba(color_hex)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    if glow_strength > 0:
        glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gr = int(s * (0.28 + 0.10 * glow_strength))
        ga = int(170 * glow_strength)
        gd.ellipse((cx - gr, cy - gr, cx + gr, cy + gr), fill=(r, g, b, ga))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.14)))
        img = Image.alpha_composite(img, glow)

    draw = ImageDraw.Draw(img)
    ring_r = int(s * 0.25)
    draw.ellipse((cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r), fill=(r, g, b, 255))

    hl_r = int(s * 0.09)
    hx = cx - int(s * 0.06)
    hy = cy - int(s * 0.06)
    draw.ellipse((hx - hl_r, hy - hl_r, hx + hl_r, hy + hl_r), fill=(255, 255, 255, 195))

    return img.resize((size, size), RESAMPLE_LANCZOS)


def render_aa_icon(kind, color_hex, size=18):
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    col = hex_to_rgba(color_hex, 255)
    soft = hex_to_rgba(color_hex, 75)
    w = max(4, s // 11)
    c = s // 2

    if kind == "radar":
        draw.arc((s * 0.12, s * 0.12, s * 0.88, s * 0.88), 30, 330, fill=col, width=w)
        draw.arc((s * 0.28, s * 0.28, s * 0.72, s * 0.72), 45, 315, fill=col, width=max(3, w - 1))
        draw.line((c, c, s * 0.80, s * 0.24), fill=col, width=w)
        draw.ellipse((c - w, c - w, c + w, c + w), fill=col)
    elif kind == "activity":
        pts = [(s * 0.10, c), (s * 0.28, c), (s * 0.40, s * 0.20), (s * 0.58, s * 0.80), (s * 0.72, c), (s * 0.90, c)]
        draw.line(pts, fill=col, width=w, joint="curve")
    elif kind == "dns":
        draw.rounded_rectangle((s * 0.14, s * 0.16, s * 0.86, s * 0.46), radius=s * 0.10, outline=col, width=w)
        draw.rounded_rectangle((s * 0.14, s * 0.54, s * 0.86, s * 0.84), radius=s * 0.10, outline=col, width=w)
        draw.ellipse((s * 0.24, s * 0.27, s * 0.34, s * 0.37), fill=col)
        draw.ellipse((s * 0.24, s * 0.65, s * 0.34, s * 0.75), fill=col)
    elif kind == "lan":
        draw.rounded_rectangle((s * 0.34, s * 0.12, s * 0.66, s * 0.36), radius=s * 0.06, outline=col, width=w)
        draw.line((c, s * 0.36, c, s * 0.52), fill=col, width=w)
        draw.line((s * 0.26, s * 0.52, s * 0.74, s * 0.52), fill=col, width=w)
        draw.line((s * 0.26, s * 0.52, s * 0.26, s * 0.64), fill=col, width=w)
        draw.line((s * 0.74, s * 0.52, s * 0.74, s * 0.64), fill=col, width=w)
        draw.rounded_rectangle((s * 0.12, s * 0.64, s * 0.40, s * 0.88), radius=s * 0.06, outline=col, width=w)
        draw.rounded_rectangle((s * 0.60, s * 0.64, s * 0.88, s * 0.88), radius=s * 0.06, outline=col, width=w)
    elif kind == "gear":
        r_out = s * 0.36
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1 = c + math.cos(rad) * (r_out * 0.65)
            y1 = c + math.sin(rad) * (r_out * 0.65)
            x2 = c + math.cos(rad) * (r_out * 1.08)
            y2 = c + math.sin(rad) * (r_out * 1.08)
            draw.line((x1, y1, x2, y2), fill=col, width=w + 2)
        draw.ellipse((c - r_out * 0.78, c - r_out * 0.78, c + r_out * 0.78, c + r_out * 0.78), outline=col, width=w + 1)
        draw.ellipse((c - r_out * 0.32, c - r_out * 0.32, c + r_out * 0.32, c + r_out * 0.32), fill=col)
    elif kind == "mini":
        draw.rounded_rectangle((s * 0.12, s * 0.16, s * 0.88, s * 0.84), radius=s * 0.12, outline=col, width=w)
        draw.rounded_rectangle((s * 0.46, s * 0.46, s * 0.80, s * 0.76), radius=s * 0.08, fill=col)
    elif kind == "dl":
        draw.ellipse((s * 0.08, s * 0.08, s * 0.92, s * 0.92), fill=soft, outline=col, width=max(3, w - 2))
        draw.line((c, s * 0.28, c, s * 0.70), fill=col, width=w)
        draw.line((s * 0.32, s * 0.54, c, s * 0.72, s * 0.68, s * 0.54), fill=col, width=w, joint="curve")
    elif kind == "ul":
        draw.ellipse((s * 0.08, s * 0.08, s * 0.92, s * 0.92), fill=soft, outline=col, width=max(3, w - 2))
        draw.line((c, s * 0.72, c, s * 0.30), fill=col, width=w)
        draw.line((s * 0.32, s * 0.46, c, s * 0.28, s * 0.68, s * 0.46), fill=col, width=w, joint="curve")
    elif kind == "globe":
        draw.ellipse((s * 0.12, s * 0.12, s * 0.88, s * 0.88), outline=col, width=w)
        draw.ellipse((s * 0.32, s * 0.12, s * 0.68, s * 0.88), outline=col, width=max(3, w - 2))
        draw.line((s * 0.14, c, s * 0.86, c), fill=col, width=max(3, w - 2))
    elif kind == "refresh":
        draw.arc((s * 0.16, s * 0.16, s * 0.84, s * 0.84), 35, 325, fill=col, width=w)
        draw.polygon([(s * 0.84, s * 0.22), (s * 0.84, s * 0.46), (s * 0.62, s * 0.40)], fill=col)
    elif kind == "bolt":
        pts = [(s * 0.58, s * 0.10), (s * 0.24, s * 0.54), (s * 0.48, s * 0.54), (s * 0.40, s * 0.90), (s * 0.76, s * 0.44), (s * 0.52, s * 0.44)]
        draw.polygon(pts, fill=col)
    elif kind == "bookmark":
        pts = [(s * 0.24, s * 0.14), (s * 0.76, s * 0.14), (s * 0.76, s * 0.86), (c, s * 0.65), (s * 0.24, s * 0.86)]
        draw.polygon(pts, fill=soft)
        draw.line(pts + [pts[0]], fill=col, width=w, joint="curve")
    elif kind == "trash":
        draw.line((s * 0.18, s * 0.26, s * 0.82, s * 0.26), fill=col, width=w)
        draw.rounded_rectangle((s * 0.36, s * 0.13, s * 0.64, s * 0.26), radius=s * 0.04, outline=col, width=max(3, w - 1))
        draw.rounded_rectangle((s * 0.26, s * 0.26, s * 0.74, s * 0.86), radius=s * 0.08, outline=col, width=w)
        draw.line((s * 0.42, s * 0.42, s * 0.42, s * 0.72), fill=col, width=max(3, w - 2))
        draw.line((s * 0.58, s * 0.42, s * 0.58, s * 0.72), fill=col, width=max(3, w - 2))
    elif kind == "plus":
        draw.line((s * 0.20, c, s * 0.80, c), fill=col, width=w + 2)
        draw.line((c, s * 0.20, c, s * 0.80), fill=col, width=w + 2)
    elif kind == "close":
        draw.line((s * 0.24, s * 0.24, s * 0.76, s * 0.76), fill=col, width=w + 1)
        draw.line((s * 0.76, s * 0.24, s * 0.24, s * 0.76), fill=col, width=w + 1)
    elif kind == "lock":
        draw.arc((s * 0.30, s * 0.14, s * 0.70, s * 0.54), 180, 360, fill=col, width=w)
        draw.line((s * 0.30, s * 0.34, s * 0.30, s * 0.48), fill=col, width=w)
        draw.line((s * 0.70, s * 0.34, s * 0.70, s * 0.48), fill=col, width=w)
        draw.rounded_rectangle((s * 0.20, s * 0.44, s * 0.80, s * 0.86), radius=s * 0.10, fill=soft, outline=col, width=w)
        draw.ellipse((c - w * 0.7, s * 0.59, c + w * 0.7, s * 0.71), fill=col)
    elif kind == "unlock":
        draw.arc((s * 0.30, s * 0.10, s * 0.70, s * 0.50), 180, 330, fill=col, width=w)
        draw.line((s * 0.30, s * 0.30, s * 0.30, s * 0.48), fill=col, width=w)
        draw.rounded_rectangle((s * 0.20, s * 0.44, s * 0.80, s * 0.86), radius=s * 0.10, fill=soft, outline=col, width=w)
        draw.ellipse((c - w * 0.7, s * 0.59, c + w * 0.7, s * 0.71), fill=col)

    return img.resize((size, size), RESAMPLE_LANCZOS)


def draw_aa_series_on_rgba(base_img, pts, line_hex, pad_top, y_bottom, scale, glow_alpha=125, fill_alpha_top=92):
    W, H = base_img.size
    r, g, b, _ = hex_to_rgba(line_hex)
    smooth_pts = smooth_catmull_rom(pts, samples_per_seg=4, y_min=pad_top, y_max=y_bottom)

    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    poly = [(pts[0][0], y_bottom)] + smooth_pts + [(pts[-1][0], y_bottom)]
    md.polygon(poly, fill=255)

    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    span = max(1, int(y_bottom - pad_top))
    for y in range(int(pad_top), int(y_bottom) + 1):
        frac = 1.0 - ((y - pad_top) / float(span))
        a = int(fill_alpha_top * (frac ** 1.25))
        if a > 0:
            gd.line((0, y, W, y), fill=(r, g, b, a))

    fill_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fill_layer.paste(grad, (0, 0), mask)
    base_img = Image.alpha_composite(base_img, fill_layer)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gld = ImageDraw.Draw(glow)
    gld.line(smooth_pts, fill=(r, g, b, glow_alpha), width=int(5 * scale), joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(3 * scale)))
    base_img = Image.alpha_composite(base_img, glow)

    draw = ImageDraw.Draw(base_img)
    draw.line(smooth_pts, fill=(r, g, b, 255), width=int(2.2 * scale), joint="curve")
    return base_img


def render_ping_graph_base(w, h, T, graph_data_1, graph_data_2, num_targets):
    scale = 2
    W, H = w * scale, h * scale
    pad_top, pad_bot, pad_right = 18 * scale, 12 * scale, 48 * scale
    plot_h = H - pad_top - pad_bot
    plot_w = W - pad_right
    y_bottom = H - pad_bot
    step_x = plot_w / 59.0

    img = Image.new("RGBA", (W, H), hex_to_rgba(T["card"], 255))
    draw = ImageDraw.Draw(img)

    valid_vals = [v for v in graph_data_1 if v is not None and v > 0]
    if num_targets == 2:
        valid_vals += [v for v in graph_data_2 if v is not None and v > 0]
    peak = max(valid_vals) if valid_vals else 100
    scale_options = [100.0, 150.0, 200.0, 300.0, 500.0, 800.0]
    max_val = next((s for s in scale_options if s >= peak * 1.15), float(int(peak * 1.2)))

    grid_col = hex_to_rgba(T["grid"], 255)
    muted_col = hex_to_rgba(T["muted"], 255)
    f_axis = load_pil_font(bold=False, mono=True, size=9 * scale)
    f_live = load_pil_font(bold=True, mono=True, size=9 * scale)

    for i in range(5):
        y = int(pad_top + i * (plot_h / 4.0))
        ms_label = int(max_val - i * (max_val / 4.0))
        for dx in range(0, int(plot_w), 10 * scale):
            draw.line((dx, y, min(dx + 5 * scale, plot_w), y), fill=grid_col, width=scale)
        draw.text((plot_w + 8 * scale, y - 5 * scale), f"{ms_label}", fill=muted_col, font=f_axis)

    for i in range(1, 6):
        x = int(i * (plot_w / 6.0))
        draw.line((x, pad_top, x, y_bottom), fill=hex_to_rgba(T["grid"], 140), width=scale)

    def build_pts_and_timeouts(data):
        pts = []
        for i, v in enumerate(data):
            val = 0 if (v is None or v == -1) else min(v, max_val)
            x = i * step_x
            y = y_bottom - (val / max_val) * plot_h
            pts.append((x, y))
            if v == -1:
                for dy in range(int(pad_top), int(y_bottom), 8 * scale):
                    draw.line((x, dy, x, min(dy + 4 * scale, y_bottom)), fill=(185, 28, 28, 170), width=scale)
        return pts

    pts1 = build_pts_and_timeouts(graph_data_1)
    pts2 = build_pts_and_timeouts(graph_data_2) if num_targets == 2 else None

    img = draw_aa_series_on_rgba(img, pts1, T["accent1"], pad_top, y_bottom, scale, glow_alpha=125, fill_alpha_top=92)
    if pts2 is not None:
        img = draw_aa_series_on_rgba(img, pts2, T["accent2"], pad_top, y_bottom, scale, glow_alpha=115, fill_alpha_top=78)

    def draw_end_marker(pts, data, line_hex):
        lx, ly = pts[-1]
        last_v = data[-1]
        dot_hex = COLOR_RED if last_v == -1 else line_hex
        dot_col = hex_to_rgba(dot_hex, 255)
        ring_col = hex_to_rgba(dot_hex, 120)
        md = ImageDraw.Draw(img)
        r_out = 7 * scale
        r_in = 3.6 * scale
        md.ellipse((lx - r_out, ly - r_out, lx + r_out, ly + r_out), fill=ring_col)
        md.ellipse((lx - r_in, ly - r_in, lx + r_in, ly + r_in), fill=(255, 255, 255, 255), outline=dot_col, width=2 * scale)
        if last_v is not None:
            lbl = "ERR" if last_v == -1 else f"{last_v}"
            md.text((lx + 10 * scale, ly - 6 * scale), lbl, fill=dot_col, font=f_live)

    draw_end_marker(pts1, graph_data_1, T["accent1"])
    if pts2 is not None:
        draw_end_marker(pts2, graph_data_2, T["accent2"])

    meta = (pts1, pts2, step_x, pad_top, y_bottom, plot_w, scale)
    return img, meta


def render_ping_graph_frame(base_img, meta, w, h, T, graph_data_1, graph_data_2, graph_times, num_targets, hover_idx):
    final_img = base_img.copy()
    if hover_idx is not None and meta is not None:
        pts1, pts2, step_x, pad_top, y_bottom, plot_w, scale = meta
        W, H = final_img.size
        v1 = graph_data_1[hover_idx]
        t_lbl = graph_times[hover_idx]
        if v1 is not None or t_lbl:
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            hx = hover_idx * step_x
            muted_col = hex_to_rgba(T["muted"], 180)
            for dy in range(int(pad_top), int(y_bottom), 8 * scale):
                od.line((hx, dy, hx, min(dy + 4 * scale, y_bottom)), fill=muted_col, width=scale)

            _, hy1 = pts1[hover_idx]
            c1_hex = COLOR_RED if v1 == -1 else T["accent1"]
            r_dot = 4.8 * scale
            od.ellipse((hx - r_dot, hy1 - r_dot, hx + r_dot, hy1 + r_dot), fill=(255, 255, 255, 255), outline=hex_to_rgba(c1_hex), width=2 * scale)

            lines = [(f"Time: {t_lbl or '--:--:--'}", T["muted"])]
            t1_txt = "TIMEOUT" if v1 == -1 else (f"{v1} ms" if v1 is not None else "--")
            lines.append((f"T1: {t1_txt}", c1_hex))

            if num_targets == 2 and pts2 is not None:
                v2 = graph_data_2[hover_idx]
                _, hy2 = pts2[hover_idx]
                c2_hex = COLOR_RED if v2 == -1 else T["accent2"]
                od.ellipse((hx - r_dot, hy2 - r_dot, hx + r_dot, hy2 + r_dot), fill=(255, 255, 255, 255), outline=hex_to_rgba(c2_hex), width=2 * scale)
                t2_txt = "TIMEOUT" if v2 == -1 else (f"{v2} ms" if v2 is not None else "--")
                lines.append((f"T2: {t2_txt}", c2_hex))

            bw = 132 * scale
            bh = (17 * len(lines) + 12) * scale
            bx = hx + 12 * scale if (hx + bw + 16 * scale < plot_w) else max(6 * scale, hx - bw - 12 * scale)
            by = pad_top + 4 * scale
            od.rounded_rectangle((bx, by, bx + bw, by + bh), radius=8 * scale, fill=hex_to_rgba(T["tooltip_bg"], 235), outline=hex_to_rgba(T["accent1"], 210), width=scale)

            f_tt = load_pil_font(bold=True, mono=True, size=10 * scale)
            for row_i, (txt, clr) in enumerate(lines):
                od.text((bx + 10 * scale, by + (8 + row_i * 17) * scale), txt, fill=hex_to_rgba(clr), font=f_tt)

            final_img = Image.alpha_composite(final_img, overlay)

    return final_img.resize((w, h), RESAMPLE_LANCZOS)


def render_net_graph_base(w, h, T, dl_history, ul_history):
    scale = 2
    W, H = w * scale, h * scale
    pad_top, pad_bot, pad_right = 12 * scale, 10 * scale, 56 * scale
    plot_h = H - pad_top - pad_bot
    plot_w = W - pad_right
    y_bottom = H - pad_bot
    step_x = plot_w / 59.0

    img = Image.new("RGBA", (W, H), hex_to_rgba(T["card"], 255))
    draw = ImageDraw.Draw(img)

    peak = max(max(dl_history), max(ul_history), 100.0)
    scale_steps = [100.0, 250.0, 512.0, 1024.0, 2560.0, 5120.0, 10240.0, 25600.0, 51200.0]
    max_val = next((s for s in scale_steps if s >= peak * 1.15), peak * 1.2)

    grid_col = hex_to_rgba(T["grid"], 255)
    muted_col = hex_to_rgba(T["muted"], 255)
    f_axis = load_pil_font(bold=False, mono=True, size=9 * scale)

    for i in range(3):
        y = int(pad_top + i * (plot_h / 2.0))
        val = max_val - i * (max_val / 2.0)
        lbl = f"{int(val)}K" if val < 1024 else f"{val / 1024:.1f}M"
        for dx in range(0, int(plot_w), 10 * scale):
            draw.line((dx, y, min(dx + 5 * scale, plot_w), y), fill=grid_col, width=scale)
        draw.text((plot_w + 8 * scale, y - 5 * scale), lbl, fill=muted_col, font=f_axis)

    pts_dl = [(i * step_x, y_bottom - (min(v, max_val) / max_val) * plot_h) for i, v in enumerate(dl_history)]
    pts_ul = [(i * step_x, y_bottom - (min(v, max_val) / max_val) * plot_h) for i, v in enumerate(ul_history)]

    img = draw_aa_series_on_rgba(img, pts_dl, COLOR_GREEN, pad_top, y_bottom, scale, glow_alpha=110, fill_alpha_top=80)
    img = draw_aa_series_on_rgba(img, pts_ul, COLOR_ORANGE, pad_top, y_bottom, scale, glow_alpha=100, fill_alpha_top=65)

    meta = (pts_dl, pts_ul, step_x, pad_top, y_bottom, plot_w, scale)
    return img, meta


def render_net_graph_frame(base_img, meta, w, h, T, dl_history, ul_history, net_times, hover_idx):
    final_img = base_img.copy()
    if hover_idx is not None and meta is not None:
        pts_dl, pts_ul, step_x, pad_top, y_bottom, plot_w, scale = meta
        W, H = final_img.size
        hx = hover_idx * step_x
        dl_v = dl_history[hover_idx]
        ul_v = ul_history[hover_idx]
        t_lbl = net_times[hover_idx] or "--:--:--"

        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        muted_col = hex_to_rgba(T["muted"], 180)
        for dy in range(int(pad_top), int(y_bottom), 8 * scale):
            od.line((hx, dy, hx, min(dy + 4 * scale, y_bottom)), fill=muted_col, width=scale)

        _, y_dl = pts_dl[hover_idx]
        _, y_ul = pts_ul[hover_idx]
        r_dot = 4.5 * scale
        od.ellipse((hx - r_dot, y_dl - r_dot, hx + r_dot, y_dl + r_dot), fill=(255, 255, 255, 255), outline=hex_to_rgba(COLOR_GREEN), width=2 * scale)
        od.ellipse((hx - r_dot, y_ul - r_dot, hx + r_dot, y_ul + r_dot), fill=(255, 255, 255, 255), outline=hex_to_rgba(COLOR_ORANGE), width=2 * scale)

        dl_str = f"{dl_v:.1f} KB/s" if dl_v < 1024 else f"{dl_v / 1024:.2f} MB/s"
        ul_str = f"{ul_v:.1f} KB/s" if ul_v < 1024 else f"{ul_v / 1024:.2f} MB/s"

        bw, bh = 148 * scale, 56 * scale
        bx = hx + 12 * scale if (hx + bw + 16 * scale < plot_w) else max(6 * scale, hx - bw - 12 * scale)
        by = pad_top + 4 * scale
        od.rounded_rectangle((bx, by, bx + bw, by + bh), radius=8 * scale, fill=hex_to_rgba(T["tooltip_bg"], 235), outline=hex_to_rgba(T["accent1"], 210), width=scale)

        f_sm = load_pil_font(bold=True, mono=True, size=9 * scale)
        f_val = load_pil_font(bold=True, mono=True, size=10 * scale)
        od.text((bx + 10 * scale, by + 7 * scale), f"Time: {t_lbl}", fill=hex_to_rgba(T["muted"]), font=f_sm)
        od.text((bx + 10 * scale, by + 22 * scale), f"DL: {dl_str}", fill=hex_to_rgba(COLOR_GREEN), font=f_val)
        od.text((bx + 10 * scale, by + 37 * scale), f"UL: {ul_str}", fill=hex_to_rgba(COLOR_ORANGE), font=f_val)
        final_img = Image.alpha_composite(final_img, overlay)

    return final_img.resize((w, h), RESAMPLE_LANCZOS)