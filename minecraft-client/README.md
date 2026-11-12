# krof-smp client pack (draft)

This pack combines Fabulously Optimized 13.6.0 with Open Parties and Claims,
Xaero's Minimap, Xaero's World Map, and Jade. The client uses Minecraft 26.1.2
and Fabric loader 0.19.5; the server independently uses loader 0.19.3.
Fresh Textures remains an optional server resource pack.

Run `python3 minecraft-client/build.py` to create
`minecraft-client/dist/krof-smp-1.0.0.mrpack`. The build checks the pinned base
archive, downloads and checks every file's hashes and size, preserves its
configuration overrides, and adds the pinned client mods. No mod binaries are
committed. Built artifacts are ignored by Git.

In the Modrinth App choose Add content / Import from file and select the
`.mrpack`. Start the imported profile, then join using your separately shared
private Minecraft address. Do not put a tailnet address or credentials in the
pack. Keep the prior pack file before upgrading; to roll back, import it as a
separate profile rather than overwriting local worlds or map data. Back up
waypoints locally before switching profiles.

This is a draft. A clean import, real client login and two-player claims/map
integration test remain required before distribution. Do not publish or promise
support until each base-pack component and included override's redistribution
and download rules have been checked. No private distribution location has been
configured. Do not monetize this pack; see `CREDITS.txt` for required links and
`FABULOUSLY-OPTIMIZED-LICENSE.txt` for the base pack's license.
