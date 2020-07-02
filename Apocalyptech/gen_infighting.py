#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

import re
import os
import sys
import lzma

from bl3data.bl3data import BL3Data
from bl3hotfixmod.bl3hotfixmod import Mod, LVL_TO_ENG

# So this util relies on having a set of level-specific object dumps, of the sort
# generated by UUU, among other UE4 DLL-injected libraries:
# https://framedsc.github.io/GeneralGuides/universal_ue4_consoleunlocker.htm
#
# That's a *bit* overkill, but the advantage is that it's a pretty trivial way
# for me to tailor a set of level hotfixes without going too crazy with MatchAll.
# This alternative (but untested) implementation is theoretically all you'd need
# to do this mod using only JWP serializations:
#
#     data = BL3Data()
#     for spawnoption_name in data.find('', 'SpawnOptions_'):
#         if 'Enemies' in spawnoption_name:
#             spawnoption = data.get_exports(spawnoption_name, 'SpawnOptionData')[0]
#             for idx in range(len(spawnoption['Options'])):
#                 mod.reg_hotfix(Mod.EARLYLEVEL, 'MatchAll',
#                         spawnoption_name,
#                         'Options.Options[{}].Factory.Object..TeamOverride'.format(idx),
#                         team_to_set)
#
# ... that's it!  But you still end up with a mod file that's nearly 800KB (this
# one's 1.1MB, so not that much bigger), and you'd have nearly 3k MatchAll level
# statements.
#
# So in the end, I just kept this implementation, since I've got those object name
# dumps anyway.  Apologies to anyone else looking to re-generate this mod, though!

# TODO: It'd be trivial to adapt this to make all enemies totally friendly, but then
# I'd have to go through and make sure that any required-kill enemies *aren't*
# friendly, and that's more work than I care to do.

# Control vars
base_dir = '/home/pez/bl3_steam_root/OakGame/Binaries/Win64/data'
subdirs = [
        'basegame',
        'events',
        'others',
        'dlc1',
        'dlc2',
        'dlc3',
        ]
spawn_re = re.compile(r' SpawnFactory_OakAI (?P<spawnoption>SpawnOptions_.*)\.\1\.SpawnFactory_OakAI_(?P<raw_number>\d+)')
spawn2_re = re.compile(r' SpawnFactory_OakAI (?P<spawnoption>SpawnOptions_.*)\.\1\.(?P<factory_obj>Factory_SpawnFactory_OakAI(_\d+)?)')
spawnoption_blacklist = {
        # There's another "SpawnOptions_CoVMix_Mine" and this one appears unused
        '/Game/PatchDLC/Event2/Enemies/_Spawning/WorldMechanicMixes/WorldMapMixes/SpawnOptions_CoVMix_Mine',
        }
# Turns out we don't need to "randomize" teams at all, 'cause the Enraged Goliath
# team works great all by itself.
#teams_base = [
#        'Team_Ape',
#        'Team_Biobeast',
#        'Team_CombatIO',
#        'Team_CotV_Skagzilla',
#        'Team_CotV',
#        'Team_Enemies',
#        'Team_EnragedGoliath',
#        'Team_FriendlyToAll',
#        'Team_Guardians',
#        'Team_Hostile',
#        'Team_LootTracker_Evil',
#        'Team_LootTracker',
#        'Team_Maliwan',
#        'Team_Nekrobug',
#        'Team_Neutral',
#        'Team_NonPlayers_NoPlayerCollision',
#        'Team_NonPlayers',
#        'Team_Players',
#        'Team_Rakk_Troy',
#        'Team_Rakk',
#        'Team_Ratch',
#        'Team_Saurian',
#        'Team_ServiceBots',
#        'Team_Skag',
#        'Team_Spiderant',
#        'Team_Splotch',
#        'Team_TroyCalypso',
#        'Team_Varkid',
#        ]
team_to_set = Mod.get_full_cond('/Game/Common/_Design/Teams/Team_EnragedGoliath', 'Team')

# Extra check, since this requires some extra data
if not os.path.exists(base_dir):
    print('Constructing this requires a specific set of data dumps, using a UE4 object-dumper DLL')
    sys.exit(1)

# Figure out what SpawnOptions_* objects we care about
data = BL3Data()
spawnoptions = {}
for spawnoption in data.find('', 'SpawnOptions_'):
    if spawnoption in spawnoption_blacklist:
        continue
    if 'Enemies' in spawnoption:
        last_bit = spawnoption.split('/')[-1]
        if last_bit in spawnoptions:
            print('ERROR: {} already in spawnoptions: {} -> {}'.format(
                last_bit,
                spawnoptions[last_bit],
                spawnoption,
                ))
            sys.exit(2)
        spawnoptions[last_bit] = spawnoption

# Start writing the mod
mod = Mod('infighting.txt',
        'Infighting',
        'Apocalyptech',
        [
            "Sets all enemies to be on the 'enraged goliath' team, meaning that they'll",
            "be as likely to attack each other as they are to attack you.  Not very",
            "thoroughly tested, but seems to do the trick!",
        ],
        lic=Mod.CC_BY_SA_40,
        )

# No read our data dumps to find the SpawnFactory objects we'll modify
for subdir in subdirs:
    full_subdir = os.path.join(base_dir, subdir)
    for level in os.listdir(full_subdir):
        print('Processing {}...'.format(level))
        #if level != 'Lake_P':
        #    continue
        mod.header('{} ({})'.format(
            LVL_TO_ENG[level],
            level,
            ))
        obj_file = os.path.join(full_subdir, level, 'UE4Tools_ObjectsDump.txt.xz')
        with lzma.open(obj_file, 'rt', encoding='utf-8') as df:
            for line in df:
                match = spawn_re.search(line)
                if match:
                    raw_number = int(match.group('raw_number'))
                    assert(raw_number > 0)
                    if match.group('spawnoption') in spawnoptions:
                        obj_real = '{}.{}:SpawnFactory_OakAI_{}'.format(
                                spawnoptions[match.group('spawnoption')],
                                match.group('spawnoption'),
                                raw_number-1,
                                )
                        mod.reg_hotfix(Mod.EARLYLEVEL, level,
                                obj_real,
                                'TeamOverride',
                                team_to_set)
                else:
                    match = spawn2_re.search(line)
                    if match:
                        if match.group('spawnoption') in spawnoptions:
                            obj_real = '{}.{}:{}'.format(
                                    spawnoptions[match.group('spawnoption')],
                                    match.group('spawnoption'),
                                    match.group('factory_obj'),
                                    )
                            mod.reg_hotfix(Mod.EARLYLEVEL, level,
                                    obj_real,
                                    'TeamOverride',
                                    team_to_set)

        mod.newline()

mod.close()