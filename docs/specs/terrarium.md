# GitHub Terrarium Specification

Status: v1 contract; implementation in progress.
Decision date: 2026-11-15.
This document defines intended behavior; see [README.md](../../README.md) for what is currently implemented.

## Purpose

Turn a person's public GitHub activity into a distinctive, animated terrarium embedded in their profile README.
The habitat retains its identity, earns permanent growth, and changes its recent details as the person's activity changes.
It is a personal visualization, not an assessment of engineering ability or a leaderboard.

## Scope

V1 supports one configured GitHub user per repository, one habitat, five activity dimensions, a daily GitHub Actions run, and one self-contained SVG.
The source branch is `main`; generated images and persistent state share the `output` branch.
Different people can run independent copies with their own configuration.
No central service, database, browser JavaScript, or visitor authentication is required.

Private activity, organization-wide attribution, multi-user hosting, interactive controls, real-time updates, merge-quality scoring, and additional biomes are deferred.
Commit counts are deliberately excluded from v1, including commits created by this generator.
Do not activate the daily workflow during the documentation bootstrap.

## User journey

1. Configure the target login in a repository copy and grant its workflow permission to publish generated contents.
2. Run generation manually; the first successful run establishes the user's stable identity and initial habitat.
3. Embed the generated `output/terrarium.svg` URL in a profile README with descriptive alt text.
4. Let the daily workflow collect activity, update growth, and publish the next state and image in one commit.
5. Inspect the workflow summary when data is stale or generation fails; the last valid habitat remains available.

The default schedule is `23 0 * * *`: 00:23 UTC, equivalent to 09:23 Asia/Seoul.
UTC is the activity-day boundary regardless of the owner's locale.
The schedule is a daily attempt, not an exact delivery-time guarantee.

## Metric contract

Stars and forks describe attention received by the user's repositories.
Pull requests, reviews, and issues describe contributions made by the user.
All metrics are explicitly public-only even when a credential can access private data.

| Dimension | V1 measurement | Habitat effect |
| --- | --- | --- |
| Stars | Current stars on owned, public, non-fork repositories | Flowers and fireflies |
| Forks | Current fork counts on the same repository set | Branches and satellite seedlings |
| Pull requests | GitHub-recognized public PR-opening contributions, including drafts | Main plant and leaves |
| Code reviews | Public review contributions, deduplicated by user, PR, and UTC day | Pond detail and small pond creatures |
| Issues | GitHub-recognized public issue-opening contributions | Mushrooms and ground cover |

Include archived original repositories in the stars/forks set; exclude the repository running the generator from every dimension.
Public contributions to other owners' repositories are eligible for PR, review, and issue metrics.
An issue count is not a count of solved bugs; a PR-opening count is not a count of merged PRs.
Restricted or private contributions are excluded rather than inferred from aggregate totals.
Only complete, validated, fully paginated observations may update the habitat.

## Two timescales

**Permanent growth** controls the main plant's development and unlocked details.
Earned growth never decreases because the owner rests, loses stars, or has an older contribution disappear from the API.
**Recent traits** use the most recent 30 completed UTC days for PRs, reviews, and issues, and current snapshots for stars and forks.
Recent flowers, visitors, and pond details may change while the main plant keeps its earned stage.

A stable seed derived from the GitHub user node ID fixes terrain, anchor positions, and variation.
A login rename must not create a different habitat.
Changing to another user must fail with an identity mismatch until a deliberate reset is authorized.
Successful empty collection means inactivity; failed collection means unknown data and must preserve the last valid output.

## Scoring version 1

These constants are frozen as scoring version 1; they are not a calibrated measure of contribution quality.
They were approved on 2026-11-17 in [#20](https://github.com/AndrewDongminYoo/github-terrarium/issues/20#issuecomment-6932925175) after the fixture gallery review, with no formula change.
Changing any weight, cap, threshold, trait cap, or bootstrap policy below requires a new scoring version with an explicit migration or refusal of older state; `tests/test_scoring_v1.py` pins these values and the persona results after bootstrap.

For each completed activity day, let `P`, `R`, and `I` be the eligible PR, deduplicated review, and issue counts.
Award `activity_xp = 12 × min(P, 5) + 4 × min(R, 10) + 3 × min(I, 5)`.
For example, two PRs, three reviewed PRs, and one issue earn `24 + 12 + 3 = 39` XP.
The maximum activity award is 115 XP per day.

For each observation day, let `S` and `F` be accumulated new star and fork units above previously observed per-repository high-water marks.
Award `popularity_xp = 2 × min(S, 20) + 5 × min(F, 10)`.
Three new star units and one new fork unit earn 11 XP; the maximum popularity award is 90 XP per day.
Apply caps to the whole UTC day, not to each workflow invocation.
Current star/fork totals are not repeatedly added to growth.

The first run establishes popularity high-water marks without awarding historical popularity XP.
It credits eligible activity from the previous 30 completed days once, using the daily activity formula.
A repository seen for the first time later also establishes its baseline without retroactive popularity credit.
These choices avoid inventing historical star/fork acquisition dates or rewarding repository transfers as new attention.
Reconciliation may increase a day's award, but never reduce an award already earned or award the same units twice.

| Earned XP | Stage | Main plant |
| --- | --- | --- |
| 0–99 | Seed | Soil, seed, and a small shoot |
| 100–499 | Sprout | A short stem with several leaves |
| 500–1,499 | Grove | A branching plant and ground cover |
| 1,500–3,999 | Mature | A developed canopy and finer detail |
| 4,000+ | Sanctuary | The richest bounded composition |

Visual density uses `trait(x, cap) = min(1, log(1 + x) / log(1 + cap))` for nonnegative `x`.
V1 caps are 500 stars, 100 forks, 30 PRs, 60 review units, and 20 issues.
The three activity caps use the recent 30-day totals, not lifetime totals.
Map the normalized values into bounded slots; exceeding a cap must not add unbounded SVG elements.
Keep a seed-stage habitat visually complete even when every metric is zero.

## Visual and motion direction

Art-direction decision: 2026-11-16.
Use a container-free landscape cross-section in a layered paper-cut style, with distant ridges, uneven moss-covered terrain, a visible soil/root section, a main tree, a pond, and restrained ambient particles.
Glass-vessel walls and reflections are not part of the composition; a thin rounded image border may frame the canvas.
Use readable silhouettes, overlapping vegetation groups, and depth from distinct foreground, middle, and distant layers.

### Paper-cut art rules

1. Each paper piece has one flat-color silhouette, with no internal gradients or shading.
2. Shadows reuse the same contour through `<use>`, translated down and to the right as a dark copy.
3. Light comes from behind the upper left; distant layers are lighter and warmer, while foreground layers are darker and cooler.
4. Gradients are limited to the sky, light bloom, and fireflies.
5. Branches extend toward the light, and thick roots extend toward the pond.
6. Color accents are limited to coral mushrooms and brown cattails.

Foliage pieces use a single contour with nine leaf tips and short pressed vein strokes.
Keep the canopy clear of identity/stage labels and distinguish rock moss from the surrounding ground.
Keep artwork self-contained, without filters, scripts, or external images.

### Reference and implementation boundary

The [Sanctuary paper-cut reference](../../assets/references/terrarium-papercut-sanctuary.svg) is the operator-supplied SVG created with Claude and retained unchanged from the supplied file.
It defines the target composition and art treatment; its fixed login, dates, and stage are design-mockup labels, not collected activity or generated growth state.
The reference is separate from packaged runtime assets and is not loaded by the renderer.
Renderer version 3 assembles extracted paper-cut pieces under the [port plan](../plans/2026-11-16-papercut-renderer.md), with low/high activity comparisons and state-driven stages and traits.
The fixed reference banner was verified in the public repository README; this does not establish GitHub playback of generated output or complete the fixture-gallery and visual-approval gates.
Source code and original artwork are released under the [MIT License](../../LICENSE).

### Scene format and motion

The SVG has a responsive `viewBox` with a design size of 900 × 360 and an opaque, self-contained scene background.
An opaque scene gives one consistent palette on both light and dark GitHub pages; transparent variants are deferred.
A compact identity label and last complete activity date make the image recognizable and its freshness understandable.

V1 has three ambient motion families: leaf sway, firefly travel, and pond ripples.
Use CSS transforms and opacity for the first implementation, with staggered cycles and no flashing.
The biological state is set at generation time; browser animation does not earn growth or simulate new activity.
After seven completed days with no eligible PR, review, or issue activity, use calmer motion without dead plants or lost progress.
Honor `prefers-reduced-motion` with a complete still illustration and preserve a useful first frame when animation is unavailable.
Include SVG `title` and `desc` elements and document descriptive README alt text.

## Publication and failure behavior

Publish `terrarium.svg`, `state.json`, and `manifest.json` together on `output` after all validation succeeds.
Keep append-only Git history with ordinary fast-forward pushes; never force-push the output branch.
Skip commits when all publishable bytes are unchanged.
The same user, normalized input, prior state, logical dates, configuration, and generator version must produce identical bytes.

API errors, missing pages, exhausted rate limits, invalid state, malformed SVG, or a failed push must not replace the previous valid bundle.
Do not bootstrap over a missing or corrupt state file on an existing output branch.
Recover missed activity days where supported and disclose unrecoverable gaps instead of fabricating zeroes or distributing observed popularity across unknown dates.
GitHub caching may delay the display of a new image; animation playback itself does not require repeated API requests.

## Acceptance criteria

| ID | Observable result |
| --- | --- |
| AC-01 | Zero-data, popularity-heavy, PR-heavy, review-heavy, and issue-heavy fixtures produce distinct, legible habitats. |
| AC-02 | A replay of the same input and state produces identical bytes and no additional growth. |
| AC-03 | Same-day extra runs respect daily caps, and decreases followed by recovery below a high-water mark do not earn popularity twice. |
| AC-04 | Missed days and late observations follow the recovery contract without duplicate activity awards. |
| AC-05 | A public-data filter excludes private/restricted nodes and the generator repository even with a privileged test credential. |
| AC-06 | A partial API result, invalid state, invalid SVG, or rejected push leaves the prior published bundle intact. |
| AC-07 | The SVG animates through an HTML image element and a real GitHub README; reduced motion displays a complete still scene. |
| AC-08 | The scene remains readable at 360, 768, and 900 CSS pixels on light and dark host pages. |
| AC-09 | Initial budgets are at most 200 KiB uncompressed SVG, 1,200 SVG elements, and 40 independently animated groups. |
| AC-10 | A complete run uses no stored credential for publication beyond the repository's workflow token; broader data credentials remain optional and public-filtered. |
| AC-11 | State and SVG hashes in the manifest identify one coherent output commit; no workflow is triggered by an output-only push. |
| AC-12 | Login changes preserve the seed; user ID or unsupported schema changes stop instead of resetting growth. |

## Pending release decisions

Calibrate performance budgets using the first implementation.
The architecture and implementation order are defined in [the technical design](architecture.md) and [the plan](../plans/implementation.md).
