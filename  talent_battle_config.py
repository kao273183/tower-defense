"""
Battle Talent System config for Tower Defense (Roguelike-style)

Usage (in main.py):
    from talent_battle_config import (
        TALENT_POOL, RARITY_WEIGHTS_BY_TIER,
        roll_talent_choices, apply_talent_effect,
        format_talent_text
    )

Typical flow:
    # when a wave is cleared
    choices = roll_talent_choices(wave, picked_ids=state['picked_talents'])
    # show choices to player and obtain chosen `tid`
    apply_talent_effect(tid, state)

The `state` object expected by apply_talent_effect is a dict including (suggested):
    state = {
        'picked_talents': set(),
        'tower_mod': {  # multiplicative or additive modifiers applied at runtime
            'global_rof_mul': 1.0,
            'global_atk_mul': 1.0,
            'element_mod': {  # per element overrides
                # 'fire': {'atk_mul':1.0, 'slow_ratio_bonus':0.0, ...}
            },
        },
        'economy': {
            'kill_reward_bonus_flat': 0,    # +$ per kill
            'coin_card_bonus': 0,          # +$ for coin cards
            'lumber_heal_bonus_ratio': 0,  # +% heal bonus from sawmill
            'magic_stone_drop_add': 0.0,   # +drop rate
        },
        'skills': {
            'cooldown_mul': 1.0,
            'cost_reduction': 0,            # magic stone cost -N
            'combo_counter': 0,
        },
        'set_bonuses': {
            # derived bonuses (e.g. same-element count >= 3)
            'same_elem_attack_mul': {},
        },
        # you can attach your live systems here, e.g. references to PRICES, ELEMENT_EFFECTS, etc.
        'refs': {
            'PRICES': None,                 # attach the dict from main
            'ELEMENT_EFFECTS': None,        # attach the dict from main
        }
    }

Integrators can choose to translate these modifiers into your existing systems
(e.g. when computing tower stats, multiply attack by state['tower_mod']['global_atk_mul']).

"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple, Set

# -----------------------------
# Rarity setup
# -----------------------------
RARITY = ('R', 'SR', 'SSR')

# Dynamic rarity weights by wave tiers (feel free to tweak)
# keys are upper-bounds (<= key) for wave indexing; last item is fallback
RARITY_WEIGHTS_BY_TIER: List[Tuple[int, Dict[str, int]]] = [
    (10,  {'R': 80, 'SR': 19, 'SSR': 1}),
    (20,  {'R': 65, 'SR': 30, 'SSR': 5}),
    (30,  {'R': 55, 'SR': 35, 'SSR': 10}),
    (999, {'R': 45, 'SR': 40, 'SSR': 15}),
]

# -----------------------------
# Talent pool
# Each entry: id, name, desc, rarity, tags, apply()
# -----------------------------

TALENT_POOL: Dict[str, Dict] = {}

def _reg(tid: str, name: str, desc: str, rarity: str, tags: List[str], effect_key: str, payload: dict):
    TALENT_POOL[tid] = {
        'id': tid,
        'name': name,
        'desc': desc,
        'rarity': rarity,
        'tags': tags,
        'effect_key': effect_key,  # internal routing key
        'payload': payload,
    }

# --- Tower-focused (elements & generic) ---
_reg('fire_boost', '火焰爆燃', '火塔傷害 +25%，攻速 -10%', 'R', ['tower','fire'],
     'tower_element_mul', {'element': 'fire', 'atk_mul': 1.25, 'rof_mul': 0.90})
_reg('water_extend', '寒氣延伸', '水/冰塔緩速範圍 +1', 'R', ['tower','water'],
     'elemental_field_bonus', {'element': 'water', 'range_add': 1})
_reg('lightning_bounce', '雷電共鳴', '雷塔有 15% 機率彈跳至另一敵人', 'SR', ['tower','lightning'],
     'lightning_chain', {'chain_chance': 0.15, 'extra_targets': 1})
_reg('wind_rush', '狂風之力', '風塔攻速 +25%，射程 -1', 'R', ['tower','wind'],
     'tower_element_mul', {'element': 'wind', 'rof_mul': 1.25, 'range_add': -1})
_reg('poison_cloud', '毒霧擴散', '毒塔範圍 +2，持續延長 50%', 'SR', ['tower','poison'],
     'poison_extend', {'range_add': 2, 'duration_mul': 1.5})
_reg('earth_bulwark', '堅土壁壘', '土塔生命 +50%，首次承受爆炸免疫', 'SR', ['tower','earth'],
     'earth_shield', {'hp_mul': 1.5, 'bomb_immunity_once': True})
_reg('global_elite', '精銳鍛造', '所有塔攻擊 +10%', 'SR', ['tower','global'],
     'global_atk_mul', {'atk_mul': 1.10})

# --- Economy ---
_reg('hardworker', '勤勞之心', '每 10 擊殺獲得 +1 金幣', 'R', ['eco'],
     'kill_gold_flat', {'per_kills': 10, 'gold': 1})
_reg('greed', '貪婪本能', '金幣卡收益 +1', 'R', ['eco','card'],
     'coin_card_bonus', {'bonus': 1})
_reg('sawmill_master', '伐木增效', '伐木場修復主堡時額外 +20% HP', 'R', ['eco','building'],
     'sawmill_heal_bonus', {'ratio': 0.20})
_reg('arcane_quarry', '礦場繁榮', '擊殺額外 +5% 機率掉魔法石', 'SR', ['eco'],
     'magic_stone_drop', {'add_ratio': 0.05})

# --- Skills ---
_reg('skill_haste', '技能回流', '技能冷卻 -20%', 'R', ['skill'],
     'skill_cd_mul', {'mul': 0.80})
_reg('arcane_combo', '魔導加速', '每使用 3 張技能卡，全塔攻速 +20% 持續 5 秒', 'SR', ['skill'],
     'skill_combo_buff', {'need': 3, 'rof_mul': 1.20, 'sec': 5.0})
_reg('mana_focus', '奧術專注', '技能卡魔石消耗 -1', 'SR', ['skill'],
     'skill_cost_reduce', {'minus': 1})
_reg('thunder_reflect', '雷鳴反射', '雷電技能追加一次連鎖', 'SR', ['skill','lightning'],
     'skill_lightning_echo', {'extra_bounce': 1})

# --- Tactical ---
_reg('mulligan', '戰略撤退', '下一波開始前可免費重抽整手牌一次', 'R', ['tactic','card'],
     'free_reroll_once', {'granted': True})
_reg('panic_wall', '緊急防禦', '主堡 HP < 50% 時，全塔防禦 +30%', 'SR', ['tactic'],
     'lowhp_defense_aura', {'hp_ratio': 0.5, 'def_mul': 1.30})
_reg('fusion_plus', '融合強化', '元素融合後，結果元素立即 +1 級', 'SR', ['tactic','fusion'],
     'fusion_bonus_level', {'add_level': 1})
_reg('synergy', '元素暴走', '同屬性塔數 ≥ 3：該屬性塔攻擊 +15%', 'SR', ['tactic','set'],
     'same_element_set', {'need': 3, 'atk_mul': 1.15})

# --- High-tier (SSR) ---
_reg('storm_eye', '元素風暴眼', '所有塔獲得隨機元素 10 秒', 'SSR', ['ultimate'],
     'global_random_element', {'sec': 10.0})
_reg('time_stop', '時間裂隙', '時間暫停 3 秒、全塔立即攻擊一次', 'SSR', ['ultimate'],
     'time_stop_burst', {'sec': 3.0})
_reg('double_loot', '雙倍掉落', '本波結束金幣與魔法石掉落翻倍', 'SSR', ['ultimate','eco'],
     'double_end_loot', {'enable': True})
_reg('artisan', '工匠之心', '建塔速度 +30%、升級花費 -1（最低 1）', 'SR', ['eco','tower'],
     'build_upgrade_discount', {'build_speed_mul': 1.30, 'upgrade_minus': 1})

# -----------------------------
# Choice rolling
# -----------------------------

def _rarity_weights_for_wave(wave: int) -> Dict[str, int]:
    for ub, weights in RARITY_WEIGHTS_BY_TIER:
        if wave <= ub:
            return weights
    return RARITY_WEIGHTS_BY_TIER[-1][1]


def _sample_rarity(wave: int) -> str:
    weights = _rarity_weights_for_wave(wave)
    pool, w = zip(*weights.items())
    return random.choices(pool, weights=w, k=1)[0]


def roll_talent_choices(wave: int, picked_ids: Set[str] | None = None, k: int = 3) -> List[Dict]:
    """Return k random talent dicts filtered by rarity and not already picked.
    Duplicates by `effect_key` can be optionally filtered if you prefer.
    """
    picked = picked_ids or set()
    # Try up to a few rerolls to avoid repeats
    result: List[Dict] = []
    tried: Set[str] = set()
    attempts = 0
    while len(result) < k and attempts < 50:
        attempts += 1
        r = _sample_rarity(wave)
        candidates = [t for t in TALENT_POOL.values() if t['rarity'] == r and t['id'] not in picked]
        if not candidates:
            # fallback to any not picked
            candidates = [t for t in TALENT_POOL.values() if t['id'] not in picked]
            if not candidates:
                break
        cand = random.choice(candidates)
        if cand['id'] in tried:
            continue
        tried.add(cand['id'])
        result.append(cand)
    return result

# -----------------------------
# Apply effects (mutate `state`)
# -----------------------------

def apply_talent_effect(tid: str, state: Dict) -> None:
    """Mutate the `state` according to the chosen talent.
    The engine (main.py) should read these modifiers during stat calculations
    and in relevant systems (skills, economy, etc.).
    """
    t = TALENT_POOL.get(tid)
    if not t:
        return
    ek = t['effect_key']
    p = t['payload']

    state.setdefault('picked_talents', set()).add(tid)
    tower_mod = state.setdefault('tower_mod', {})
    econ      = state.setdefault('economy', {})
    skills    = state.setdefault('skills', {})
    setsys    = state.setdefault('set_bonuses', {})

    if ek == 'tower_element_mul':
        elem = p.get('element')
        em = tower_mod.setdefault('element_mod', {}).setdefault(elem, {'atk_mul':1.0, 'rof_mul':1.0, 'range_add':0})
        em['atk_mul']  = em.get('atk_mul', 1.0) * p.get('atk_mul', 1.0)
        em['rof_mul']  = em.get('rof_mul', 1.0) * p.get('rof_mul', 1.0)
        em['range_add']= em.get('range_add', 0) + p.get('range_add', 0)

    elif ek == 'elemental_field_bonus':
        elem = p.get('element')
        em = tower_mod.setdefault('element_mod', {}).setdefault(elem, {})
        em['range_add'] = em.get('range_add', 0) + p.get('range_add', 0)

    elif ek == 'lightning_chain':
        lm = tower_mod.setdefault('element_mod', {}).setdefault('lightning', {})
        lm['chain_chance'] = lm.get('chain_chance', 0.0) + p.get('chain_chance', 0.0)
        lm['extra_targets']= lm.get('extra_targets', 0) + p.get('extra_targets', 0)

    elif ek == 'poison_extend':
        pm = tower_mod.setdefault('element_mod', {}).setdefault('poison', {})
        pm['range_add'] = pm.get('range_add', 0) + p.get('range_add', 0)
        pm['duration_mul'] = pm.get('duration_mul', 1.0) * p.get('duration_mul', 1.0)

    elif ek == 'earth_shield':
        em = tower_mod.setdefault('element_mod', {}).setdefault('earth', {})
        em['hp_mul'] = em.get('hp_mul', 1.0) * p.get('hp_mul', 1.0)
        em['bomb_immunity_once'] = True

    elif ek == 'global_atk_mul':
        tower_mod['global_atk_mul'] = tower_mod.get('global_atk_mul', 1.0) * p.get('atk_mul', 1.0)

    elif ek == 'kill_gold_flat':
        econ['kill_reward_bonus_flat'] = econ.get('kill_reward_bonus_flat', 0) + p.get('gold', 0)
        econ['kill_reward_every'] = p.get('per_kills', 10)

    elif ek == 'coin_card_bonus':
        econ['coin_card_bonus'] = econ.get('coin_card_bonus', 0) + p.get('bonus', 0)

    elif ek == 'sawmill_heal_bonus':
        econ['lumber_heal_bonus_ratio'] = econ.get('lumber_heal_bonus_ratio', 0.0) + p.get('ratio', 0.0)

    elif ek == 'magic_stone_drop':
        econ['magic_stone_drop_add'] = econ.get('magic_stone_drop_add', 0.0) + p.get('add_ratio', 0.0)

    elif ek == 'skill_cd_mul':
        skills['cooldown_mul'] = skills.get('cooldown_mul', 1.0) * p.get('mul', 1.0)

    elif ek == 'skill_combo_buff':
        skills['combo_rule'] = {
            'need': p.get('need', 3),
            'rof_mul': p.get('rof_mul', 1.2),
            'sec': p.get('sec', 5.0),
        }

    elif ek == 'skill_cost_reduce':
        skills['cost_reduction'] = skills.get('cost_reduction', 0) + p.get('minus', 0)

    elif ek == 'skill_lightning_echo':
        skills['lightning_echo'] = skills.get('lightning_echo', 0) + p.get('extra_bounce', 0)

    elif ek == 'free_reroll_once':
        state['free_reroll_available'] = True

    elif ek == 'lowhp_defense_aura':
        tower_mod['lowhp_defense_aura'] = {
            'hp_ratio': p.get('hp_ratio', 0.5),
            'def_mul': p.get('def_mul', 1.3)
        }

    elif ek == 'fusion_bonus_level':
        state['fusion_add_level'] = state.get('fusion_add_level', 0) + p.get('add_level', 1)

    elif ek == 'same_element_set':
        setsys['same_elem_rule'] = {
            'need': p.get('need', 3),
            'atk_mul': p.get('atk_mul', 1.15)
        }

    elif ek == 'global_random_element':
        state['temp_global_random_element_sec'] = p.get('sec', 10.0)

    elif ek == 'time_stop_burst':
        state['time_stop'] = max(0.0, float(p.get('sec', 3.0)))
        state['burst_cast'] = True  # engine should fire all towers once

    elif ek == 'double_end_loot':
        state['double_loot_this_wave'] = True

    elif ek == 'build_upgrade_discount':
        # To be consumed by your PRICES system
        state['build_speed_mul'] = state.get('build_speed_mul', 1.0) * p.get('build_speed_mul', 1.0)
        state['upgrade_cost_minus'] = state.get('upgrade_cost_minus', 0) + p.get('upgrade_minus', 0)


# -----------------------------
# Helper: pretty text for UI
# -----------------------------

def format_talent_text(t: Dict) -> str:
    return f"[{t['rarity']}] {t['name']}\n{t['desc']}"
