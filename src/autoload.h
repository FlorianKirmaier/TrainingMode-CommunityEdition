// AI-written (Claude): a recording named TMREC_AUTO_… that is at most AUTOLOAD_SECONDS old was just written by a tool
// (slippi-achievements' "Practice from here"); the event select then picks the Lab and the Lab CSS opens it.
#pragma once
#include "../MexTK/mex.h"

#define AUTOLOAD_PREFIX "TMREC_AUTO_"
#define AUTOLOAD_SECONDS 120

static void Autoload_WaitCard(void)
{
    while (stc_memcard_work->is_done == 0)
        blr2();
}

// The newest fresh TMREC_AUTO_ recording's file number on the card in the slot, or -1.
static int Autoload_Find(int slot)
{
    s32 memSize, sectorSize;
    int file_no = -1;
    int result = CARDProbeEx(slot, &memSize, &sectorSize);
    if (result != CARD_RESULT_READY)
    {
        OSReport("autoload: slot %d probe %d\n", slot, result);
        return -1;
    }
    stc_memcard_work->is_done = 0;
    result = CARDMountAsync(slot, stc_memcard_work->work_area, 0, Memcard_RemovedCallback);
    if (result != CARD_RESULT_READY)
    {
        OSReport("autoload: slot %d mount %d\n", slot, result);
        return -1;
    }
    Autoload_WaitCard();

    u32 ticks_per_second = os_info->bus_clock / 4;
    u64 now = OSGetTime();
    u32 newest = 0;
    CARDStat card_stat;
    for (int i = 0; i < CARD_MAX_FILE; i++)
    {
        if (CARDGetStatus(slot, i, &card_stat) != CARD_RESULT_READY)
            continue;
        if (strncmp(os_info->company, (char *)card_stat.company, sizeof(os_info->company)) != 0 ||
                strncmp(os_info->gameName, (char *)card_stat.gameName, sizeof(os_info->gameName)) != 0 ||
                strncmp(AUTOLOAD_PREFIX, card_stat.fileName, sizeof(AUTOLOAD_PREFIX) - 1) != 0)
            continue;
        u64 written = (u64)card_stat.time * ticks_per_second;
        if (written > now || now - written > (u64)AUTOLOAD_SECONDS * ticks_per_second || card_stat.time < newest)
            continue;
        newest = card_stat.time;
        file_no = i;
    }

    CARDUnmount(slot);
    stc_memcard_work->is_done = 0;
    OSReport("autoload: slot %d file %d\n", slot, file_no);
    return file_no;
}
