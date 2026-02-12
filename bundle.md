---
bundle:
  name: projector
  version: 0.1.0
  description: Project management and strategy layer for Amplifier

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: projector:behaviors/projector
  - bundle: projector:behaviors/projector-policy
---

# Projector

Cross-session project management, strategy enforcement, and coordination intelligence for Amplifier.

Projector makes every session aware of your projects, strategies, and recent work - so you never have to re-establish context or repeat working preferences.

@projector:context/projector-instructions.md

---

@foundation:context/shared/common-system-base.md
