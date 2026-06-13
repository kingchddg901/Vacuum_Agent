# eufy_vacuum

Room-level control for **Eufy robot vacuums** in Home Assistant — a custom integration paired with the **eufy-vacuum-command-center** Lovelace card. Choose exactly which rooms to clean and in what order, give each room its own settings, save reusable profiles, and watch a learning system get more accurate over every run.

> Tested on the **Eufy X10 Pro Omni**. These docs are generated from the `docs/` tree in the repository — edit there, not on the rendered site.

## Where to start

<div class="grid cards" markdown>

- **[User Guide](user-guide/01-overview.md)**

    Set up and drive the card day to day — rooms, queue, running a clean, the map, maintenance, profiles, themes.

- **[Advanced](advanced/03-services.md)**

    Services, automation examples, the learning system, map configuration, room rules, and the theme system in depth.

- **[Developer](dev/01-architecture-overview.md)**

    Architecture, the manager, the adapter system, every subsystem, the card architecture, and the render harness.

- **[Testing](testing/01-overview.md)**

    How the test suite is structured, how to run it, fixtures, patterns, and per-subsystem coverage.

- **[Contributing](contributing/porting-guide.md)**

    Porting the adapter to a new brand, and authoring mascots.

- **[Theme Gallery ↗](https://kingchddg901.github.io/Vacuum_Agent/)**

    Browse the real card rendered under every community-submitted theme — the live render gallery.

</div>

## Highlights

- **Room-level control** — pick rooms and order per run, with per-room mode, suction, water, path, passes, and edge-mop.
- **Profiles & run profiles** — save room settings or a whole room selection and reapply in one tap.
- **Learning system** — per-room timing estimates that improve with use, with confidence indicators.
- **Custom maps** — auto-detect rooms from a screenshot, or hand-draw named layouts on any backdrop. See [Making your own maps](user-guide/16-making-your-own-maps.md).
- **Theming** — fully customizable from the card, including a colorblind-safe theme.
- **AI-assisted theming** — the token system is documented as a machine-readable spec, so you can hand an AI a vibe (a photo, a few hex swatches), have it author a complete theme JSON, then render it through the harness and refine. See [Authoring themes with an AI](dev/reference/ai-theme-authoring.md).
