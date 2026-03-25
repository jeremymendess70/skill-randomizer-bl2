import os
import random
import re

import unrealsdk
from unrealsdk import *

from ..ModManager import BL2MOD, RegisterMod
from Mods.ModMenu import Game, Hook


class CrossSkillRandomizer(BL2MOD):
    Name: str = "Skill Level Randomizer ({})"
    Description: str = "Keep vanilla trees and randomize only vanilla skill max levels (1 to 50)."
    Version: str = "3.1"
    Author: str = "Abahbob"
    SupportedGames = Game.BL2
    LocalModDir: str = os.path.dirname(os.path.realpath(__file__))
    SeedFileName: str = "current_seed.txt"
    SeedBroadcastPattern = re.compile(r"\[CCSR_SEED:(-?\d+)\]")
    SkillMaxCap: int = 50

    def __init__(self, seed=None):
        self.Seed = seed if seed is not None else self.LoadSavedSeed()
        if self.Seed is None:
            self.Name = self.Name.format("New Seed")
        else:
            self.Name = self.Name.format(self.Seed)

    def GetSeedFilePath(self) -> str:
        return self.LocalModDir + "\\" + self.SeedFileName

    def LoadSavedSeed(self):
        seed_path = self.GetSeedFilePath()
        if not os.path.isfile(seed_path):
            return None

        with open(seed_path, "r") as f:
            raw_seed = f.read().strip()
            if raw_seed == "":
                return None

        try:
            return int(raw_seed)
        except ValueError:
            unrealsdk.Log("Invalid saved seed '{}' , ignoring seed file.".format(raw_seed))
            return None

    def SaveSeed(self) -> None:
        with open(self.GetSeedFilePath(), "w") as f:
            f.write(str(self.Seed))

    def SetSeed(self, seed: int, persist: bool = True) -> None:
        self.Seed = seed
        self.RNG = random.Random(self.Seed)
        self.Name = "Skill Level Randomizer ({})".format(self.Seed)
        unrealsdk.Log("Skill Level Randomizer seed set to '{}' (1..{}).".format(self.Seed, self.SkillMaxCap))
        if persist:
            self.SaveSeed()

    def PreloadPackages(self) -> None:
        packages = [
            "GD_Assassin_Streaming_SF",
            "GD_Mercenary_Streaming_SF",
            "GD_Siren_Streaming_SF",
            "GD_Lilac_Psycho_Streaming_SF",
            "GD_Tulip_Mechro_Streaming_SF",
            "GD_Soldier_Streaming_SF",
        ]
        for package in packages:
            unrealsdk.LoadPackage(package)

    def GetAllVanillaSkillNames(self):
        all_names = []
        for skill_names in self.ClassSkills.values():
            all_names += skill_names
        all_names += self.AnarchySkills
        all_names += self.BloodlustSkills
        all_names += self.GlobalSkills
        return all_names

    def RandomizeVanillaSkillLevels(self) -> int:
        if self.Seed is None:
            return 0

        self.PreloadPackages()
        changed_skills = 0
        for skill_name in self.GetAllVanillaSkillNames():
            skill_def = unrealsdk.FindObject("SkillDefinition", skill_name)
            if skill_def is None:
                continue
            rolled_max = self.RNG.randint(1, self.SkillMaxCap)
            for max_attr in ["MaxGrade", "GradeCap", "MaxSkillGrade", "MaxSkillLevel"]:
                if hasattr(skill_def, max_attr):
                    setattr(skill_def, max_attr, rolled_max)
            changed_skills += 1

        return changed_skills

    def ShareSeedInChat(self, caller: UObject) -> None:
        if self.Seed is None:
            return
        caller.ConsoleCommand("say [CCSR_SEED:{}]".format(self.Seed))

    def TryApplySeedFromMessage(self, message: str) -> bool:
        seed_match = self.SeedBroadcastPattern.search(str(message))
        if seed_match is None:
            return False

        shared_seed = int(seed_match.group(1))
        if self.Seed == shared_seed:
            return True

        self.SetSeed(shared_seed)
        changed_skills = self.RandomizeVanillaSkillLevels()
        unrealsdk.Log("Applied shared seed '{}' to {} vanilla skills.".format(shared_seed, changed_skills))
        return True

    @Hook("WillowGame.WillowPlayerController.ConsoleCommand")
    def HandleConsoleSeedCommand(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
        return self.TryHandleSeedCommand(caller, params.Command)

    @Hook("Engine.PlayerController.ConsoleCommand")
    def HandleConsoleSeedCommandEngine(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
        return self.TryHandleSeedCommand(caller, params.Command)

    def TryHandleSeedCommand(self, caller: UObject, raw_command) -> bool:
        command = str(raw_command).strip()
        parts = command.split()
        if len(parts) == 0 or parts[0].lower() != "seed":
            return True

        if len(parts) != 2:
            unrealsdk.Log("Usage: seed <number>")
            return False

        try:
            new_seed = int(parts[1])
        except ValueError:
            unrealsdk.Log("Invalid seed '{}' . Usage: seed <number>".format(parts[1]))
            return False

        self.SetSeed(new_seed)
        changed_skills = self.RandomizeVanillaSkillLevels()
        self.ShareSeedInChat(caller)
        unrealsdk.Log("Seed changed and applied to {} vanilla skills.".format(changed_skills))
        return False

    @Hook("WillowGame.WillowPlayerController.ClientMessage")
    def ReceiveSeedFromChat(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
        for message_attr in ["S", "Message", "Msg", "Text", "String"]:
            if hasattr(params, message_attr):
                if self.TryApplySeedFromMessage(getattr(params, message_attr)):
                    break
        return True

    @Hook("WillowGame.TextChatGFxMovie.AddChatMessage")
    def ReceiveSeedFromTextChat(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
        for message_attr in ["msg", "Message", "Text", "S"]:
            if hasattr(params, message_attr):
                if self.TryApplySeedFromMessage(getattr(params, message_attr)):
                    break
        return True

    @Hook("WillowGame.PlayerSkillTree.Initialize")
    def InjectSkills(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
        if self.Seed is None:
            self.SetSeed(random.randrange(2**63))
        else:
            self.RNG = random.Random(self.Seed)

        changed_skills = self.RandomizeVanillaSkillLevels()
        unrealsdk.Log("Applied vanilla skill max-level randomization with seed '{}' to {} skills.".format(self.Seed, changed_skills))
        return True

    ClassSkills = {
        "Soldier": [
            "GD_Soldier_Skills.Guerrilla.DoubleUp",
            "GD_Soldier_Skills.Guerrilla.LaserSight",
            "GD_Soldier_Skills.Guerrilla.ScorchedEarth",
            "GD_Soldier_Skills.Guerrilla.Sentry",
            "GD_Soldier_Skills.Gunpowder.Battlefront",
            "GD_Soldier_Skills.Gunpowder.LongBowTurret",
            "GD_Soldier_Skills.Gunpowder.Nuke",
            "GD_Soldier_Skills.Survival.Gemini",
            "GD_Soldier_Skills.Survival.Mag-Lock",
            "GD_Soldier_Skills.Survival.PhalanxShield",
        ],
        "Assassin": [
            "GD_Assassin_Skills.Bloodshed.Execute",
            "GD_Assassin_Skills.Bloodshed.Grim",
            "GD_Assassin_Skills.Bloodshed.ManyMustFall",
            "GD_Assassin_Skills.Cunning.DeathBlossom",
            "GD_Assassin_Skills.Cunning.Innervate",
            "GD_Assassin_Skills.Cunning.Unforseen",
        ],
        "Siren": [
            "GD_Siren_Skills.Cataclysm.ChainReaction",
            "GD_Siren_Skills.Cataclysm.Helios",
            "GD_Siren_Skills.Cataclysm.Ruin",
            "GD_Siren_Skills.Harmony.Elated",
            "GD_Siren_Skills.Harmony.Res",
            "GD_Siren_Skills.Harmony.SweetRelease",
            "GD_Siren_Skills.Harmony.Wreck",
            "GD_Siren_Skills.Motion.Converge",
            "GD_Siren_Skills.Motion.Quicken",
            "GD_Siren_Skills.Motion.SubSequence",
            "GD_Siren_Skills.Motion.Suspension",
            "GD_Siren_Skills.Motion.ThoughtLock",
        ],
        "Mercenary": [
            "GD_Mercenary_Skills.Brawn.AintGotTimeToBleed",
            "GD_Mercenary_Skills.Brawn.BusThatCantSlowDown",
            "GD_Mercenary_Skills.Brawn.ComeAtMeBro",
            "GD_Mercenary_Skills.Brawn.FistfulOfHurt",
            "GD_Mercenary_Skills.Gun_Lust.DivergentLikness",
            "GD_Mercenary_Skills.Gun_Lust.DownNotOut",
            "GD_Mercenary_Skills.Gun_Lust.KeepItPipingHot",
            "GD_Mercenary_Skills.Rampage.DoubleYourFun",
            "GD_Mercenary_Skills.Rampage.GetSome",
            "GD_Mercenary_Skills.Rampage.ImReadyAlready",
            "GD_Mercenary_Skills.Rampage.KeepFiring",
            "GD_Mercenary_Skills.Rampage.LastLonger",
            "GD_Mercenary_Skills.Rampage.SteadyAsSheGoes",
            "GD_Mercenary_Skills.Rampage.YippeeKiYay",
        ],
        "Lilac": [
            "GD_Lilac_Skills_Bloodlust.Skills.BloodTrance",
            "GD_Lilac_Skills_Bloodlust.Skills.BuzzAxeBombadier",
            "GD_Lilac_Skills_Bloodlust.Skills.TasteOfBlood",
            "GD_Lilac_Skills_Hellborn.Skills.HellfireHalitosis",
            "GD_Lilac_Skills_Mania.Skills.FuelTheRampage",
            "GD_Lilac_Skills_Mania.Skills.LightTheFuse",
            "GD_Lilac_Skills_Mania.Skills.ReleaseTheBeast",
        ],
        "Mechromancer": [
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.20PercentCooler",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.BuckUp",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.ExplosiveClap",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.MadeOfSternerStuff",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.PotentAsAPony",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.SharingIsCaring",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.UpshotRobot",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.AnnoyedAndroid",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.RobotRampage",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.MakeItSparkle",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.OneTwoBoom",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.StrengthOfFiveGorillas",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.TheStare",
        ],
    }

    AnarchySkills = [
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.PreshrunkCyberpunk",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.Discord",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TypecastIconoclast",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.RationalAnarchist",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.WithClaws",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.BloodSoakedShields",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.DeathFromAbove",
    ]

    BloodlustSkills = [
        "GD_Lilac_Skills_Bloodlust.Skills.BloodOverdrive",
        "GD_Lilac_Skills_Bloodlust.Skills.BloodyRevival",
        "GD_Lilac_Skills_Bloodlust.Skills.BloodBath",
        "GD_Lilac_Skills_Bloodlust.Skills.FuelTheBlood",
        "GD_Lilac_Skills_Bloodlust.Skills.BoilingBlood",
        "GD_Lilac_Skills_Bloodlust.Skills.NervousBlood",
        "GD_Lilac_Skills_Bloodlust.Skills.Bloodsplosion",
    ]

    GlobalSkills = [
        "GD_Assassin_Skills.Bloodshed.Backstab",
        "GD_Assassin_Skills.Bloodshed.BeLikeWater",
        "GD_Assassin_Skills.Bloodshed.Followthrough",
        "GD_Assassin_Skills.Bloodshed.IronHand",
        "GD_Assassin_Skills.Bloodshed.KillingBlow",
        "GD_Assassin_Skills.Bloodshed.LikeTheWind",
        "GD_Assassin_Skills.Bloodshed.Resurgence",
        "GD_Assassin_Skills.Cunning.Ambush",
        "GD_Assassin_Skills.Cunning.CounterStrike",
        "GD_Assassin_Skills.Cunning.DeathMark",
        "GD_Assassin_Skills.Cunning.FastHands",
        "GD_Assassin_Skills.Cunning.Fearless",
        "GD_Assassin_Skills.Cunning.RisingShot",
        "GD_Assassin_Skills.Cunning.TwoFang",
        "GD_Assassin_Skills.Sniping.AtOneWithTheGun",
        "GD_Assassin_Skills.Sniping.Bore",
        "GD_Assassin_Skills.Sniping.CriticalAscention",
        "GD_Assassin_Skills.Sniping.HeadShot",
        "GD_Assassin_Skills.Sniping.KillConfirmed",
        "GD_Assassin_Skills.Sniping.Killer",
        "GD_Assassin_Skills.Sniping.OneShotOneKill",
        "GD_Assassin_Skills.Sniping.Optics",
        "GD_Assassin_Skills.Sniping.Precision",
        "GD_Assassin_Skills.Sniping.Velocity",
        "GD_Lilac_Skills_Bloodlust.Skills.BloodfilledGuns",
        "GD_Lilac_Skills_Bloodlust.Skills.BloodyTwitch",
        "GD_Lilac_Skills_Hellborn.Skills.BurnBabyBurn",
        "GD_Lilac_Skills_Hellborn.Skills.DelusionalDamage",
        "GD_Lilac_Skills_Hellborn.Skills.ElementalElation",
        "GD_Lilac_Skills_Hellborn.Skills.ElementalEmpathy",
        "GD_Lilac_Skills_Hellborn.Skills.FireFiend",
        "GD_Lilac_Skills_Hellborn.Skills.FlameFlare",
        "GD_Lilac_Skills_Hellborn.Skills.FuelTheFire",
        "GD_Lilac_Skills_Hellborn.Skills.NumbedNerves",
        "GD_Lilac_Skills_Hellborn.Skills.PainIsPower",
        "GD_Lilac_Skills_Hellborn.Skills.RavingRetribution",
        "GD_Lilac_Skills_Mania.Skills.EmbraceThePain",
        "GD_Lilac_Skills_Mania.Skills.EmptyRage",
        "GD_Lilac_Skills_Mania.Skills.FeedTheMeat",
        "GD_Lilac_Skills_Mania.Skills.PullThePin",
        "GD_Lilac_Skills_Mania.Skills.RedeemTheSoul",
        "GD_Lilac_Skills_Mania.Skills.SaltTheWound",
        "GD_Lilac_Skills_Mania.Skills.SilenceTheVoices",
        "GD_Lilac_Skills_Mania.Skills.StripTheFlesh",
        "GD_Lilac_Skills_Mania.Skills.ThrillOfTheKill",
        "GD_Mercenary_Skills.Brawn.Asbestos",
        "GD_Mercenary_Skills.Brawn.Diehard",
        "GD_Mercenary_Skills.Brawn.ImTheJuggernaut",
        "GD_Mercenary_Skills.Brawn.Incite",
        "GD_Mercenary_Skills.Brawn.JustGotReal",
        "GD_Mercenary_Skills.Brawn.OutOfBubblegum",
        "GD_Mercenary_Skills.Brawn.SexualTyrannosaurus",
        "GD_Mercenary_Skills.Gun_Lust.AllIneedIsOne",
        "GD_Mercenary_Skills.Gun_Lust.AutoLoader",
        "GD_Mercenary_Skills.Gun_Lust.ImYourHuckleberry",
        "GD_Mercenary_Skills.Gun_Lust.LayWaste",
        "GD_Mercenary_Skills.Gun_Lust.LockedandLoaded",
        "GD_Mercenary_Skills.Gun_Lust.MoneyShot",
        "GD_Mercenary_Skills.Gun_Lust.NoKillLikeOverkill",
        "GD_Mercenary_Skills.Gun_Lust.QuickDraw",
        "GD_Mercenary_Skills.Rampage.5Shotsor6",
        "GD_Mercenary_Skills.Rampage.AllInTheReflexes",
        "GD_Mercenary_Skills.Rampage.FilledtotheBrim",
        "GD_Mercenary_Skills.Rampage.Inconceivable",
        "GD_Siren_Skills.Cataclysm.Backdraft",
        "GD_Siren_Skills.Cataclysm.BlightPhoenix",
        "GD_Siren_Skills.Cataclysm.CloudKill",
        "GD_Siren_Skills.Cataclysm.Flicker",
        "GD_Siren_Skills.Cataclysm.Foresight",
        "GD_Siren_Skills.Cataclysm.Immolate",
        "GD_Siren_Skills.Cataclysm.Reaper",
        "GD_Siren_Skills.Harmony.LifeTap",
        "GD_Siren_Skills.Harmony.MindsEye",
        "GD_Siren_Skills.Harmony.Recompense",
        "GD_Siren_Skills.Harmony.Restoration",
        "GD_Siren_Skills.Harmony.Scorn",
        "GD_Siren_Skills.Harmony.Sustenance",
        "GD_Siren_Skills.Motion.Accelerate",
        "GD_Siren_Skills.Motion.Fleet",
        "GD_Siren_Skills.Motion.Inertia",
        "GD_Siren_Skills.Motion.KineticReflection",
        "GD_Siren_Skills.Motion.Ward",
        "GD_Soldier_Skills.Guerrilla.Able",
        "GD_Soldier_Skills.Guerrilla.CrisisManagement",
        "GD_Soldier_Skills.Guerrilla.Grenadier",
        "GD_Soldier_Skills.Guerrilla.Onslaught",
        "GD_Soldier_Skills.Guerrilla.Ready",
        "GD_Soldier_Skills.Guerrilla.Willing",
        "GD_Soldier_Skills.Gunpowder.DoOrDie",
        "GD_Soldier_Skills.Gunpowder.DutyCalls",
        "GD_Soldier_Skills.Gunpowder.Expertise",
        "GD_Soldier_Skills.Gunpowder.Impact",
        "GD_Soldier_Skills.Gunpowder.MetalStorm",
        "GD_Soldier_Skills.Gunpowder.Overload",
        "GD_Soldier_Skills.Gunpowder.Ranger",
        "GD_Soldier_Skills.Gunpowder.Steady",
        "GD_Soldier_Skills.Survival.Forbearance",
        "GD_Soldier_Skills.Survival.Grit",
        "GD_Soldier_Skills.Survival.HealthY",
        "GD_Soldier_Skills.Survival.LastDitchEffort",
        "GD_Soldier_Skills.Survival.Preparation",
        "GD_Soldier_Skills.Survival.Pressure",
        "GD_Soldier_Skills.Survival.QuickCharge",
        "GD_Tulip_Mechromancer_Skills.BestFriendsForever.CloseEnough",
        "GD_Tulip_Mechromancer_Skills.BestFriendsForever.CookingUpTrouble",
        "GD_Tulip_Mechromancer_Skills.BestFriendsForever.FancyMathematics",
        "GD_Tulip_Mechromancer_Skills.BestFriendsForever.TheBetterHalf",
        "GD_Tulip_Mechromancer_Skills.BestFriendsForever.UnstoppableForce",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.Anarchy",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.SmallerLighterFaster",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TheNthDegree",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.ElectricalBurn",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.EvilEnchantress",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.InterspersedOutburst",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.MorePep",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.Myelin",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.ShockAndAAAGGGHHH",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.ShockStorm",
        "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.WiresDontTalk",
    ]

rando = CrossSkillRandomizer()

RegisterMod(rando)
