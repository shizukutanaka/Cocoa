# Cocoa

Cocoa is a powerful configuration and plugin management system designed for managing complex applications and services.

## Features

- Multi-language support
- Advanced error handling
- Task scheduling
- Plugin system
- Performance monitoring
- Configuration validation
- Automatic backups
- Backup scheduling
- Environment variable support
- Dynamic plugin loading
- Enhanced configuration versioning
- Enhanced backup scheduler
- Enhanced performance monitoring
- Parameter management
- Preset management
- Parameter optimization
- Performance analysis
- Notification system
- Advanced preset management
- Configuration validation system

### Configuration Validation System

Cocoa now includes a robust configuration validation system that:

1. Validates configuration against schema
2. Checks required fields
3. Validates field types
4. Validates constraints
5. Validates relationships between fields

To use the configuration validator:

```python
from main.config_validator import ConfigValidator
from main.logging_manager import Logger

# Initialize logger and validator
logger = Logger()
validator = ConfigValidator(logger)

# Validate a configuration file
validation_result = validator.validate("config.json")

if validation_result['valid']:
    print("Configuration is valid!")
else:
    print("Validation errors:")
    for error in validation_result['errors']:
        print(f"- {error}")
```

### Advanced Preset Management

Cocoa now includes an advanced preset manager that:

1. Loads and manages presets
2. Validates preset data
3. Compares presets
4. Merges presets
5. Provides error handling

To use the preset manager:

```python
from main.preset_manager import PresetManager
from main.logging_manager import Logger

# Initialize logger and preset manager
logger = Logger()
preset_manager = PresetManager(logger)

# Load all presets
preset_manager.load_presets()

# Save a new preset
preset_data = {
    'name': 'my_preset',
    'version': '1.0',
    'parameters': {
        'param1': 'value1',
        'param2': 'value2'
    }
}
preset_manager.save_preset('my_preset', preset_data)

# Compare two presets
comparison = preset_manager.compare_presets('preset1', 'preset2')
print(f"Differences found: {len(comparison['differences'])}")

# Merge presets
merged = preset_manager.merge_presets('base_preset', 'update_preset')
```

### Notification System

Cocoa now includes a notification system that:

1. Supports multiple notification handlers
2. Provides console, file, and web notifications
3. Includes notification history
4. Supports different notification levels

To use the notification system:

```python
from main.notification_system import NotificationSystem
from main.logging_manager import Logger

# Initialize logger and notification system
logger = Logger()
notification_system = NotificationSystem(logger)

# Register notification handlers
notification_system.register_handler(ConsoleNotificationHandler(logger))
notification_system.register_handler(FileNotificationHandler(logger, "notifications.log"))

# Send a notification
notification_system.send_notification(
    title="System Status",
    message="System is running normally",
    level="info"
)

# Get notification history
notifications = notification_system.get_notifications()

# Clear notification history
notification_system.clear_notifications()
```

### Performance Analysis

Cocoa now includes a performance analyzer that:

1. Monitors CPU usage
2. Tracks memory usage
3. Analyzes disk performance
4. Monitors network activity
5. Provides detailed performance reports

To use the performance analyzer:

```python
from main.performance_analyzer import PerformanceAnalyzer
from main.logging_manager import Logger

# Initialize logger and analyzer
logger = Logger()
analyzer = PerformanceAnalyzer(logger)

# Start monitoring (every 5 seconds)
analyzer.start_monitoring(5)

# Get current metrics
metrics = analyzer.get_metrics()

# Analyze performance
analysis = analyzer.analyze_performance()

# Stop monitoring
analyzer.stop_monitoring()
```

## Getting Started

### Prerequisites

- Python 3.8+
- Git

### Platform-Specific Requirements

#### Windows
- Windows 10 or later
- PowerShell 5.1 or later
- Visual C++ Redistributable

#### Mac
- macOS 10.14 (Mojave) or later
- Homebrew (for dependency management)
- Xcode Command Line Tools

### Installation

#### Windows
1. Clone the repository:
```bash
git clone https://github.com/shizukutanaka/Cocoa.git
```

2. Install dependencies:
```bash
pip install -r setup/win/requirements.txt
```

3. Run the Windows setup:
```bash
setup\win\setup.bat
```

#### Mac
1. Clone the repository:
```bash
git clone https://github.com/shizukutanaka/Cocoa.git
```

2. Install dependencies:
```bash
pip install -r setup/mac/requirements.txt
```

3. Run the Mac setup:
```bash
setup/mac/setup.sh
```

### Usage

#### Windows
```bash
# Launch Cocoa
launch\win\run_cocoa.bat

# Backup configuration
launch\win\backup_cocoa.bat

# Access web admin
http://localhost:8080
```

#### Mac
```bash
# Launch Cocoa
launch/mac/run_cocoa.sh

# Backup configuration
launch/mac/backup_cocoa.sh

# Access web admin
http://localhost:8080
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/shizukutanaka/Cocoa.git
```

2. Install dependencies:
```bash
pip install -r setup/requirements.txt
```

### Configuration

The main configuration file is located at `config/config.json`. You can override settings using environment variables or by modifying the JSON file.

### Usage

Run the application:
```bash
python launch/run_cocoa.py
```

## Directory Structure

```
cocoa/
├── config/           # Configuration files
│   ├── config.json   # Main configuration
│   └── plugins/      # Plugin configurations
├── launch/          # Launch scripts
│   ├── win/         # Windows launch scripts
│   │   └── run_cocoa.bat
│   └── mac/         # Mac launch scripts
│       └── run_cocoa.sh
├── main/             # Main application code
│   ├── win/         # Windows main files
│   │   └── run_cocoa.bat
│   ├── mac/         # Mac main files
│   │   └── run_cocoa.sh
│   ├── avatar/       # Avatar management
│   ├── parameters/   # Parameter management
│   ├── presets/      # Preset management
│   └── utils/       # Utility functions
├── plugins/          # Custom plugins
├── setup/           # Setup scripts
│   ├── win/        # Windows setup
│   │   └── setup.bat
│   └── mac/        # Mac setup
│       └── setup.sh
├── backup/         # Backup scripts
│   ├── win/       # Windows backup
│   │   └── backup_cocoa.bat
│   └── mac/       # Mac backup
│       └── backup_cocoa.sh
└── locales/         # Language files
```

## Contributing

### Platform-Specific Guidelines

#### Windows
- Use `.bat` files for scripts
- Use Windows line endings (CRLF)
- Use Windows-style paths (\)
- Test on Windows 10 or later

#### Mac
- Use `.sh` files for scripts
- Use Unix line endings (LF)
- Use Unix-style paths (/)
- Test on macOS 10.14 or later

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License

## Support

For support, please open an issue in the GitHub repository.
