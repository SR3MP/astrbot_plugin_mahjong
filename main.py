# astrbot_plugin_mahjong © 2026 SR3MP
# Based on Xpilot © 2025 Fyisvia Virell — https://mj.fyisvia.com
# Licensed under AGPL-3.0 with Additional Terms (see LICENSE).
# Note: Certain non-code assets (including datasets, content sets, or media files)
# are excluded from the AGPL license and may NOT be publicly published or redistributed
# without written permission from the author. (See LICENSE for details)

"""
立直麻将工具插件 (AstrBot)
==========================
雀魂/天凤规则 - 牌理、和牌役数、符数、点数计算

触发方式 (群内):
    牌理 123m234p345s11z
    和牌 123m234p456s11z+1z
    和牌 123m234p456s11z+1z 自 庄
    和牌 123m234p456s11z+1z 自 立 场风东 自风东 d6m
    麻将帮助
"""
import re
import random
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

PLUGIN_DIR = Path(__file__).resolve().parent
TEMP_DIR = PLUGIN_DIR / "tmp"
TEMP_DIR.mkdir(exist_ok=True)

import sys
sys.path.insert(0, str(PLUGIN_DIR))

import riichi
import pailli_image


HELP_TEXT = """🀄 立直麻将工具 (雀魂/天凤规则)

牌理: 牌理 <牌面>
  输入手牌, 自动算向听/进张/切牌
  例: 牌理 123m234p345s11z

和牌: 和牌 <牌面>[+和牌] [选项]
  例: 和牌 123m234p456s11z+1z 自 庄
  例: 和牌 123m(444p)345s11z+1z 荣和
  门清时不写条件会询问是否立直/自摸

选项 (全称或缩写均可):
  自摸/自, 荣和        (默认荣和)
  立直/立, 一发/一     (缩写可连写: 立一自)
  场风东/南/西/北      (默认东)
  自风东/南/西/北      (默认东)
  宝牌1 / d1 / dora1 (宝牌个数, 不区分大小写)
  海底/河底/岭上/枪杠
  天和/地和
  亲家/子家结果自动同时输出

和牌副露 (仅和牌命令):
  (111z)或（111z）  明刻/明顺/明杠
  [1111m]或【1111m】 暗杠
  [1m]或【1m】 暗杠简写(1张代表4张)"""


@register("astrbot_plugin_mahjong", "SR3MP", "立直麻将工具", "1.1.0")
class RiichiPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config

    # ---------- 牌理 ----------
    @filter.command("牌理")
    async def on_pailli(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        if not text:
            yield event.plain_result("请输入牌面, 例如: 牌理 123m234p345s11z")
            return
        try:
            red_tiles = []
            tiles = riichi.parse_tiles(text, red_tiles)
        except ValueError as e:
            yield event.plain_result(f"解析失败: {e}")
            return

        n = len(tiles)
        if n == 0:
            yield event.plain_result("手牌为空")
            return

        # 和牌判定 (任何张数, 包括副露)
        cc = [0] * 34
        for t in tiles:
            cc[t] += 1
        if riichi._shanten_solver.calc(cc) == -1:
            sorted_tiles = riichi.sort_tiles(tiles)
            img = pailli_image.render_pailli(sorted_tiles, len(tiles), -1, [], [], None, red_tiles=red_tiles)
            img_path = str(TEMP_DIR / "pailli_result.png")
            pailli_image.save_pailli_image(img, img_path)
            yield event.image_result(img_path)
            return

        # 根据张数模式处理（参考天凤）
        drawn_tile = None
        display_tiles = list(tiles)

        if n % 3 == 1:
            # 3k+1张：随机摸一张变3k+2，切牌模式
            drawn_tile = self._random_draw(tiles)
            if drawn_tile is None:
                yield event.plain_result("没有可摸的牌了")
                return
            display_tiles.append(drawn_tile)
            n += 1
        elif n % 3 == 0 and n >= 3:
            # 3k张：随机摸一张变3k+1，正常向听模式
            drawn_tile = self._random_draw(tiles)
            if drawn_tile is None:
                yield event.plain_result("没有可摸的牌了")
                return
            display_tiles.append(drawn_tile)
            n += 1
        # 3k+2张：直接走切牌模式

        sorted_tiles = riichi.sort_tiles(display_tiles)

        # 向听数
        shanten, best_discards, discard_info, kinds = riichi.shanten_for_hand(display_tiles)

        # 计算进张枚数
        def _ukeire_counts(hand_tiles, wait_indices):
            cc = [0] * 34
            for t in hand_tiles:
                cc[t] += 1
            groups = {}
            total = 0
            for wt in wait_indices:
                avail = 4 - cc[wt]
                if avail <= 0:
                    continue
                groups[wt] = groups.get(wt, 0) + avail
                total += avail
            return groups, total

        # 构建 discard_info_render
        discard_info_render = []
        if best_discards:
            # 3k+2张：切牌分析
            for dt, waits in discard_info:
                hand = list(display_tiles)
                hand.remove(dt)
                groups, total = _ukeire_counts(hand, waits)
                discard_info_render.append((dt, groups, total))
            discard_info_render.sort(key=lambda x: -x[2])
        else:
            # 3k+1张：直接进张
            groups, total = _ukeire_counts(display_tiles, discard_info)
            discard_info_render.append((None, groups, total))

        # 渲染图片
        img = pailli_image.render_pailli(
            sorted_tiles, n, shanten, best_discards,
            discard_info_render, kinds,
            drawn_tile=drawn_tile,
            red_tiles=red_tiles
        )
        img_path = str(TEMP_DIR / "pailli_result.png")
        pailli_image.save_pailli_image(img, img_path)
        yield event.image_result(img_path)

    def _random_draw(self, tiles):
        """随机摸一张牌，返回牌索引"""
        cc = [0] * 34
        for t in tiles:
            cc[t] += 1
        avail = [i for i in range(34) if cc[i] < 4]
        if not avail:
            return None
        return random.choice(avail)

    # ---------- 和牌 ----------
    @filter.command("和牌", alias={"算点", "点数计算"})
    async def on_agari(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        if not text:
            yield event.plain_result(HELP_TEXT)
            return

        options = self._parse_options(text)
        hand_text = options.pop('_hand_text')

        # 判断是否门清
        is_menzen = self._check_menzen(hand_text)

        # 门清且未指定立直/自摸 → 交互询问
        if is_menzen and not options.get('is_riichi') and not options.get('is_tsumo'):
            yield event.plain_result("门清和牌，请补充条件\n立=立直  自=自摸  立自=两者\n荣和=门前荣和(默认)")
            try:
                reply = await self._wait_user_input(event, timeout=30)
                if reply:
                    extra_opts = {}
                    self._parse_opt_token(reply.strip(), extra_opts)
                    options.update(extra_opts)
            except Exception:
                pass

        # 同时计算亲家和子家
        opts_dealer = dict(options, is_dealer=True)
        opts_non = dict(options, is_dealer=False)

        result_dealer = riichi.analyze_hand(hand_text, opts_dealer)
        result_non = riichi.analyze_hand(hand_text, opts_non)

        if not result_dealer['success']:
            yield event.plain_result(f"❌ {result_dealer.get('error', '解析失败')}")
            return

        if not result_dealer.get('is_win', False):
            yield event.plain_result(
                f"手牌: {result_dealer.get('tiles_formatted', '')}\n"
                f"❌ {result_dealer.get('error', '未和牌')}"
            )
            return

        # 渲染图片 (亲家+子家)
        img = pailli_image.render_agari_dual(result_dealer, result_non)
        img_path = str(TEMP_DIR / "agari_result.png")
        pailli_image.save_pailli_image(img, img_path)
        yield event.image_result(img_path)

    async def _wait_user_input(self, event, timeout=30):
        """等待用户回复，返回文本"""
        from astrbot.api.util import session_waiter, SessionController

        @session_waiter(timeout)
        async def waiter(controller: SessionController, ev: AstrMessageEvent):
            txt = ev.message_str.strip()
            if txt:
                controller._reply = txt
                controller.stop()

        try:
            await waiter(event)
            return getattr(event, '_reply', None)
        except TimeoutError:
            return None

    def _check_menzen(self, hand_text):
        """判断手牌是否门清 (无副露括号)"""
        for ch in hand_text:
            if ch in '()（）【[]':
                return False
        return True

    # ---------- 帮助 ----------
    @filter.command("麻将帮助", alias={"立直帮助"})
    async def on_help(self, event: AstrMessageEvent):
        yield event.plain_result(HELP_TEXT)

    # ---------- 选项解析 ----------
    def _parse_options(self, text):
        """解析和牌选项
        支持全称与缩写: 自摸/自, 立直/立, 一发/一
        缩写可连写: 立一自 (也可用空格隔开)
        宝牌: 宝牌6m / d6m / dora6m (不区分大小写)
        返回: {'_hand_text': str, ...options}
        """
        options = {}
        parts = text.split()

        hand_parts = []
        # 先按空格切，处理单独 token；再处理连写缩写
        for p in parts:
            if self._parse_opt_token(p, options):
                continue
            hand_parts.append(p)

        options['_hand_text'] = ''.join(hand_parts)
        return options

    def _parse_opt_token(self, p, options):
        """解析一个 token，返回 True 表示识别为选项"""
        # 庄家/亲家/闲家/子家
        seat = {
            '庄家': 'is_dealer', '庄': 'is_dealer', '亲家': 'is_dealer', '親家': 'is_dealer',
            '闲家': 'is_non_dealer', '闲': 'is_non_dealer', '子家': 'is_non_dealer', '子': 'is_non_dealer',
        }
        if p in seat:
            # 庄/亲/闲/子 仅标记，不设 is_dealer（因为现在同时算两种）
            return True

        # 单独缩写/全称
        full = {
            '自摸': 'is_tsumo', '自': 'is_tsumo',
            '荣和': None, '榮和': None,
            '立直': 'is_riichi', '立': 'is_riichi',
            '一发': 'is_ippatsu', '一發': 'is_ippatsu', '一': 'is_ippatsu',
            '海底': 'is_haitei', '河底': 'is_houtei',
            '岭上': 'is_rinshan', '嶺上': 'is_rinshan',
            '枪杠': 'is_chankan', '槍槓': 'is_chankan',
            '天和': 'is_tenhou', '地和': 'is_chiihou',
        }
        if p in full:
            key = full[p]
            if key is None:
                options['is_tsumo'] = False
            else:
                options[key] = True
            return True

        # 宝牌 / d / dora (不区分大小写)
        # d1 = 宝牌1个, d2 = 宝牌2个; d6m = 指定宝牌牌面
        low = p.lower()
        for prefix in ('宝牌', 'dora', 'd'):
            if low.startswith(prefix) and len(p) > len(prefix):
                val = p[len(prefix):]
                if val.isdigit() and int(val) >= 1:
                    options['dora_count'] = int(val)
                    return True
                # 也支持指定宝牌牌面 (如 d6m)
                try:
                    options['dora_indicators'] = riichi.parse_tiles(val)
                    return True
                except:
                    pass

        # 场风/自风
        for prefix, key in (('场风', 'round_wind'), ('場風', 'round_wind'),
                            ('自风', 'seat_wind'), ('自風', 'seat_wind')):
            if p.startswith(prefix) and len(p) > len(prefix):
                options[key] = self._parse_wind(p[len(prefix):])
                return True

        # 连写缩写: 立一自 / 一立 / 自立 等 (由 立/一/自/荣 组成)
        # 也支持混合: 立一自d3, 立荣d1, 立自dora5m
        # 先尝试提取 d/dora 宝牌后缀
        dora_handled = False
        for prefix in ('dora', 'd'):
            idx = low.find(prefix)
            if idx > 0:
                dora_val = p[idx + len(prefix):]
                # 纯数字 = 宝牌数量
                if dora_val.isdigit() and int(dora_val) >= 1:
                    options['dora_count'] = int(dora_val)
                    dora_handled = True
                    p = p[:idx]
                    low = p.lower()
                    break
                # 牌面格式 (如 6m)
                try:
                    options['dora_indicators'] = riichi.parse_tiles(dora_val)
                    dora_handled = True
                    p = p[:idx]
                    low = p.lower()
                    break
                except:
                    pass

        # 解析剩余的连写缩写
        # 支持字符: 立(立直) 一(一发) 自(自摸) 荣/榮(荣和=tsumo False)
        abbrev_map = {'立': 'is_riichi', '一': 'is_ippatsu', '自': 'is_tsumo', '荣': '_ron', '榮': '_ron'}
        if p and all(c in abbrev_map for c in p) and len(p) >= 1:
            for c in p:
                key = abbrev_map[c]
                if key == '_ron':
                    options['is_tsumo'] = False
                else:
                    options[key] = True
            return True

        if dora_handled:
            return True

        return False

    def _parse_wind(self, text):
        """解析风牌: 东→27, 南→28, 西→29, 北→30"""
        wind_map = {'东': 27, '東': 27, '南': 28, '西': 29, '北': 30}
        return wind_map.get(text, 27)
