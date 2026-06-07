# For contributors

## Development

```bash
git clone https://github.com/aetherforge/aetherforge
cd aetherforge
uv sync
make test
```

## Project structure

```
aetherforge/
├── packages/
│   ├── gateway/    → LLM provider abstraction + routing
│   ├── mesh/       → Compute resource discovery + management
│   └── swarm/      → Multi-agent orchestration
├── src/aetherforge/ → Unified CLI + config
└── tests/
```

## PR checklist

- [ ] Tests pass (`make test`)
- [ ] New code has tests
- [ ] API.md updated if public API changed
- [ ] No breaking changes without deprecation notice

## Code of Conduct

Be excellent to each other.
