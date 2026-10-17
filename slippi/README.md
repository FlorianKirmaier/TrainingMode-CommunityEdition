# Slippi recording and auto-load (fork `slippi-recording`)

AI-written (Claude), for personal use with [slippi-achievements](https://github.com/FlorianKirmaier/slippi-achivements).
Not meant as a contribution to TM-CE ("Do not contribute AI code").

## What it adds

- **Slippi recording in Training Mode.** `add-recording.py` copies a TM-CE ISO and appends Slippi's "Slippi Recording"
  Gecko codes, taken from the installed Slippi Dolphin, to TM-CE's own `codes.gct`. The Slippi Dolphin then writes `.slp`
  replays of Lab sessions and streams them to spectators (overlays) like any match. Games are Event Match (major scene 43),
  which vanilla Slippi never records, so tools can tell them apart.
- **Auto-load** (`src/autoload.h`, `src/events.c`, `src/lab_css.c`). When a recording named `TMREC_AUTO_…` that is at most
  120 s old is on a memory card, the game boots straight into the Lab, opens the import menu on it, confirms, and the Lab
  starts from that position. Older `TMREC_AUTO_` files are ordinary recordings in Lab → Import.

## Build

```sh
./build.sh "<vanilla Melee 1.02 ISO>"            # devkitPro gamecube-dev + xdelta3; debug build with OSReport logs
python3 slippi/add-recording.py TM-CE.iso ~/smash/TM-CE-slippi.iso
```

`add-recording.py` needs the Slippi Launcher's netplay Dolphin (macOS default path, or pass its `Sys` folder). Nothing of
Slippi's is copied into this repository; after a Slippi update, run it again. `--skip <name>` leaves out codes (for
bisecting); `GC_FST=<binary>` uses another gc_fst.

## How the recording codes fit in

- Game ID stays `GTME01`, so Dolphin loads none of Slippi's own codes. Setting it to `GALE01` makes Dolphin add *all*
  required Slippi codes, whose online m-ex codeset and boot hook collide with TM-CE's (crash at event start).
- Taken: the "Slippi Recording" block plus `EXITransferBuffer` and `ProcessGecko` from Slippi's `bootloader.gct`
  (static functions at 0x800055F0 / 0x800055FC the recording codes call).
- Left out: Init Player/Stage Data (TM-CE has the same), CSS KO stars.
- Changed: player block 0x2600 (Slippi) instead of 0x2530 (TM-CE); Slippi's only own field is at 0x25FF. ShouldRecord
  returns true in every scene. `GeckoHeapPtr` points to an empty code list at 0x80005620, so the replay's code list is empty.

## Lessons learned

- **gc_fst `fs insert` could overwrite another file.** Free space was computed from ranges sorted by start only; an empty
  file sharing its start with another (`usa.ini` and `TM/eventMenu.dat` at 0x460000) made the occupied range look free,
  and the inserted `codes.gct` overwrote `eventMenu.dat`. Every rebuilt ISO crashed, which looked like a Slippi/TM-CE
  conflict for a long time. Fixed in FlorianKirmaier/gc_fst (branch `fix-free-space-overlap`); `bin/gc_fst_macos_arm64`
  is that build, and `add-recording.py` refuses ISOs with overlapping files. When a built ISO crashes, check its layout
  first: `bin/gc_fst_macos_arm64 tree <iso> -s -o -x`.
- **The CSS overwrites the fighters once more after confirming an import.** `Import_Start` sets preload/CSS fighters and
  leaves the CSS; on the next frame the CSS writes its own (empty) choices again: Master Hand (26) for the CPU or none (33)
  for the human, which crashed the Lab (`Invalid read`, PC 0x8000b21c in `JObj_GetWorldPos`). Confirming by hand only
  works because the A press fires the confirm twice. The auto-load re-applies the import for 5 frames.
- **Never touch the memory card during a scene change.** Mounting it in `OnSceneChange` while the game saves broke the
  game's card state (`Invalid write to 0xffffffff`, PC 0x80347b80 `ExternalInterruptHandler`). Look for files only when
  `Memcard_CheckStatus() != 11`.
- **The event select is part of the main menu** (scene 1/0); 43/0 is already the event's CSS. Faked A presses in the main
  menu are ignored, and leaving the main menu with `Scene_ExitMinor` lands on the title screen. `OnBoot` (0x801bfa28) runs
  right after the boot scene chose the next major, so `Scene_SetNextMajor(0x2B)` there boots straight into the event.
- **Controller port.** Without the event select nobody "entered" the CSS: the human port is the last used one
  (`EventBackup.port`) if a controller is plugged in there (`stc_master_pads->pad[i].error == 0`), else the first plugged one.
- **Dolphin reads the GCI memory card folder only at start**, so a new recording needs a Dolphin restart.

## Debugging with logs

The debug build reports with `OSReport` (lines starting with `autoload:`, `import:`, `event init:`). To see them in the
netplay Dolphin (`~/Library/Application Support/com.project-slippi.dolphin/netplay/User`):

1. Copy `GTME01.map` to `User/Maps/GTME01.map` (Dolphin then recognises `OSReport`).
2. In `User/Config/Logger.ini` add under `[Options]` `Verbosity = 4` and `WriteToFile = True`, and a section `[Logs]`
   with `OSREPORT = True` and `OSREPORT_HLE = True`.
3. Read `User/Logs/dolphin.log`. Remove the lines again afterwards.

Crash addresses map to functions through `GTME01.map`.
