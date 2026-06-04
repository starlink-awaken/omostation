# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-04

### Added

#### Pattern 09 v2.2: Legacy Dimension
- **Legacy scoring system**: Three sub-dimensions (Age, Refactoring Resistance, Migration Path)
- **Legacy priority adjustment**: +15% / 0% / -10% based on legacy score bands
- **Standalone command**: `assess-legacy` for independent legacy evaluation
- **Legacy module**: `omo_debt.legacy` package with reusable scoring functions

### Changed
- **Version**: 0.2.0 → 1.0.0
- **Pattern**: v2.1 → v2.2
- **CLI version source**: Now reads from `omo_debt.__version__`
- **Project metadata URLs**: Switched to `starlink-awaken/omo-debt` repository

### Quality
- Unit tests expanded to 69 total (including 10 legacy tests)
- Lint and formatting checks passing in GitHub Actions
- GitHub Release v0.2.0 published and artifacts attached

## [0.2.0] - 2026-06-03

### Added

#### Pattern 09 v2.1: Honesty Dimension
- **Honesty scoring system**: Three-dimensional assessment (Completeness, Consistency, Verifiability)
- **Priority adjustment**: ±25% adjustment based on honesty score
- **CLI integration**: `--enable-honesty` flag for v2.1 mode
- **Standalone command**: `assess-honesty` for independent honesty evaluation

#### Documentation
- **TUTORIAL.md**: 5000+ word comprehensive user guide
- **API.md**: Complete API reference with examples
- **CONTRIBUTING.md**: Contribution guidelines
- **examples/**: Real-world examples (gbrain, omostation, minimal)

#### Testing
- 25 honesty dimension unit tests (100% pass rate)
- 87% honesty module coverage
- GitPython date format fixes

### Changed
- **Version**: 0.1.0 → 0.2.0
- **Pattern**: v2.0 → v2.1
- **Backward compatible**: v2.0 mode remains default

### Fixed
- GitPython date format in stage identification tests
- Honesty dimension function signatures in CLI integration

## [0.1.0] - 2026-05-28

### Added

#### Pattern 09 v2.0: Core Features
- **Stage identification**: Auto-detect project stage from Git history
- **Three-factor scoring**: Impact, Frequency, Cost with stage-specific weights
- **Priority levels**: P0, P1, P2 based on normalized scores
- **CLI commands**: `identify-stage`, `score`, `compare`, `analyze`

#### Documentation
- README with quick start guide
- Basic examples and usage

### Initial Release
- First public release of omo-debt CLI tool
- Implements Pattern 09 v2.0 specification

[0.2.0]: https://github.com/starlink-awaken/omo-debt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/starlink-awaken/omo-debt/releases/tag/v0.1.0
[1.0.0]: https://github.com/starlink-awaken/omo-debt/compare/v0.2.0...v1.0.0
