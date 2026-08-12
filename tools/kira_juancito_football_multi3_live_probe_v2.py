from __future__ import annotations

import time

import kira_juancito_football_multi3_live_probe as base


def wait_for_boss_frame(page):
    deadline = time.time() + 25
    while time.time() < deadline:
        for frame in page.frames:
            if "BOSSWagering/Sportsbook" in (frame.url or ""):
                return frame
        page.wait_for_timeout(1000)
    raise RuntimeError("INFRA_BOSS_FRAME_NOT_LOADED")


base.surf = wait_for_boss_frame

if __name__ == "__main__":
    base.main()
