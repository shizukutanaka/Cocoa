# Cocoa - Avatar Management Platform

![Status](https://img.shields.io/badge/status-active-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A production-grade avatar management system with enterprise security, comprehensive monitoring, and disaster recovery capabilities.

## Features

- **Security First**: AES-256-GCM encryption, audit logging, and policy-driven access control
- **System Monitoring**: Real-time health checks, performance metrics, and anomaly detection
- **Disaster Recovery**: Automated backups, verification, and multi-strategy recovery
- **Preset Management**: Large-scale parameter handling with version control and GUI tools
- **Multi-language Support**: 140+ languages with real-time translation capabilities
- **Metaverse Ready**: VR/AR integration, cross-platform synchronization

## Quick Start

### Prerequisites

- Python 3.8 or later
- 4 GB RAM (minimum), 8 GB recommended
- 10 GB free disk space

### Installation

```bash
# Clone and setup
git clone https://github.com/yourusername/cocoa.git
cd cocoa

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Basic Usage

```bash
# Launch main application
python main/main.py

# Run tests
python -m pytest tests -v

# Check system health
python -c "from main.health_monitor import get_health_monitor; import json; print(json.dumps(get_health_monitor().run_all_checks(), indent=2, ensure_ascii=False))"
```

## Project Structure

```
cocoa/
├── main/
│   ├── main.py                   # Application launcher
│   ├── integrated_security.py    # Security & encryption
│   ├── health_monitor.py         # System health checks
│   ├── performance_monitor.py    # Performance metrics
│   ├── disaster_recovery.py      # Backup & recovery
│   ├── preset_manager.py         # Preset management
│   └── avatar_preset_linker_gui.py
├── config/
│   ├── config.json              # Configuration
│   ├── database.json            # Database settings
│   └── plugins/                 # Plugin configs
├── scripts/
│   ├── run_performance_tests.py
│   ├── migrate_to_database.py
│   └── perf_log_viewer.py
├── tests/                       # Test suite
├── docs/                        # Documentation
├── requirements.txt
├── .env.example
└── LICENSE
```

## Configuration

### Environment Variables

Essential variables in `.env`:

```env
OTEDAMA_SECRET_KEY=<32+ char random string>
OTEDAMA_ENCRYPTION_KEY=<32+ char random string>
OTEDAMA_ADMIN_PASS=<bcrypt hash>
OTEDAMA_SECURITY_DB=data/security/security.db
```

Generate secure keys:

```python
import secrets
print(secrets.token_urlsafe(48))
```

### Config File

Update `config/config.json`:

```json
{
  "security": {
    "encryption_enabled": true,
    "audit_logging": true
  },
  "performance_monitoring": {
    "enabled": true,
    "check_interval_seconds": 300
  },
  "backup": {
    "enabled": true,
    "retention_days": 30
  }
}
```

## Operations

### Daily Checks

```bash
# Health check
python -c "from main.health_monitor import get_health_monitor; import json; print(json.dumps(get_health_monitor().run_all_checks(), indent=2))"

# Security report
python -c "from main.integrated_security import get_security_manager; m = get_security_manager(); m.initialize(); import json; print(json.dumps(m.get_security_report(), indent=2))"
```

### Backup & Recovery

```python
from main.disaster_recovery import DisasterRecoveryManager, RecoveryStrategy

# Create backup
manager = DisasterRecoveryManager()
success, message, metadata = manager.create_backup(verify=True)

# List backups
backups = manager.list_backups(verified_only=True)

# Restore
manager.restore_backup("backup_id", strategy=RecoveryStrategy.FULL_RESTORE)
```

## Testing

```bash
# Run all tests
python -m pytest tests -v

# Run specific test file
python -m pytest tests/test_cocoa.py -v

# Run with coverage
python -m pytest tests --cov=main --cov-report=html
```

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Detailed configuration options
- [Developer Guide](docs/DEVELOPER_GUIDE.md) - Development setup and contributing
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [API Reference](docs/API_REFERENCE.md) - API endpoint documentation

## Security

- Encryption: AES-256-GCM
- Access Control: Policy-driven with IP whitelist
- Audit Logging: Complete audit trail with tamper-evidence
- Key Management: Automated rotation and secure storage

See [Security Policy](SECURITY.md) for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history and updates.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub issue tracker
- **Discussions**: GitHub discussions

## Acknowledgments

- Built with Python 3.8+
- Security: cryptography library
- Testing: pytest
- Monitoring: Custom health checks

---

**Last Updated**: 2025-11-02
**Version**: 1.0.0-alpha
