# Third-party notices

BiomeBeacon itself is MIT-licensed (see [LICENSE](LICENSE)). The components below
are third-party material with their own terms. These notices must be kept with
any redistribution of BiomeBeacon, including the packaged macro `.exe`.

## Coteab Macro (Noteab-Macro)

- Project: <https://github.com/xVapure/Noteab-Macro>
- Copyright 2025 Noteab
- License: Apache License 2.0 — full text in [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)

BiomeBeacon contains material derived from Coteab Macro, **modified** for this
project (Apache License 2.0, section 4):

- The biome color palette and biome metadata in
  `server/biomebeacon_server/db.py` (`BIOME_SEED`) are derived from Coteab
  Macro's `biomes_data.json`. Modifications: restructured into BiomeBeacon's
  per-biome notification schema, and the upstream `NORMAL` entry (which
  mistakenly reused the `GLITCHED` color/thumbnail) was corrected.
- Some biome thumbnail images (`EGGLAND`, `SINGULARITY`, `DREAMSPACE`,
  `CYBERSPACE`) are loaded at runtime from the Coteab Macro repository's
  `images/` directory; they are not bundled with BiomeBeacon.
- The macro UI (`macro/biomebeacon/webui/`) and the server admin dashboard
  (`server/biomebeacon_server/dashboard/`) adapt the visual design and layout
  ideas of Coteab Macro's HTML interface. Modifications: the markup, styles and
  scripts were rewritten for BiomeBeacon's detection-only feature set.

Upstream's `LICENSE.txt` refers to a NOTICE file, but no NOTICE file exists in
the Noteab-Macro repository (checked 2026-06-12), so there are no NOTICE
attribution entries to reproduce beyond the copyright line above.

## maxstellar biome thumbnails

Most biome thumbnails are loaded at runtime from
<https://maxstellar.github.io/> (the biome thumbnail set commonly shared by
Sol's RNG community tools). They are not bundled with BiomeBeacon.

## Sarpanch font

The bundled [Sarpanch](https://fonts.google.com/specimen/Sarpanch) webfont
(macro UI and server dashboard) is used under the SIL Open Font License 1.1 —
see `server/biomebeacon_server/dashboard/static/fonts/OFL-Sarpanch.txt`.
