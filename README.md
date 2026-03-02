# balena-pi-camera

Multi-fleet Raspberry Pi camera platform on balenaCloud. Each fleet directory contains a self-contained balena app for a specific hardware configuration.

## Fleets

| Directory | Fleet | Hardware | Status |
|-----------|-------|----------|--------|
| `fleets/tophand-zerocam01` | tophand-zerocam01 | Pi Zero 2W + single IMX708 | Active |
| `fleets/tophand-zerocam04` | tophand-zerocam04 | Pi Zero 2W + 4-port mux + 4x IMX708 | Planned |

## Repo Structure

```
balena-pi-camera/
├── README.md                     # This file
├── BALENA_SKILLS.md              # Comprehensive balena knowledge base
├── .gitignore
└── fleets/
    ├── tophand-zerocam01/        # Single camera fleet
    │   ├── docker-compose.yml
    │   ├── balena.yml
    │   ├── camera-service/
    │   │   ├── Dockerfile.template
    │   │   └── scripts/
    │   │       └── capture_upload.py
    │   ├── config/
    │   │   └── config.txt
    │   └── README.md
    └── tophand-zerocam04/        # Quad camera fleet (planned)
        └── ...
```

## Quick Start

```bash
# Install balena CLI
npm install -g balena-cli

# Login
balena login

# Deploy a fleet
cd fleets/tophand-zerocam01
balena push tophand-zerocam01
```

## Common Hardware

- **SBC**: Raspberry Pi Zero 2 W (aarch64)
- **Camera**: IMX708 Camera Module 3 (Wide 120)
- **Cellular** (planned): Quectel BG95 LTE-M modem
- **Storage**: Supabase object storage for image upload

## Knowledge Base

See [BALENA_SKILLS.md](BALENA_SKILLS.md) for comprehensive balena platform documentation including CLI reference, Dockerfile patterns, hardware access, networking, and troubleshooting.

## License

MIT

## Credits

Developed for Etzlertech ranch monitoring project.
