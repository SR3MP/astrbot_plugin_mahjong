"""
立直麻将核心逻辑 - 雀魂/天凤规则
完全按照 Xpilot (https://github.com/fyisvia/Xpilot) 改造
移植: shanten.js / yakucalculation.js / HandPointCalculation.vue / evaluation.js
"""
import math

# ==================== 常量 ====================
TILE_NAMES = ['1m','2m','3m','4m','5m','6m','7m','8m','9m',
              '1p','2p','3p','4p','5p','6p','7p','8p','9p',
              '1s','2s','3s','4s','5s','6s','7s','8s','9s',
              '1z','2z','3z','4z','5z','6z','7z']
TILE_CN = ['一万','二万','三万','四万','五万','六万','七万','八万','九万',
           '一饼','二饼','三饼','四饼','五饼','六饼','七饼','八饼','九饼',
           '一索','二索','三索','四索','五索','六索','七索','八索','九索',
           '东','南','西','北','白','发','中']
SUIT_OFFSET = {'m':0,'p':9,'s':18,'z':27}
SUIT_STR = 'mpsz'

# Xpilot string-based constants
TERMINALS_HONOURS_STR = {'1m','9m','1p','9p','1s','9s','1z','2z','3z','4z','5z','6z','7z'}
TERMINAL_STR = {'1m','9m','1p','9p','1s','9s'}
HONOR_STR = {'1z','2z','3z','4z','5z','6z','7z'}
DRAGON_STR = {'5z','6z','7z'}
WIND_MAP = {'east':'1z','south':'2z','west':'3z','north':'4z'}

# ==================== 牌索引<->字符串转换 ====================
def idx_to_str(idx):
    if idx < 9: return f'{idx+1}m'
    elif idx < 18: return f'{idx-9+1}p'
    elif idx < 27: return f'{idx-18+1}s'
    else: return f'{idx-27+1}z'

def str_to_idx(s):
    n = 5 if s[0]=='0' else int(s[0])
    suit = s[-1]
    return SUIT_OFFSET[suit] + n - 1

def normalize_tile_str(t):
    if t[0]=='0': return '5'+t[1:]
    return t

def tile_sort_key(t):
    so = {'m':0,'p':1,'s':2,'z':3}
    n = 5.5 if t[0]=='0' else int(t[0])
    return (so[t[-1]], n)

def sort_tiles_str(tiles):
    return sorted(tiles, key=tile_sort_key)

# ==================== 原有工具函数 ====================
def suit_of(t): return t // 9
def num_of(t): return t % 9
def tile_name(t): return TILE_NAMES[t]
def tile_cn(t): return TILE_CN[t]

# ==================== 解析 ====================
def parse_tiles(text, red_tiles=None):
    tiles, digits = [], []
    if red_tiles is None: red_tiles = []
    for ch in text:
        if ch.isdigit(): digits.append(int(ch))
        elif ch in 'mpsz':
            for d in digits:
                if d == 0 and ch != 'z':
                    d = 5
                    red_tiles.append(SUIT_OFFSET[ch]+d-1)
                if ch == 'z' and (d<1 or d>7): raise ValueError(f'字牌无效: {d}z')
                if ch != 'z' and (d<1 or d>9): raise ValueError(f'数牌无效: {d}{ch}')
                tiles.append(SUIT_OFFSET[ch]+d-1)
            digits = []
    if digits: raise ValueError('数字后缺少花色')
    return tiles

def parse_hand_input(text):
    text = text.strip()
    wt = None
    if '+' in text:
        p = text.split('+',1)
        text = p[0].strip()
        wts = parse_tiles(p[1].strip())
        if len(wts)!=1: raise ValueError('和牌应为1张')
        wt = wts[0]
    concealed, melds, i = [], [], 0
    open_pairs = {'(' : ')', '（': '）'}
    closed_pairs = {'[': ']', '【': '】'}
    while i < len(text):
        ch = text[i]
        if ch in open_pairs:
            close = open_pairs[ch]
            j = text.index(close, i)
            melds.append(_classify(parse_tiles(text[i+1:j]), True))
            i = j+1
        elif ch in closed_pairs:
            close = closed_pairs[ch]
            j = text.index(close, i)
            melds.append(_classify(parse_tiles(text[i+1:j]), False))
            i = j+1
        elif ch.isdigit() or ch in 'mpsz':
            k = i
            while k < len(text) and (text[k].isdigit() or text[k] in 'mpsz'): k += 1
            concealed.extend(parse_tiles(text[i:k]))
            i = k
        else: i += 1
    nmt = sum(3 if m['type'] in ('triplet','sequence') else 4 for m in melds)
    nq = sum(1 for m in melds if m['type']=='quad')
    ec = 14 + nq - nmt
    if wt is not None: concealed.append(wt)
    else:
        if len(concealed)<2: raise ValueError('没有手牌')
        wt = concealed[-1]
    if len(concealed)<ec: raise ValueError(f'暗手牌不足: {len(concealed)}张, 需要{ec}张')
    if wt not in concealed: raise ValueError(f'和牌{tile_name(wt)}不在手牌中')
    return {'concealed':concealed, 'melds':melds, 'winning_tile':wt}

def _classify(tiles, open_):
    if len(tiles)==3:
        if tiles[0]==tiles[1]==tiles[2]: return {'type':'triplet','tile':tiles[0],'open':open_}
        s = sorted(tiles)
        if suit_of(s[0])==suit_of(s[1])==suit_of(s[2])<3 and s[0]+1==s[1] and s[1]+1==s[2]:
            return {'type':'sequence','tile':s[0],'open':open_}
        raise ValueError(f'无效面子: {tiles}')
    elif len(tiles)==4:
        if all(t==tiles[0] for t in tiles): return {'type':'quad','tile':tiles[0],'open':open_}
        raise ValueError(f'无效杠子: {tiles}')
    elif len(tiles)==1 and not open_:
        # 暗杠便捷输入: [1m] 或 【1m】 = 1111m
        return {'type':'quad','tile':tiles[0],'open':False}
    raise ValueError(f'面子张数无效: {len(tiles)}')

def sort_tiles(tiles): return sorted(tiles)
def format_tiles(tiles):
    tiles=sorted(tiles)
    if not tiles: return ''
    parts, cs, cn = [], None, []
    for t in tiles:
        s,n = suit_of(t), num_of(t)+1
        if s!=cs:
            if cn: parts.append(''.join(str(x) for x in cn)+SUIT_STR[cs])
            cs, cn = s, [n]
        else: cn.append(n)
    if cn: parts.append(''.join(str(x) for x in cn)+SUIT_STR[cs])
    return ''.join(parts)

def format_tiles_pretty(tiles): return ' '.join(tile_cn(t) for t in sorted(tiles))

def get_all_tiles(hand):
    tiles = list(hand['concealed'])
    for m in hand['melds']:
        if m['type']=='triplet': tiles.extend([m['tile']]*3)
        elif m['type']=='quad': tiles.extend([m['tile']]*4)
        elif m['type']=='sequence': tiles.extend([m['tile'],m['tile']+1,m['tile']+2])
    return tiles

def wind_idx_to_str(idx):
    return {27:'east',28:'south',29:'west',30:'north'}.get(idx,'east')

# ==================== Shanten (Xpilot shanten.js) ====================
class _ShantenCalc:
    AGARI_STATE = -1
    NUMERAL_COUNT = 27
    HAND_MAX_TILES = 14
    MAX_SHANTEN = 8
    KOKUSHI_INDICES = [0,8,9,17,18,26,27,28,29,30,31,32,33]

    def calc(self, tiles34, use_chiitoitsu=True, use_kokushi=True):
        results = []
        if use_chiitoitsu:
            s = self._chiitoitsu(tiles34)
            results.append(s)
            if s == self.AGARI_STATE: return self.AGARI_STATE
        if use_kokushi:
            s = self._kokushi(tiles34)
            results.append(s)
            if s == self.AGARI_STATE: return self.AGARI_STATE
        results.append(self._regular(tiles34))
        return min(results)

    def _chiitoitsu(self, t):
        cnt2=cnt3=cnt4=0
        for c in t:
            if c==2: cnt2+=1
            elif c==3: cnt3+=1
            elif c==4: cnt4+=1
        if cnt2==4 and cnt3==2: return 1
        if cnt2==5 and cnt4==1: return 1
        if cnt2==7: return self.AGARI_STATE
        return 6-(cnt2+cnt3+cnt4)

    def _kokushi(self, t):
        unique = sum(1 for i in self.KOKUSHI_INDICES if t[i]>0)
        has_pair = any(t[i]>=2 for i in self.KOKUSHI_INDICES)
        return 13-unique-(1 if has_pair else 0)

    def _regular(self, tiles34):
        self.tiles = tiles34[:]
        self.number_melds=0; self.number_tatsu=0; self.number_pairs=0
        self.number_jidahai=0; self.number_characters=0; self.number_isolated_tiles=0
        self.min_shanten = self.MAX_SHANTEN
        count = sum(tiles34)
        if count > self.HAND_MAX_TILES: count = self.HAND_MAX_TILES
        self._remove_character_tiles(count)
        init_mentsu = (14-count)//3
        self._scan(init_mentsu)
        return self.min_shanten

    def _scan(self, init_mentsu):
        self.number_characters = 0
        for i in range(self.NUMERAL_COUNT):
            if self.tiles[i]==4: self.number_characters |= (1<<i)
        self.number_melds += init_mentsu
        self._run(0)

    def _run(self, depth):
        if self.min_shanten==self.AGARI_STATE: return
        while depth<self.NUMERAL_COUNT and self.tiles[depth]==0: depth+=1
        if depth>=self.NUMERAL_COUNT: self._update_result(); return
        t=self.tiles; i=depth%9; tc=t[depth]; t1=t[depth+1]; t2=t[depth+2]
        t3=t[depth+3] if depth+3<34 else 0
        if tc==4:
            self._inc_set(depth)
            if i<7 and t2:
                if t1: self._inc_syuntsu(depth); self._run(depth+1); self._dec_syuntsu(depth)
                self._inc_tatsu2(depth); self._run(depth+1); self._dec_tatsu2(depth)
            if i<8 and t1: self._inc_tatsu1(depth); self._run(depth+1); self._dec_tatsu1(depth)
            self._inc_isolated(depth); self._run(depth+1); self._dec_isolated(depth)
            self._dec_set(depth)
            self._inc_pair(depth)
            if i<7 and t2:
                if t1: self._inc_syuntsu(depth); self._run(depth); self._dec_syuntsu(depth)
                self._inc_tatsu2(depth); self._run(depth+1); self._dec_tatsu2(depth)
            if i<8 and t1: self._inc_tatsu1(depth); self._run(depth+1); self._dec_tatsu1(depth)
            self._dec_pair(depth)
        if tc==3:
            self._inc_set(depth); self._run(depth+1); self._dec_set(depth)
            self._inc_pair(depth)
            if i<7 and t1 and t2: self._inc_syuntsu(depth); self._run(depth+1); self._dec_syuntsu(depth)
            else:
                if i<7 and t2: self._inc_tatsu2(depth); self._run(depth+1); self._dec_tatsu2(depth)
                if i<8 and t1: self._inc_tatsu1(depth); self._run(depth+1); self._dec_tatsu1(depth)
            self._dec_pair(depth)
            if i<7 and t[depth+2]>=2 and t[depth+1]>=2:
                self._inc_syuntsu(depth); self._inc_syuntsu(depth); self._run(depth)
                self._dec_syuntsu(depth); self._dec_syuntsu(depth)
        if tc==2:
            self._inc_pair(depth); self._run(depth+1); self._dec_pair(depth)
            if i<7 and t2 and t1: self._inc_syuntsu(depth); self._run(depth); self._dec_syuntsu(depth)
        if tc==1:
            if i<6 and t1==1 and t2 and t3!=4:
                self._inc_syuntsu(depth); self._run(depth+2); self._dec_syuntsu(depth)
            else:
                self._inc_isolated(depth); self._run(depth+1); self._dec_isolated(depth)
                if i<7 and t2:
                    if t1: self._inc_syuntsu(depth); self._run(depth+1); self._dec_syuntsu(depth)
                    self._inc_tatsu2(depth); self._run(depth+1); self._dec_tatsu2(depth)
                if i<8 and t1: self._inc_tatsu1(depth); self._run(depth+1); self._dec_tatsu1(depth)

    def _update_result(self):
        ret = 8-self.number_melds*2-self.number_tatsu-self.number_pairs
        n_kouho = self.number_melds+self.number_tatsu
        if self.number_pairs: n_kouho += self.number_pairs-1
        elif self.number_characters and self.number_isolated_tiles:
            if (self.number_characters|self.number_isolated_tiles)==self.number_characters: ret+=1
        if n_kouho>4: ret += n_kouho-4
        if ret!=self.AGARI_STATE and ret<self.number_jidahai: ret=self.number_jidahai
        if ret<self.min_shanten: self.min_shanten=ret

    def _inc_set(self,k): self.tiles[k]-=3; self.number_melds+=1
    def _dec_set(self,k): self.tiles[k]+=3; self.number_melds-=1
    def _inc_pair(self,k): self.tiles[k]-=2; self.number_pairs+=1
    def _dec_pair(self,k): self.tiles[k]+=2; self.number_pairs-=1
    def _inc_syuntsu(self,k): self.tiles[k]-=1;self.tiles[k+1]-=1;self.tiles[k+2]-=1;self.number_melds+=1
    def _dec_syuntsu(self,k): self.tiles[k]+=1;self.tiles[k+1]+=1;self.tiles[k+2]+=1;self.number_melds-=1
    def _inc_tatsu1(self,k): self.tiles[k]-=1;self.tiles[k+1]-=1;self.number_tatsu+=1
    def _dec_tatsu1(self,k): self.tiles[k]+=1;self.tiles[k+1]+=1;self.number_tatsu-=1
    def _inc_tatsu2(self,k): self.tiles[k]-=1;self.tiles[k+2]-=1;self.number_tatsu+=1
    def _dec_tatsu2(self,k): self.tiles[k]+=1;self.tiles[k+2]+=1;self.number_tatsu-=1
    def _inc_isolated(self,k): self.tiles[k]-=1;self.number_isolated_tiles|=(1<<k)
    def _dec_isolated(self,k): self.tiles[k]+=1;self.number_isolated_tiles&=~(1<<k)

    def _remove_character_tiles(self, nc):
        number=0; isolated=0
        for i in range(27,34):
            if self.tiles[i]==4: self.number_melds+=1;self.number_jidahai+=1;number|=1<<(i-27);isolated|=1<<(i-27)
            if self.tiles[i]==3: self.number_melds+=1
            if self.tiles[i]==2: self.number_pairs+=1
            if self.tiles[i]==1: isolated|=1<<(i-27)
        if self.number_jidahai and nc%3==2: self.number_jidahai-=1
        if isolated:
            self.number_isolated_tiles|=1<<27
            if (number|isolated)==number: self.number_characters|=1<<27

_shanten_solver = _ShantenCalc()

def shanten_counts(counts, n=13):
    s1 = _shanten_solver._regular(counts)
    if n >= 13: s2=_shanten_solver._chiitoitsu(counts); s3=_shanten_solver._kokushi(counts)
    else: s2=s3=99
    return s1, s2, s3

def _ukeire(counts, current_shanten, n=13):
    waits=[]
    for t in range(34):
        if counts[t]>=4: continue
        counts[t]+=1
        s1=_shanten_solver._regular(counts)
        if n>=13: s=min(s1,_shanten_solver._chiitoitsu(counts),_shanten_solver._kokushi(counts))
        else: s=s1
        if s<current_shanten: waits.append(t)
        counts[t]-=1
    return waits

# ==================== HandDivider (Xpilot yakucalculation.js) ====================
class HandDivider:
    def normalize_tile(self, tile):
        if tile[0]=='0': return '5'+tile[1:]
        return tile

    def is_triplet(self, tiles):
        return tiles[0]==tiles[1]==tiles[2]

    def is_sequence(self, tiles):
        t1,t2,t3=tiles
        return (t1[-1]==t2[-1]==t3[-1] and int(t1[0])+1==int(t2[0]) and int(t2[0])+1==int(t3[0]))

    def is_meld(self, tiles):
        return self.is_triplet(tiles) or self.is_sequence(tiles)

    def find_melds(self, hand, current, results):
        if len(hand)==2:
            if hand[0]==hand[1]: results.append(current+[hand])
            return
        for i in range(len(hand)-2):
            for j in range(i+1, len(hand)-1):
                for k in range(j+1, len(hand)):
                    cand=[hand[i],hand[j],hand[k]]
                    is_all_honor = all(t[-1]=='z' for t in cand)
                    if is_all_honor and len(set(cand))!=1: continue
                    if self.is_meld(cand):
                        remaining=[t for idx,t in enumerate(hand) if idx not in (i,j,k)]
                        self.find_melds(remaining, current+[cand], results)

    def get_meld_type(self, meld):
        if len(meld)==3:
            if self.is_triplet(meld): return 'handkouutsu'
            if self.is_sequence(meld): return 'handshuntsu'
        if len(meld)==2: return 'handtoitsu'
        return 'unknowntype'

    def decompose_hand(self, hand):
        normalized = sorted([self.normalize_tile(t) for t in hand], key=tile_sort_key)
        results = []
        self.find_melds(normalized, [], results)
        seen = set()
        formatted = []
        for melds in results:
            key = json_key(melds)
            if key not in seen:
                seen.add(key)
                formatted.append([{'type':self.get_meld_type(m),'tiles':m} for m in melds])
        return formatted

def json_key(melds):
    return ','.join(','.join(sorted(m)) for m in sorted(melds, key=lambda m: (m[0],m[1]) if m else ('',)))

# ==================== YakuList (Xpilot yakucalculation.js) ====================
class YakuList:
    def checkTanyao(self, hand):
        return all(t not in TERMINALS_HONOURS_STR for m in hand for t in m['tiles'])

    def _check_wind(self, hand, wind_str):
        target = WIND_MAP.get(wind_str)
        return any(m['tiles'][0]==target and len(m['tiles'])>=3 for m in hand)

    def checkRoundEast(self, hand, rw): return rw=='east' and self._check_wind(hand,'east')
    def checkRoundSouth(self, hand, rw): return rw=='south' and self._check_wind(hand,'south')
    def checkRoundWest(self, hand, rw): return rw=='west' and self._check_wind(hand,'west')
    def checkSeatEast(self, hand, sw): return sw=='east' and self._check_wind(hand,'east')
    def checkSeatSouth(self, hand, sw): return sw=='south' and self._check_wind(hand,'south')
    def checkSeatWest(self, hand, sw): return sw=='west' and self._check_wind(hand,'west')
    def checkSeatNorth(self, hand, sw): return sw=='north' and self._check_wind(hand,'north')

    def _check_dragon(self, hand, d):
        return any(m['tiles'][0]==d and len(m['tiles'])>=3 for m in hand)
    def checkHaku(self, hand): return self._check_dragon(hand,'5z')
    def checkHatsu(self, hand): return self._check_dragon(hand,'6z')
    def checkChun(self, hand): return self._check_dragon(hand,'7z')

    def checkMenzenTsumo(self, isMenzen, isTsumo): return isMenzen and isTsumo

    def checkPinfu(self, hand, waitType, rw, sw):
        wind_map = {'east':'1z','south':'2z','west':'3z','north':'4z'}
        all_valid = all(m['type'] in ('handshuntsu','handtoitsu') for m in hand)
        valid_wait = waitType == 'ryanmen-machi'
        valid_pair = False
        for m in hand:
            if m['type']=='handtoitsu':
                yaku_meld = {wind_map[rw], wind_map[sw], '5z','6z','7z'}
                valid_pair = m['tiles'][0] not in yaku_meld
        return all_valid and valid_wait and valid_pair

    def checkIipeikou(self, hand, isMenzen):
        if not isMenzen: return False
        seqs = {}
        for m in hand:
            if m['type']=='handshuntsu':
                k = ''.join(sorted(m['tiles']))
                seqs[k] = seqs.get(k,0)+1
        return any(c>=2 for c in seqs.values())

    def checkToitoi(self, hand):
        return all(m['type'] in ('handkouutsu','pon','ankan','minkan','handtoitsu') for m in hand)

    def checkSanankou(self, hand, waitType, isTsumo):
        ankou = sum(1 for m in hand if m['type'] in ('handkouutsu','ankan'))
        if waitType=='shanpon' and not isTsumo: ankou-=1
        return ankou==3

    def checkSankantsu(self, hand):
        return sum(1 for m in hand if m['type'] in ('minkan','ankan'))==3

    def checkSanshokuDoko(self, hand):
        tm = {}
        for m in hand:
            if m['type'] in ('handkouutsu','pon','ankan','minkan'):
                s = m['tiles'][0]
                if s[-1] in ('m','p','s'):
                    n = s[0]
                    if n not in tm: tm[n]=set()
                    tm[n].add(s[-1])
        return any(len(suits)==3 for suits in tm.values())

    def checkHonrouto(self, hand):
        all_valid = all(t in TERMINALS_HONOURS_STR for m in hand for t in m['tiles'])
        types_ok = all(m['type'] in ('handkouutsu','handtoitsu','pon','minkan','ankan') for m in hand)
        has_honor = any(t in HONOR_STR for m in hand for t in m['tiles'])
        has_terminal = any(t in TERMINAL_STR for m in hand for t in m['tiles'])
        return all_valid and types_ok and has_honor and has_terminal

    def checkShouSangen(self, hand):
        dc = {'5z':0,'6z':0,'7z':0}
        for m in hand:
            if m['type'] in ('handkouutsu','pon','minkan','ankan'):
                if m['tiles'][0] in dc: dc[m['tiles'][0]]+=1
            elif m['type']=='handtoitsu' and m['tiles'][0] in dc: dc[m['tiles'][0]]+=0.5
        vals = list(dc.values())
        return sum(1 for v in vals if v>=1)==2 and 0.5 in vals

    def checkSanshokuDoujun(self, hand):
        sm = {}
        for m in hand:
            if m['type'] in ('handshuntsu','chii'):
                ns = ''.join(sorted(t[0] for t in m['tiles']))
                s = m['tiles'][0][-1]
                if s in ('m','p','s'):
                    if ns not in sm: sm[ns]=set()
                    sm[ns].add(s)
        return any(len(suits)==3 for suits in sm.values())

    def checkIttsu(self, hand):
        seqs = {'m':[],'p':[],'s':[]}
        for m in hand:
            if m['type'] in ('handshuntsu','chii'):
                s = m['tiles'][0][-1]
                if s in seqs: seqs[s].append(m['tiles'])
        def check_color(melds):
            needed = [['1','2','3'],['4','5','6'],['7','8','9']]
            used = set()
            for g in needed:
                found = False
                for idx,meld in enumerate(melds):
                    if idx in used: continue
                    suit = meld[0][-1]
                    if all(n+suit in meld for n in g):
                        used.add(idx); found=True; break
                if not found: return False
            return True
        return any(check_color(v) for v in seqs.values())

    def checkChanta(self, hand):
        has_seq = False
        for m in hand:
            if not any(t in TERMINALS_HONOURS_STR for t in m['tiles']): return False
            if m['type'] in ('handshuntsu','chii'): has_seq=True
        has_honor = any(t in HONOR_STR for m in hand for t in m['tiles'])
        return has_seq and has_honor

    def checkHonitsu(self, hand):
        suits = set(); has_honor = False
        for m in hand:
            for t in m['tiles']:
                s = t[-1]; suits.add(s)
                if s=='z': has_honor=True
        return len(suits)==2 and 'z' in suits and has_honor

    def checkJunchan(self, hand):
        has_seq=False
        for m in hand:
            if not any(t in TERMINAL_STR for t in m['tiles']): return False
            if m['type'] in ('handshuntsu','chii'): has_seq=True
        return has_seq

    def checkRyanpeikou(self, hand, isMenzen):
        if not isMenzen: return False
        melds = [m for m in hand if m['type']=='handshuntsu']
        pair = any(m['type']=='handtoitsu' for m in hand)
        if len(melds)!=4 or not pair: return False
        counts = {}
        for m in melds:
            k = ''.join(sorted(m['tiles']))
            counts[k] = counts.get(k,0)+1
        return sum(1 for c in counts.values() if c==2)==2

    def checkChinitsu(self, hand):
        suits = set()
        for m in hand:
            for t in m['tiles']:
                if t[-1]=='z': return False
                suits.add(t[-1])
        return len(suits)==1

    def checkDaisangen(self, hand):
        ds = ['5z5z5z','6z6z6z','7z7z7z','5z5z5z5z','6z6z6z6z','7z7z7z7z']
        return sum(1 for m in hand if ''.join(m['tiles']) in ds)==3

    def checkShousuushii(self, hand):
        winds = ['1z','2z','3z','4z']
        wc=0; hw=None
        for m in hand:
            if m['type'] in ('handkouutsu','pon','minkan','ankan'):
                if m['tiles'][0] in winds: wc+=1
            if m['type']=='handtoitsu': hw=m['tiles'][0]
        return wc==3 and hw in winds

    def checkDaisushi(self, hand):
        winds = ['1z','2z','3z','4z']
        return sum(1 for m in hand if m['type'] in ('handkouutsu','pon','minkan','ankan') and m['tiles'][0] in winds)==4

    def checkTsuuiisou(self, hand):
        return all(t in HONOR_STR for m in hand for t in m['tiles'])

    def checkRyuuiisou(self, hand):
        green = {'2s','3s','4s','6s','8s','6z'}
        return all(t in green for m in hand for t in m['tiles'])

    def checkChinroutou(self, hand):
        return all(t in TERMINAL_STR for m in hand for t in m['tiles'])

    def checkSuuankou(self, hand, isMenzen, isTsumo, waitType):
        if not isMenzen or not isTsumo or waitType!='shanpon': return False
        return sum(1 for m in hand if m['type'] in ('handkouutsu','ankan'))==4

    def checkSuuankouTanki(self, hand, isMenzen, waitType):
        if not isMenzen or waitType!='tanki-machi': return False
        return sum(1 for m in hand if m['type'] in ('handkouutsu','ankan'))==4

    def _check_chuuren(self, hand, isMenzen, wmi, wti, pure):
        if not isMenzen: return False
        suits = set()
        for m in hand:
            for t in m['tiles']:
                if t[-1]=='z': return False
                suits.add(t[-1])
        if len(suits)!=1: return False
        all_tiles=[]; all_excl=[]
        for idx,m in enumerate(hand):
            all_tiles.extend(m['tiles'])
            if idx==wmi:
                all_excl.extend(t for i,t in enumerate(m['tiles']) if i!=wti)
            else: all_excl.extend(m['tiles'])
        digits = [str(int(t[0])) for t in all_tiles] if all_tiles else []
        digit_count = {}
        for d in digits:
            digit_count[d] = digit_count.get(d,0)+1
        valid = digit_count.get('1',0)>=3 and digit_count.get('9',0)>=3
        for i in range(2,9):
            valid = valid and digit_count.get(str(i),0)>=1
        digits_excl = [str(int(t[0])) for t in all_excl] if all_excl else []
        dc_excl = {}
        for d in digits_excl:
            dc_excl[d] = dc_excl.get(d,0)+1
        valid_excl = dc_excl.get('1',0)==3 and dc_excl.get('9',0)==3
        for i in range(2,9):
            valid_excl = valid_excl and dc_excl.get(str(i),0)==1
        wt_digit = int(hand[wmi]['tiles'][wti][0])
        wt_is_edge = wt_digit in (1,9)
        if pure: return valid and valid_excl and wt_is_edge
        else: return valid and not (valid_excl and wt_is_edge)

    def checkChuurenPoutou(self, hand, isMenzen, wmi, wti):
        return self._check_chuuren(hand, isMenzen, wmi, wti, False)

    def checkJunseiChuurenPoutou(self, hand, isMenzen, wmi, wti):
        return self._check_chuuren(hand, isMenzen, wmi, wti, True)

    def checkSuukantsu(self, hand):
        return sum(1 for m in hand if m['type'] in ('minkan','ankan'))==4

# ==================== 符计算 (Xpilot HandPointCalculation.vue) ====================
def calculate_fu(hand_struct):
    melds = hand_struct['melds']
    is_tsumo = hand_struct['isTsumo']
    is_menzen = hand_struct['isMenzen']
    rw = hand_struct['roundWind']
    sw = hand_struct['seatWind']
    wait_type = hand_struct['waitType']
    wmi = hand_struct['winningMeldIndex']
    fu = 20
    is_pair_add_fu = False
    for i, m in enumerate(melds):
        if m['type']=='handshuntsu' or m['type']=='chii':
            pass
        elif m['type']=='handkouutsu':
            is_th = any(t in TERMINALS_HONOURS_STR for t in m['tiles'])
            if is_tsumo:
                fu += 8 if is_th else 4
            else:
                if wmi==i: fu += 4 if is_th else 2
                else: fu += 8 if is_th else 4
        elif m['type']=='handtoitsu':
            wt = m['tiles'][0]
            rw_t = WIND_MAP.get(rw)
            sw_t = WIND_MAP.get(sw)
            if rw_t==wt and sw_t!=wt: fu+=2; is_pair_add_fu=True
            elif rw_t!=wt and sw_t==wt: fu+=2; is_pair_add_fu=True
            elif rw_t==wt and sw_t==wt: fu+=4; is_pair_add_fu=True
            elif wt in DRAGON_STR: fu+=2; is_pair_add_fu=True
        elif m['type']=='pon' and len(m['tiles'])==3:
            is_th = any(t in TERMINALS_HONOURS_STR for t in m['tiles'])
            fu += 4 if is_th else 2
        elif m['type']=='minkan' and len(m['tiles'])==4:
            is_th = any(t in TERMINALS_HONOURS_STR for t in m['tiles'])
            fu += 16 if is_th else 8
        elif m['type']=='ankan' and len(m['tiles'])==4:
            is_th = any(t in TERMINALS_HONOURS_STR for t in m['tiles'])
            fu += 32 if is_th else 16
    if is_menzen and not is_tsumo: fu += 10
    if is_tsumo: fu += 2
    if wait_type in ('tanki-machi','penchan-machi','kanchan-machi'): fu += 2
    is_pinfu_tsumo = False
    is_chow_20 = False
    if (is_menzen and is_tsumo and
        all(m['type'] in ('handshuntsu','handtoitsu') for m in melds) and
        wait_type=='ryanmen-machi' and not is_pair_add_fu):
        is_pinfu_tsumo=True; fu=20
    if (not is_menzen and not is_tsumo and
        all(m['type'] in ('handshuntsu','handtoitsu','chii') for m in melds) and
        any(m['type']=='chii' for m in melds) and
        wait_type=='ryanmen-machi' and not is_pair_add_fu):
        is_chow_20=True; fu=30
    return {'fuNotCeil':fu, 'fu':math.ceil(fu/10)*10, 'isPinfuTsumo':is_pinfu_tsumo, 'isChowTwentyFu':is_chow_20}

# ==================== 点数计算 (Xpilot HandPointCalculation.vue) ====================
def _ceil100(x): return math.ceil(x/100)*100

def calculate_points_xpilot(is_dealer, is_tsumo, han, fu):
    if han>=13: bp=8000
    elif han>=11: bp=6000
    elif han>=8: bp=4000
    elif han>=6: bp=3000
    elif han>=5: bp=2000
    else:
        t = fu*(2**(han+2))
        bp = 2000 if t>=2000 else t
    if is_dealer:
        if is_tsumo: return {'tsumo':_ceil100(bp*2),'ron':None}
        else: return {'tsumo':None,'ron':_ceil100(bp*6)}
    else:
        if is_tsumo: return {'tsumo':{'dealer':_ceil100(bp*2),'nonDealer':_ceil100(bp)},'ron':None}
        else: return {'tsumo':None,'ron':_ceil100(bp*4)}

def calculate_yakuman_points(is_dealer, is_tsumo, ym):
    if is_dealer:
        if is_tsumo: return {'tsumo':16000*ym,'ron':None}
        else: return {'tsumo':None,'ron':48000*ym}
    else:
        if is_tsumo: return {'tsumo':{'dealer':16000*ym,'nonDealer':8000*ym},'ron':None}
        else: return {'tsumo':None,'ron':32000*ym}

def base_name_for_han(han, ym=0):
    if ym>0: return f'役満×{ym}'
    if han>=13: return '累積役満'
    if han>=11: return '三倍満'
    if han>=8: return '倍満'
    if han>=6: return '跳満'
    if han>=5: return '満貫'
    return f'{han}飜'

# ==================== 待ち判定 (Xpilot HandPointCalculation.vue) ====================
def determine_wait_type_xpilot(all_melds, wmi, winning_tile_str):
    if wmi<0 or wmi>=len(all_melds): return 'tanki-machi'
    m = all_melds[wmi]
    wt = normalize_tile_str(winning_tile_str)
    if m['type']=='handkouutsu': return 'shanpon'
    if m['type']=='handtoitsu': return 'tanki-machi'
    if m['type']=='handshuntsu':
        nums = sorted(int(normalize_tile_str(t)[0]) for t in m['tiles'])
        wn = int(wt[0])
        if wn==nums[1]: return 'kanchan-machi'
        elif wn==nums[0]:
            return 'penchan-machi' if nums[0]==7 else 'ryanmen-machi'
        else:
            return 'penchan-machi' if nums[0]==1 else 'ryanmen-machi'
    return 'ryanmen-machi'

WAIT_SHORT = {'ryanmen-machi':'ryanmen','kanchan-machi':'kanchan','penchan-machi':'penchan',
              'tanki-machi':'tanki','shanpon':'shanpon'}

# ==================== 和牌分析 (Xpilot HandPointCalculation.vue 流程) ====================
def analyze_hand(hand_text, options=None):
    if options is None: options={}
    try: hand = parse_hand_input(hand_text)
    except ValueError as e: return {'success':False,'error':str(e)}
    wt = hand['winning_tile']
    at = get_all_tiles(hand)
    result = {'success':True,'tiles':sorted(at),'tiles_formatted':format_tiles(at),
              'tiles_pretty':format_tiles_pretty(at),
              'winning_tile':wt,'winning_tile_name':tile_name(wt),'winning_tile_cn':tile_cn(wt),
              'melds':hand['melds'],'is_win':False}
    # 转换为字符串格式
    concealed_str = [idx_to_str(t) for t in hand['concealed']]
    wt_str = idx_to_str(wt)
    # 副露 → Xpilot 格式
    open_melds = []
    for m in hand['melds']:
        ts = idx_to_str(m['tile'])
        if m['type']=='triplet':
            open_melds.append({'type':'pon' if m['open'] else 'handkouutsu','tiles':[ts]*3})
        elif m['type']=='sequence':
            tiles_s = [idx_to_str(m['tile']),idx_to_str(m['tile']+1),idx_to_str(m['tile']+2)]
            open_melds.append({'type':'chii' if m['open'] else 'handshuntsu','tiles':tiles_s})
        elif m['type']=='quad':
            open_melds.append({'type':'minkan' if m['open'] else 'ankan','tiles':[ts]*4})
    is_menzen = len(open_melds)==0 or all(m['type'] in ('handkouutsu','handshuntsu','ankan') for m in open_melds)
    rw = wind_idx_to_str(options.get('round_wind',27))
    sw = wind_idx_to_str(options.get('seat_wind',27))
    is_tsumo = options.get('is_tsumo',False)
    is_dealer = options.get('is_dealer',False)
    is_riichi = options.get('is_riichi',False)
    # 七対子判定
    chiitoi = (not hand['melds'] and len(hand['concealed'])==14 and
               sum(1 for i in range(34) if hand['concealed'].count(i)==2)==7)
    # 国士判定
    kokushi = _check_kokushi_str(concealed_str, wt_str) if not hand['melds'] and len(hand['concealed'])==14 else None
    # HandDivider 分解 (七对子也尝试标准分解，取最优)
    # 有副露时只分解 concealed 部分 (11张 = 3面子+1雀头)
    decompositions = []
    if kokushi is None:
        divider = HandDivider()
        try: decompositions = divider.decompose_hand(concealed_str)
        except: decompositions = []
    nq = sum(1 for m in hand['melds'] if m['type']=='quad')
    total = len(hand['concealed']) + sum(3 if m['type']!='quad' else 4 for m in hand['melds'])
    expected = 14 + nq
    if total != expected:
        return {'success':False,'error':f'手牌{total}张, 和牌需{expected}张'}
    if not chiitoi and not kokushi and not decompositions:
        return {'success':False,'error':'无法分解为和牌形'}
    result['is_win']=True
    yl_checker = YakuList()
    # 宝牌
    dora_inds = options.get('dora_indicators',[])
    all_tile_strs = [idx_to_str(t) for t in at]
    if dora_inds:
        dora_tiles_str = set(normalize_tile_str(idx_to_str(i)) for i in dora_inds)
        dora_count = sum(1 for t in all_tile_strs if normalize_tile_str(t) in dora_tiles_str)
    else:
        dora_count = options.get('dora_count', 0)
    results = []
    # 七対子 (特殊处理: 不走 YakuList, 只检查七对子相关役)
    if chiitoi:
        all_strs = [normalize_tile_str(s) for s in concealed_str]
        yaku = []; han = 0; ym = 0
        han += 2; yaku.append(('七対子',2,False))
        if is_riichi: han+=1; yaku.append(('立直',1,False))
        if is_tsumo: han+=1; yaku.append(('門前清自摸和',1,False))
        if all(t not in TERMINALS_HONOURS_STR for t in all_strs): han+=1; yaku.append(('断幺九',1,False))
        suits = set(t[-1] for t in all_strs)
        if len(suits-{3})==1 and 3 in suits: han+=3; yaku.append(('混一色',3,False))
        elif len(suits)==1 and 3 not in suits: han+=6; yaku.append(('清一色',6,False))
        if dora_count>0: han+=dora_count; yaku.append(('宝牌',dora_count,False))
        if options.get('is_tenhou'): ym+=1; yaku.append(('天和',1,True))
        if options.get('is_chiihou'): ym+=1; yaku.append(('地和',1,True))
        fu = 25
        if ym>0:
            pts = calculate_yakuman_points(is_dealer,is_tsumo,ym)
        else:
            pts = calculate_points_xpilot(is_dealer,is_tsumo,han,fu)
        results.append({'yaku':yaku,'han':han,'fu':fu,'yakuman':ym,'points':pts,
                        'wait':'tanki','decomp':'七対子'})
    # 国士 (特殊处理: 不走 YakuList)
    if kokushi:
        yaku=[]; han=0; ym=0
        if kokushi=='13wait':
            yaku.append(('国士無双十三面',2,True)); ym+=2
        else:
            yaku.append(('国士無双',1,True)); ym+=1
        if options.get('is_tenhou'): ym+=1; yaku.append(('天和',1,True))
        if options.get('is_chiihou'): ym+=1; yaku.append(('地和',1,True))
        pts = calculate_yakuman_points(is_dealer,is_tsumo,ym)
        results.append({'yaku':yaku,'han':0,'fu':30,'yakuman':ym,'points':pts,
                        'wait':'13面' if kokushi=='13wait' else 'normal',
                        'decomp':'国士無双'})
    # 标准分解 (七对子也参与比较)
    if kokushi is None:
        for decomp in decompositions:
            all_melds = decomp + open_melds
            # 排序: hand sets first, then open
            type_order = {'handshuntsu':1,'handkouutsu':2,'handtoitsu':3,'chii':4,'pon':5,'minkan':6,'ankan':7}
            all_melds.sort(key=lambda m: type_order.get(m['type'],99))
            # 找winning meld
            wt_norm = normalize_tile_str(wt_str)
            wmi=-1; wti=-1
            for mi,m in enumerate(all_melds):
                if m['type']=='handtoitsu':
                    if normalize_tile_str(m['tiles'][0])==wt_norm: wmi=mi; wti=1; break
                elif m['type']=='handkouutsu':
                    if normalize_tile_str(m['tiles'][0])==wt_norm: wmi=mi; wti=2; break
                elif m['type']=='handshuntsu':
                    sorted_tiles=sorted(m['tiles'],key=lambda t:int(normalize_tile_str(t)[0]))
                    for ti,t in enumerate(sorted_tiles):
                        if normalize_tile_str(t)==wt_norm: wmi=mi; wti=ti; break
                    if wmi==mi: break
            wait_type = determine_wait_type_xpilot(all_melds, wmi, wt_str)
            hand_struct = {
                'melds':all_melds,'winningMeldIndex':wmi,'winningTileIndex':wti,
                'waitType':wait_type,'roundWind':rw,'seatWind':sw,
                'isDealer':is_dealer,'isMenzen':is_menzen,'isTsumo':is_tsumo,'isRiichi':is_riichi,
            }
            yaku, han, ym = _count_yaku(hand_struct, yl_checker, options, dora_count)
            if ym==0 and han==0: continue
            fu_r = calculate_fu(hand_struct)
            fu = fu_r['fu']
            if ym>0:
                pts = calculate_yakuman_points(is_dealer,is_tsumo,ym)
            else:
                pts = calculate_points_xpilot(is_dealer,is_tsumo,han,fu)
            wait_short = WAIT_SHORT.get(wait_type, wait_type)
            decomp_str = _fmt_decomp_xpilot(all_melds)
            results.append({'yaku':yaku,'han':han,'fu':fu,'yakuman':ym,'points':pts,
                            'wait':wait_short,'decomp':decomp_str,'hand_struct':hand_struct})
    if not results:
        result['error']='和牌形成立, 但无役'; return result
    # 取最大点
    def point_total(r):
        p=r['points']
        if p.get('tsumo') is not None:
            if isinstance(p['tsumo'],dict): return p['tsumo']['dealer']+p['tsumo']['nonDealer']*2
            return p['tsumo']*3
        return p.get('ron',0)
    best = max(results, key=lambda r: (point_total(r), r['han'], r['fu']))
    result.update({k:v for k,v in best.items() if k!='hand_struct'})
    # 格式化points
    pts = best['points']
    total = point_total(best)
    if pts.get('tsumo') is not None:
        if isinstance(pts['tsumo'],dict):
            detail = f"闲家自摸 庄家{pts['tsumo']['dealer']}点/闲家{pts['tsumo']['nonDealer']}点"
        else:
            detail = f"庄家自摸 每家{pts['tsumo']}点"
    else:
        detail = f"{'庄家' if is_dealer else '闲家'}荣和 {pts['ron']}点"
    bn = base_name_for_han(best['han'], best['yakuman'])
    bp = 0
    if best['yakuman']>0: bp = 8000*best['yakuman']
    elif best['han']>=5: bp = 2000
    else: bp = min(best['fu']*(2**(best['han']+2)),2000)
    result['points'] = {'total':total,'detail':detail,'base_name':bn,'base':bp}
    return result

def _check_kokushi_str(concealed_str, wt_str):
    yao = {'1m','9m','1p','9p','1s','9s','1z','2z','3z','4z','5z','6z','7z'}
    normalized = [normalize_tile_str(t) for t in concealed_str]
    if any(t not in yao for t in normalized): return None
    counts = {}
    for t in normalized: counts[t]=counts.get(t,0)+1
    for kt in yao:
        if counts.get(kt,0)==0: return None
    for kt in yao:
        if counts.get(kt,0)==2:
            return '13wait' if normalize_tile_str(wt_str)==kt else 'normal'
    return None

def _count_yaku(hs, yl, opts, dora_count):
    """返回 (yaku_list, han, yakuman_count)
    yaku_list: [(name, han, is_yakuman), ...]"""
    melds = hs['melds']
    is_menzen = hs['isMenzen']
    is_tsumo = hs['isTsumo']
    rw = hs['roundWind']
    sw = hs['seatWind']
    wait = hs['waitType']
    wmi = hs['winningMeldIndex']
    wti = hs['winningTileIndex']
    is_riichi = hs.get('isRiichi',False)
    yaku = []
    ym = 0
    # 役满判定
    if yl.checkDaisangen(melds): ym+=1; yaku.append(('大三元',1,True))
    if yl.checkShousuushii(melds): ym+=1; yaku.append(('小四喜',1,True))
    if yl.checkDaisushi(melds): ym+=2; yaku.append(('大四喜',2,True))
    if yl.checkTsuuiisou(melds): ym+=1; yaku.append(('字一色',1,True))
    if yl.checkRyuuiisou(melds): ym+=1; yaku.append(('緑一色',1,True))
    if yl.checkChinroutou(melds): ym+=1; yaku.append(('清老頭',1,True))
    if yl.checkSuuankou(melds,is_menzen,is_tsumo,wait): ym+=1; yaku.append(('四暗刻',1,True))
    if yl.checkSuuankouTanki(melds,is_menzen,wait): ym+=2; yaku.append(('四暗刻単騎',2,True))
    if yl.checkChuurenPoutou(melds,is_menzen,wmi,wti): ym+=1; yaku.append(('九蓮宝燈',1,True))
    if yl.checkJunseiChuurenPoutou(melds,is_menzen,wmi,wti): ym+=2; yaku.append(('純正九蓮宝燈',2,True))
    if yl.checkSuukantsu(melds): ym+=1; yaku.append(('四槓子',1,True))
    if opts.get('is_tenhou'): ym+=1; yaku.append(('天和',1,True))
    if opts.get('is_chiihou'): ym+=1; yaku.append(('地和',1,True))
    if ym>0: return yaku, 0, ym
    # 通常役
    han = 0
    if is_riichi and is_menzen: han+=1; yaku.append(('立直',1,False))
    if opts.get('is_ippatsu') and is_riichi and is_menzen: han+=1; yaku.append(('一発',1,False))
    if is_tsumo and is_menzen: han+=1; yaku.append(('門前清自摸和',1,False))
    if yl.checkPinfu(melds,wait,rw,sw): han+=1; yaku.append(('平和',1,False))
    if yl.checkTanyao(melds): han+=1; yaku.append(('断幺九',1,False))
    if yl.checkIipeikou(melds,is_menzen) and not yl.checkRyanpeikou(melds,is_menzen): han+=1; yaku.append(('一杯口',1,False))
    # 役牌
    if yl.checkRoundEast(melds,rw): han+=1; yaku.append(('場風東',1,False))
    if yl.checkRoundSouth(melds,rw): han+=1; yaku.append(('場風南',1,False))
    if yl.checkRoundWest(melds,rw): han+=1; yaku.append(('場風西',1,False))
    if yl.checkSeatEast(melds,sw): han+=1; yaku.append(('自風東',1,False))
    if yl.checkSeatSouth(melds,sw): han+=1; yaku.append(('自風南',1,False))
    if yl.checkSeatWest(melds,sw): han+=1; yaku.append(('自風西',1,False))
    if yl.checkSeatNorth(melds,sw): han+=1; yaku.append(('自風北',1,False))
    if yl.checkHaku(melds): han+=1; yaku.append(('白',1,False))
    if yl.checkHatsu(melds): han+=1; yaku.append(('發',1,False))
    if yl.checkChun(melds): han+=1; yaku.append(('中',1,False))
    if yl.checkToitoi(melds): han+=2; yaku.append(('対々和',2,False))
    if yl.checkSanankou(melds,wait,is_tsumo): han+=2; yaku.append(('三暗刻',2,False))
    if yl.checkSankantsu(melds): han+=2; yaku.append(('三槓子',2,False))
    if yl.checkSanshokuDoko(melds): han+=2; yaku.append(('三色同刻',2,False))
    if yl.checkHonrouto(melds): han+=2; yaku.append(('混老頭',2,False))
    if yl.checkShouSangen(melds): han+=2; yaku.append(('小三元',2,False))
    if yl.checkSanshokuDoujun(melds):
        han+=2 if is_menzen else 1; yaku.append(('三色同順',2 if is_menzen else 1,False))
    if yl.checkIttsu(melds):
        han+=2 if is_menzen else 1; yaku.append(('一気通貫',2 if is_menzen else 1,False))
    if yl.checkChanta(melds):
        han+=2 if is_menzen else 1; yaku.append(('混全帯幺九',2 if is_menzen else 1,False))
    if yl.checkHonitsu(melds):
        han+=3 if is_menzen else 2; yaku.append(('混一色',3 if is_menzen else 2,False))
    if yl.checkJunchan(melds):
        han+=3 if is_menzen else 2; yaku.append(('純全帯幺九',3 if is_menzen else 2,False))
    if yl.checkRyanpeikou(melds,is_menzen):
        han+=3; yaku.append(('二杯口',3,False))
    if yl.checkChinitsu(melds):
        han+=6 if is_menzen else 5; yaku.append(('清一色',6 if is_menzen else 5,False))
    # 宝牌
    if dora_count>0: han+=dora_count; yaku.append(('宝牌',dora_count,False))
    # 海底/河底/嶺上/槍槓
    if is_tsumo and opts.get('is_haitei'): han+=1; yaku.append(('海底摸月',1,False))
    if not is_tsumo and opts.get('is_houtei'): han+=1; yaku.append(('河底撈魚',1,False))
    if opts.get('is_rinshan') and is_tsumo: han+=1; yaku.append(('嶺上開花',1,False))
    if opts.get('is_chankan') and not is_tsumo: han+=1; yaku.append(('槍槓',1,False))
    return yaku, han, 0

def _fmt_decomp_xpilot(all_melds):
    parts = []
    for m in all_melds:
        ts = m['tiles']
        if m['type'] in ('handshuntsu','chii'):
            parts.append(''.join(ts))
        elif m['type'] in ('handkouutsu','pon'):
            parts.append(ts[0]*3)
        elif m['type'] in ('minkan','ankan'):
            parts.append(ts[0]*4)
        elif m['type']=='handtoitsu':
            parts.append(f'雀头:{ts[0]}{ts[0]}')
    return ' '.join(parts)

# ==================== 牌理接口 (兼容 main.py) ====================
def shanten_for_hand(tiles):
    n = len(tiles)
    if n==0: return 99,None,[],(99,99,99)
    cc=[0]*34
    for t in tiles: cc[t]+=1
    r=n%3
    if r==1:
        s1,s2,s3 = shanten_counts(cc,n)
        s=min(s1,s2,s3); waits=_ukeire(cc,s,n)
        return s,None,waits,(s1,s2,s3)
    elif r==2:
        best_s=99; best_d=[]
        for t in range(34):
            if cc[t]==0: continue
            cc[t]-=1
            s1,s2,s3=shanten_counts(cc,n-1); s=min(s1,s2,s3)
            cc[t]+=1
            if s<best_s: best_s=s; best_d=[t]
            elif s==best_s: best_d.append(t)
        di=[]
        for dt in best_d:
            cc[dt]-=1; waits=_ukeire(cc,best_s,n-1); cc[dt]+=1
            di.append((dt,waits))
        return best_s,best_d,di,None
    else:
        best_s=99; best_w=[]
        for t in range(34):
            if cc[t]>=4: continue
            cc[t]+=1
            s1,s2,s3=shanten_counts(cc,n+1); s=min(s1,s2,s3)
            if s<best_s: best_s=s; best_w=[t]
            elif s==best_s: best_w.append(t)
            cc[t]-=1
        return best_s+1,None,best_w,(best_s+1,99,99)
