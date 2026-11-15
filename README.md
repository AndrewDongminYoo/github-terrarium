# GitHub Terrarium

A small living world shaped by your GitHub activity.
Stars bring flowers and fireflies, forks spread seedlings, pull requests grow plants, reviews enrich a pond, and issues add mushrooms.

**Status: specification and planning.**
The generator, artwork, and GitHub Actions workflows are not implemented yet.
No generated image or live preview is available at this stage.

## Planned experience

- A personal terrarium with a stable layout that grows over time.
- Public GitHub activity mapped to five visual traits and persistent growth.
- Gentle SVG animation that plays inside a GitHub profile README without JavaScript.
- Daily GitHub Actions generation, with images and growth state committed together to an `output` branch.
- A calm resting state during inactivity, with no loss of earned growth.

## Documentation

| Document | Contents |
| --- | --- |
| [Product specification](docs/specs/terrarium.md) | Scope, metric definitions, visual behavior, scoring, and acceptance criteria |
| [Technical design](docs/specs/architecture.md) | Collection, persistent state, SVG rendering, daily publication, and failure recovery |
| [Implementation plan](docs/plans/implementation.md) | Ordered milestones, intended files, tests, and release gates |
| [Contribution guide](CONTRIBUTING.md) | Current workflow and project boundaries |

## Repository layout

```plaintext
main
├── AGENTS.md
├── README.md
├── CONTRIBUTING.md
└── docs/
    ├── plans/implementation.md
    └── specs/
        ├── architecture.md
        └── terrarium.md
```

The planned `output` branch will contain `terrarium.svg`, `state.json`, and `manifest.json`.
It will be created by the first validated publication, not by this documentation bootstrap.
The planned default schedule is 00:23 UTC each day (09:23 Asia/Seoul), subject to GitHub scheduling delays.

## License

A license has not been selected yet.
