"""
牌理结果图片渲染模块
使用 PIL 将牌理分析结果渲染为带麻将牌图片的 PNG
"""
import os
from PIL import Image, ImageDraw, ImageFont

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(PLUGIN_DIR, "data", "tiles")

# tile index -> filename
TILE_NAMES = ['1m','2m','3m','4m','5m','6m','7m','8m','9m',
              '1p','2p','3p','4p','5p','6p','7p','8p','9p',
              '1s','2s','3s','4s','5s','6s','7s','8s','9s',
              '1z','2z','3z','4z','5z','6z','7z']

# Cached tile images
_tile_cache = {}

def _load_tile(name):
    """Load a tile image by name like '1m', '5z', etc."""
    if name not in _tile_cache:
        path = os.path.join(TILE_DIR, f"{name}.png")
        if os.path.exists(path):
            _tile_cache[name] = Image.open(path).convert("RGBA")
        else:
            _tile_cache[name] = Image.new("RGBA", (70, 100), (200, 200, 200, 255))
    return _tile_cache[name]

def _load_tile_by_index(idx):
    """Load tile image by 0-33 index"""
    if 0 <= idx < 34:
        return _load_tile(TILE_NAMES[idx])
    return Image.new("RGBA", (70, 100), (200, 200, 200, 255))

# Font helpers
_font_cache = {}
def _get_font(size):
    key = size
    if key not in _font_cache:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
            "/usr/share/fonts/wenquanyi/wqy-zenhei.ttc",
        ]
        font = None
        for p in candidates:
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, size)
                    break
                except:
                    pass
        if font is None:
            font = ImageFont.load_default()
        _font_cache[key] = font
    return _font_cache[key]

def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

# Colors — dark theme
BG_COLOR = (26, 26, 38)
PANEL_COLOR = (38, 38, 54)
TITLE_COLOR = (240, 230, 210)
SUBTITLE_COLOR = (170, 170, 185)
HIGHLIGHT_COLOR = (255, 200, 80)
GOOD_COLOR = (120, 220, 160)
MUTED_COLOR = (110, 110, 125)
DIVIDER_COLOR = (55, 55, 72)
DEALER_ACCENT = (255, 180, 60)
NON_DEALER_ACCENT = (100, 180, 255)
POINT_BIG_COLOR = (255, 215, 100)

# Layout constants
TW, TH = 52, 74  # tile display size (scaled from 70x100)
PAD = 20
MARGIN = 10
WRAP_GAP = 4  # vertical gap between wrapped sub-rows
MAX_CONTENT_WIDTH = 620  # max content width before wrapping (for waiting-tile rows)
# The hand-tile row is never wrapped, so the image must be wide enough for it.
# This is the real minimum content width; it can exceed MAX_CONTENT_WIDTH.
MIN_IMG_WIDTH = 300

def _measure_wait_tile(draw, font_small):
    """Measure the width of one wait tile + count text."""
    cnt_text = "×4"
    cw, _ = _text_size(draw, cnt_text, font_small)
    return TW + 2 + cw + 6  # tile + gap + count text + gap

def render_pailli(sorted_tiles, n, shanten, best_discards, discard_info, kinds=None, drawn_tile=None, red_tiles=None):
    """
    Render the pailli analysis result as a PIL Image.
    
    Args:
        sorted_tiles: list of tile indices (0-33), already sorted
        n: number of tiles
        shanten: shanten number (-1 = win, 0 = tenpai, etc.)
        best_discards: list of tile indices for best discard options
        discard_info: list of (discard_tile_idx_or_None, {wait_idx: count}, total) tuples
        kinds: tuple of (general, seven_pairs, kokushi) shanten or None
        drawn_tile: tile index of the drawn tile (for visual indicator) or None
        red_tiles: list of tile indices that are red (赤5) or None
    """
    # Build red tile counter
    red_counts = {}
    if red_tiles:
        for rt in red_tiles:
            red_counts[rt] = red_counts.get(rt, 0) + 1
    # Fonts
    font_title = _get_font(22)
    font_body = _get_font(16)
    font_small = _get_font(13)
    
    # Temp draw for measuring
    tmp = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp)
    
    # --- Text content ---
    title_text = "牌理分析"
    hand_label = f"手牌 ({n}张)"
    
    if shanten == -1:
        shanten_text = "和牌"
        shanten_color = GOOD_COLOR
    elif shanten == 0:
        shanten_text = "听牌"
        shanten_color = GOOD_COLOR
    else:
        shanten_text = f"{shanten}向听"
        shanten_color = TITLE_COLOR
    
    if kinds:
        shanten_text += f"  (一般形{kinds[0]} / 七对子{kinds[1]} / 国士{kinds[2]})"
    
    # Section title
    if n == 14 and discard_info:
        section_title = "最优打法"
    elif n == 13 and discard_info:
        section_title = "听牌" if shanten == 0 else "进张"
    else:
        section_title = ""
    
    # --- Pre-process discard_info: sort waits by count desc ---
    processed_rows = []
    for dt, wait_groups, total in discard_info:
        sorted_waits = sorted(wait_groups.items(), key=lambda x: -x[1])
        processed_rows.append((dt, sorted_waits, total))
    
    # --- Measure row widths and count wrapped lines ---
    wait_tile_w = _measure_wait_tile(tmp_draw, font_small)
    
    # Hand-tile row width (never wrapped; determines the minimum image width)
    hand_row_width = n * TW + (n - 1) * 2
    if drawn_tile is not None:
        hand_row_width += 8  # separator gap before drawn tile
    
    row_layouts = []  # (dt, sorted_waits, total, num_lines, indent)
    max_row_width = 0
    
    for dt, sorted_waits, total in processed_rows:
        # Calculate indent (prefix width)
        indent = 0
        if dt is not None:
            indent += TW + 8
            arrow_text = "→ 听" if shanten == 0 else "→ 进张"
            aw, _ = _text_size(tmp_draw, arrow_text, font_body)
            indent += aw + 8
        else:
            label = "听牌: " if shanten == 0 else "进张: "
            lw, _ = _text_size(tmp_draw, label, font_body)
            indent += lw + 4
        
        # Calculate total text width
        total_text = f"({total}枚)"
        tw2, _ = _text_size(tmp_draw, total_text, font_small)
        total_w = tw2 + 6
        
        # The content width available to this row = the widest of (hand row, MIN)
        # minus the indent. The hand row determines the canvas, so use it here
        # so wrapping is consistent with the actual draw width.
        row_content_w = max(hand_row_width, MIN_IMG_WIDTH)
        avail_width = row_content_w - indent
        x = 0
        num_lines = 1
        row_w = indent
        first_on_line = True
        
        for wt, cnt in sorted_waits:
            cnt_text = f"×{cnt}"
            cw, _ = _text_size(tmp_draw, cnt_text, font_small)
            item_w = TW + 2 + cw + 6
            
            if not first_on_line and x + item_w > avail_width:
                # Wrap
                num_lines += 1
                row_w = max(row_w, indent + x)
                x = 0
                first_on_line = True
            
            x += item_w
            first_on_line = False
        
        # Last line + total
        last_line_w = indent + x + total_w
        row_w = max(row_w, last_line_w)
        
        row_layouts.append((dt, sorted_waits, total, num_lines, indent, total_text, total_w))
        max_row_width = max(max_row_width, row_w)
    
    # Content width = the wider of the hand row and the widest content row.
    # The hand-tile row is never wrapped, so it always fits; never cap it.
    content_width = max(hand_row_width, max_row_width, MIN_IMG_WIDTH)
    img_width = content_width + PAD * 2
    
    # --- Calculate height ---
    y = PAD
    y += 28 + MARGIN        # title
    y += 20 + 4              # hand label
    y += TH + 4 + MARGIN     # hand tiles
    y += 22 + MARGIN         # shanten
    y += 1 + MARGIN          # divider
    if section_title:
        y += 20 + 4          # section title
    if row_layouts:
        for _, _, _, num_lines, _, _, _ in row_layouts:
            y += num_lines * TH + (num_lines - 1) * WRAP_GAP + 6
    y += PAD
    img_height = y
    
    # --- Draw ---
    img = Image.new("RGBA", (img_width, img_height), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)
    
    y = PAD
    
    # Title
    draw.text((PAD, y), title_text, fill=TITLE_COLOR, font=font_title)
    y += 28 + MARGIN
    
    # Hand label
    draw.text((PAD, y), hand_label, fill=SUBTITLE_COLOR, font=font_body)
    y += 20 + 4
    
    # Hand tiles
    x = PAD
    drawn_idx = None
    if drawn_tile is not None:
        # Find the drawn tile's position in the sorted list (first match from end,
        # so if there are duplicates the last one is treated as the draw)
        for idx in range(len(sorted_tiles) - 1, -1, -1):
            if sorted_tiles[idx] == drawn_tile:
                drawn_idx = idx
                break
    red_remaining = dict(red_counts)  # track remaining red tiles per type
    for i, t_idx in enumerate(sorted_tiles):
        # Add separator gap before drawn tile (天凤 style)
        if drawn_idx is not None and i == drawn_idx:
            x += 8
        # Check if this tile is red
        use_red_img = False
        if red_remaining.get(t_idx, 0) > 0:
            use_red_img = True
            red_remaining[t_idx] -= 1
        # Load appropriate tile image
        if use_red_img:
            suit = t_idx // 9
            if suit < 3:  # m/p/s only
                red_name = f"0{'mps'[suit]}"
                tile_img = _load_tile(red_name)
            else:
                tile_img = _load_tile_by_index(t_idx)
        else:
            tile_img = _load_tile_by_index(t_idx)
        tile_resized = tile_img.resize((TW, TH), Image.LANCZOS)
        img.paste(tile_resized, (x, y), tile_resized)
        if drawn_idx is not None and i == drawn_idx:
            # Subtle highlight underline for drawn tile
            draw.line(
                [x, y + TH + 1, x + TW - 1, y + TH + 1],
                fill=(220, 50, 50), width=2
            )
        x += TW + 2
    y += TH + 4 + MARGIN
    
    # Shanten
    draw.text((PAD, y), shanten_text, fill=shanten_color, font=font_body)
    y += 22 + MARGIN
    
    # Divider
    draw.line([(PAD, y), (img_width - PAD, y)], fill=DIVIDER_COLOR, width=1)
    y += 1 + MARGIN
    
    # Section title
    if section_title:
        draw.text((PAD, y), section_title, fill=TITLE_COLOR, font=font_body)
        y += 20 + 4
    
    # Discard rows
    for dt, sorted_waits, total, num_lines, indent, total_text, total_w in row_layouts:
        x = PAD
        
        if dt is not None:
            # Discard tile
            tile_img = _load_tile_by_index(dt)
            tile_resized = tile_img.resize((TW, TH), Image.LANCZOS)
            img.paste(tile_resized, (x, y), tile_resized)
            x += TW + 8
            # Arrow
            arrow_text = "→ 听" if shanten == 0 else "→ 进张"
            draw.text((x, y + TH // 2 - 8), arrow_text, fill=SUBTITLE_COLOR, font=font_body)
            aw, _ = _text_size(draw, arrow_text, font_body)
            x += aw + 8
        else:
            label = "听牌: " if shanten == 0 else "进张: "
            draw.text((x, y + TH // 2 - 8), label, fill=SUBTITLE_COLOR, font=font_body)
            x += indent
        
        # Wait tiles with wrapping
        # Use the SAME avail width as in the measure phase so the wrap points match.
        avail_width = max(hand_row_width, MIN_IMG_WIDTH) - indent
        line_x = 0
        first_on_line = True
        
        for wt, cnt in sorted_waits:
            cnt_text = f"×{cnt}"
            cw, _ = _text_size(draw, cnt_text, font_small)
            item_w = TW + 2 + cw + 6
            
            if not first_on_line and line_x + item_w > avail_width:
                # Wrap to next line
                y += TH + WRAP_GAP
                line_x = 0
                first_on_line = True
            
            tx = x + line_x
            tile_img = _load_tile_by_index(wt)
            tile_resized = tile_img.resize((TW, TH), Image.LANCZOS)
            img.paste(tile_resized, (tx, y), tile_resized)
            line_x += TW + 2
            draw.text((tx + TW + 2, y + TH - 14), cnt_text, fill=MUTED_COLOR, font=font_small)
            line_x += cw + 6
            first_on_line = False
        
        # Total text at end of last line
        total_x = x + line_x
        draw.text((total_x, y + TH // 2 - 8), total_text, fill=MUTED_COLOR, font=font_small)
        
        y += TH + 6
    
    return img


def save_pailli_image(img, path):
    """Save the rendered image to a file."""
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        bg = Image.new("RGB", img.size, BG_COLOR)
        bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        bg.save(path, quality=95)
    else:
        img.save(path)


def _scaled_tile(idx, tw=TW, th=TH):
    """Load and scale a tile image to display size."""
    t = _load_tile_by_index(idx)
    if t.size != (tw, th):
        return t.resize((tw, th), Image.LANCZOS)
    return t


def render_agari_dual(result_dealer, result_non, red_tiles=None):
    """Render dealer + non-dealer agari results in a single image.
    Dark theme, two-column point layout.
    """
    font_title = _get_font(24)
    font_label = _get_font(14)
    font_body = _get_font(15)
    font_yaku = _get_font(15)
    font_points_big = _get_font(28)
    font_points_sm = _get_font(13)
    font_han = _get_font(16)

    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)

    tiles_list = result_dealer.get('tiles', [])
    melds = result_dealer.get('melds', [])
    yaku = result_dealer.get('yaku', [])
    yakuman = result_dealer.get('yakuman', 0)
    han = result_dealer.get('han', 0)
    fu = result_dealer.get('fu', 0)
    wait = result_dealer.get('wait', '')
    wt_idx = result_dealer.get('winning_tile', -1)

    pad = PAD
    tile_gap = 2
    sep_gap = 10
    meld_gap = 16

    # figure out which tiles belong to melds (both open and closed)
    meld_tile_sets = []
    meld_tile_indices = set()
    for m in melds:
        start = m['tile']
        mt = m['type']
        if mt == 'sequence':
            meld_tiles = [start, start+1, start+2]
        elif mt == 'triplet':
            meld_tiles = [start, start, start]
        elif mt == 'quad':
            meld_tiles = [start]*4
        else:
            meld_tiles = [start, start+1, start+2]
        meld_tile_sets.append(meld_tiles)
        for t in meld_tiles:
            meld_tile_indices.add(t)

    # sort tiles, pull winning tile to end, remove meld tiles
    sorted_tiles = sorted(tiles_list)
    remaining = list(sorted_tiles)
    for mset in meld_tile_sets:
        for t in mset:
            if t in remaining:
                remaining.remove(t)
    wt_removed = False
    display_tiles = []
    for t in remaining:
        if not wt_removed and t == wt_idx:
            wt_removed = True
            continue
        display_tiles.append(t)

    # dynamic width: fit all tiles
    hand_w = len(display_tiles) * (TW + tile_gap)
    if wt_removed:
        hand_w += sep_gap + TW
    for mset in meld_tile_sets:
        hand_w += meld_gap + len(mset) * (TW + tile_gap)

    content_w = max(hand_w, 560)
    img_w = content_w + pad * 2

    yaku_lines = len(yaku) if yaku else 1
    yaku_h = yaku_lines * 22

    col_w = (content_w - 12) // 2
    point_block_h = 82

    wait_map = {
        'ryanmen': '両面待ち', 'kanchan': '嵌張待ち', 'penchan': '辺張待ち',
        'tanki': '単騎待ち', 'shanpon': '双碰待ち', '13面': '十三面待ち',
    }
    wait_str = wait_map.get(wait, wait) if wait else ''

    # total height
    total_h = pad + 30  # title bar
    total_h += 8 + TH + 8  # tiles
    total_h += 1 + 8 + yaku_h + 10  # divider + yaku
    total_h += point_block_h + 10  # point blocks (side by side)
    if wait_str:
        total_h += 22
    total_h += pad

    img = Image.new("RGBA", (img_w, total_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # title bar
    draw.rectangle([0, 0, img_w, 30], fill=(20, 20, 32))
    draw.text((pad, 3), "和牌結果", fill=TITLE_COLOR, font=font_title)
    if yakuman > 0:
        summary = f"役満×{yakuman}"
    else:
        summary = f"{han}飜 {fu}符"
    sw = draw.textlength(summary, font=font_han)
    draw.text((img_w - pad - sw, 7), summary, fill=HIGHLIGHT_COLOR, font=font_han)

    y = 34

    # tiles row
    x = pad
    # concealed tiles
    for ti in display_tiles:
        t_img = _scaled_tile(ti)
        draw._image.paste(t_img, (x, y), t_img)
        x += TW + tile_gap
    # winning tile with separator
    if wt_removed:
        x += sep_gap - tile_gap
        t_img = _scaled_tile(wt_idx)
        draw._image.paste(t_img, (x, y), t_img)
        x += TW + tile_gap
    # melds
    for mset in meld_tile_sets:
        x += meld_gap - tile_gap
        for ti in mset:
            t_img = _scaled_tile(ti)
            draw._image.paste(t_img, (x, y), t_img)
            x += TW + tile_gap
    y += TH + 8

    # divider
    draw.line((pad, y, img_w - pad, y), fill=DIVIDER_COLOR, width=1)
    y += 8

    # yaku list — two columns if > 4 items
    if yaku:
        use_two_col = len(yaku) > 4
        per_col = (len(yaku) + 1) // 2 if use_two_col else len(yaku)
        for i, (name, h, is_ym) in enumerate(yaku):
            if use_two_col:
                col = 0 if i < per_col else 1
                row = i if col == 0 else i - per_col
            else:
                col = 0
                row = i
            tx = pad + col * (col_w + 12)
            ty = y + row * 22
            txt = name
            if is_ym:
                txt += f"  役満"
            else:
                txt += f"  {h}飜"
            color = HIGHLIGHT_COLOR if is_ym else SUBTITLE_COLOR
            draw.text((tx, ty), txt, fill=color, font=font_yaku)
    else:
        draw.text((pad, y), "無役", fill=MUTED_COLOR, font=font_body)
    y += yaku_h + 10

    # point blocks side by side
    _draw_point_block_v2(draw, result_dealer, pad, y, col_w, point_block_h,
                         font_label, font_points_big, font_points_sm, DEALER_ACCENT, "親家")
    _draw_point_block_v2(draw, result_non, pad + col_w + 12, y, col_w, point_block_h,
                         font_label, font_points_big, font_points_sm, NON_DEALER_ACCENT, "子家")
    y += point_block_h + 10

    if wait_str:
        draw.text((pad, y), wait_str, fill=MUTED_COLOR, font=font_body)

    return img


def _draw_point_block_v2(draw, result, x, y, w, h, font_label, font_big, font_sm, accent, label):
    """Draw a compact point block with accent border on left."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=PANEL_COLOR)
    draw.rectangle([x, y, x + 3, y + h], fill=accent)

    pts = result.get('points', {})
    total = pts.get('total', 0)
    detail = pts.get('detail', '')
    base_name = pts.get('base_name', '')

    draw.text((x + 12, y + 8), label, fill=accent, font=font_label)

    pts_text = f"{total:,}"
    draw.text((x + 12, y + 24), pts_text, fill=POINT_BIG_COLOR, font=font_big)
    bw = draw.textlength(pts_text, font=font_big)
    draw.text((x + 12 + bw + 2, y + 38), "点", fill=SUBTITLE_COLOR, font=font_sm)

    if detail:
        short = detail.replace('庄家', '').replace('闲家', '').replace('荣和', '栄和').strip()
        draw.text((x + 12, y + 62), short, fill=GOOD_COLOR, font=font_sm)

    if base_name:
        bw2 = draw.textlength(base_name, font=font_sm)
        draw.text((x + w - bw2 - 10, y + 8), base_name, fill=accent, font=font_sm)

