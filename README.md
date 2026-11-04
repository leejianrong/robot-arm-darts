# Robot Arm Darts

A MuJoCo digital twin of an SO-101 robot arm that learns to throw a 10 g dart at a regulation-height dartboard. Everything calibratable lives in `twin.yaml`, so the numbers can be tuned to match a real arm later.

Status: early. The plan is in [`PLAN.md`](PLAN.md), the build order in [`SLICES.md`](SLICES.md), and the decisions in [`docs/adr/`](docs/adr/).

## Quick start

```bash
make install     # uv sync
make assets      # fetch the Menagerie SO-101 model (Apache-2.0)
make check       # lint, type-check, fast tests
```

Training and rendering are meant to run on a rented GPU pod (RunPod); the laptop only edits and reads results.

## License

Apache-2.0. The SO-101 model is from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie), also Apache-2.0, and is fetched at setup rather than redistributed.
