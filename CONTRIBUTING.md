# Contributing to quartobot

Thanks for thinking about contributing. The project is in design phase
right now — most of the value of contributing is in the design discussion,
not the code (which doesn't exist yet).

## Right now (design phase)

1. Read [`DESIGN.md`](DESIGN.md), [`docs/prior-art.md`](docs/prior-art.md),
   and [`docs/publication-plan.md`](docs/publication-plan.md).
2. If something is wrong, missing, or under-considered, open an issue.
   Strong opinions about pattern naming, defaults, scope, or co-author
   strategy are all in scope.
3. If you've worked on a related tool (manubot, pandoc-url2cite, Quarto
   extensions, related templates), please weigh in — we'd rather build
   on prior work than reinvent.

## Later (build phase)

The plan is to ship two artifacts: a Quarto extension and a template
repository. When build work begins, this section will fill in with the
usual: branching model, test setup, how to render the example
manuscript locally, what counts as a reviewable PR.

For now, the working assumption is:

- **Branches off `main`**, named with your handle and a short description
  (e.g., `seandavi/version-banner-default`).
- **No squash merges by default** — preserve the history with merge
  commits.
- **CI must pass** before merge.
- **Discuss design changes in an issue first** so there's a paper trail
  when we write the JOSS paper.

## Code of conduct

By participating, you agree to abide by the
[Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contributions will be licensed under
the [MIT License](LICENSE).
